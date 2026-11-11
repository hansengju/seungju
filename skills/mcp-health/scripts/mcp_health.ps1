# mcp_health.ps1 - one-shot, read-only MCP connection check for Claude Code on Windows.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File mcp_health.ps1 [-Cwd <session dir>] [-History]
# Shows: app start, MCP_TIMEOUT, each user-scope server's configured spec vs the version actually running,
#        last connect result from this session dir's mcp-logs, and (with -History) connect-time stats.
# Never prints env values or secret-looking args from ~/.claude.json.
# ASCII only on purpose: Windows PowerShell 5.1 reads BOM-less .ps1 files as ANSI (cp949).
param([string]$Cwd = (Get-Location).Path, [switch]$History)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = 'SilentlyContinue'
$H = $env:USERPROFILE
$CacheRoot = Join-Path $env:LOCALAPPDATA 'claude-cli-nodejs\Cache'

$cl = @(Get-Process -Name 'claude' | Sort-Object StartTime)
if ($cl.Count) { "== app: claude processes={0}, earliest start={1:yyyy-MM-dd HH:mm:ss}" -f $cl.Count, $cl[0].StartTime }
else { "== app: claude not running" }

$st = Get-Content -Raw -Encoding UTF8 (Join-Path $H '.claude\settings.json') | ConvertFrom-Json
$to = $st.env.MCP_TIMEOUT
if (-not $to) { $to = 'unset -> default 30000' }
"== MCP_TIMEOUT (settings.json env) = $to"

$j = Get-Content -Raw -Encoding UTF8 (Join-Path $H '.claude.json') | ConvertFrom-Json
$procs = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine })
$enc = $Cwd -replace '[^A-Za-z0-9]', '-'

function Safe([string]$a) {
  if ($a -match '(?i)(key|token|secret|passw)' -or $a -match '[A-Za-z0-9_\-]{40,}') { return '<redacted>' }
  return $a
}

""
"== servers (config spec | running | pin | last connect in this session dir)"
foreach ($p in $j.mcpServers.PSObject.Properties) {
  $n = $p.Name; $s = $p.Value; $a = @($s.args)
  if ($a -contains 'npx') {
    $spec = [string]$a[-1]
    $base = $spec -replace '^((@[^/@]+/)?[^@]+)@.*$', '$1'
    $ver = ''
    if ($spec -match '^(@[^/@]+/)?[^@]+@(.+)$') { $ver = $Matches[2] }
    $pin = if ($ver -and $ver -ne 'latest') { 'pinned' } else { 'NOT PINNED (fetches latest every start)' }
    $rx = [regex]::Escape($base) + '(@[\w.\-]+)?'
  } elseif ($a.Count) {
    $spec = Split-Path ([string]$a[-1]) -Leaf; $base = $spec; $pin = 'n/a (local file)'; $rx = [regex]::Escape($spec)
  } else {
    $spec = Split-Path ([string]$s.command) -Leaf; $base = $spec; $pin = 'n/a (local exe)'; $rx = [regex]::Escape($spec)
  }
  $hits = @($procs | Where-Object { $_.CommandLine -match $rx })
  $tokens = @($hits | ForEach-Object { [regex]::Match($_.CommandLine, $rx).Value } | Sort-Object -Unique)
  $newest = ($hits | Sort-Object CreationDate -Descending | Select-Object -First 1).CreationDate
  if (-not $hits.Count) { $run = 'no process' }
  else {
    $run = ($tokens -join ',') + (" (newest start {0:HH:mm:ss})" -f $newest)
    if ($pin -eq 'pinned' -and $tokens -notcontains $spec) { $run += ' MISMATCH: running != config -> restart the app' }
  }
  $logDir = Join-Path $CacheRoot ("$enc\mcp-logs-$n")
  $last = 'no log for this session dir'
  $lf = Get-ChildItem -LiteralPath $logDir -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($lf) {
    $lines = Get-Content -LiteralPath $lf.FullName -Encoding UTF8
    $lim = ''; $res = 'in progress / no result yet'; $tries = 0; $hint = ''
    foreach ($l in $lines) {
      if ($l -match 'Starting connection with timeout of (\d+)ms') { $lim = $Matches[1]; $tries++ }
      if ($l -match 'Successfully connected \(transport: (\w+)\) in (\d+)ms') { $res = "OK in $($Matches[2])ms" }
      if ($l -match 'Connection failed[^"]*\(([A-Z_]+)\)') { $res = "FAILED $($Matches[1])" }
      if ($l -match '"error":"Server stderr: ([^"]*)"') { $hint = ($Matches[1] -replace '\\r\\n', ' | ') }
    }
    if ($hint.Length -gt 90) { $hint = '...' + $hint.Substring($hint.Length - 90) }
    $last = "{0:HH:mm:ss} limit={1}ms attempts={2} -> {3}" -f $lf.LastWriteTime, $lim, $tries, $res
    if ($res -like 'FAILED*' -and $hint) { $last += "  stderr tail: $hint" }
  }
  "- {0}`n    config : {1} {2}`n    running: {3}`n    pin    : {4}`n    last   : {5}" -f $n, (Safe ([string]$s.command)), (($a | ForEach-Object { Safe ([string]$_) }) -join ' '), $run, $pin, $last
}

if ($History) {
  ""
  "== history (all session dirs under claude-cli-nodejs\Cache)"
  $dirs = @(Get-ChildItem -LiteralPath $CacheRoot -Directory)
  foreach ($p in $j.mcpServers.PSObject.Properties) {
    $n = $p.Name; $ok = @(); $fail = 0; $skipped = 0; $files = 0
    foreach ($d in $dirs) {
      $ld = Join-Path $d.FullName "mcp-logs-$n"
      if ($ld.Length -ge 248) { $skipped++; continue }
      if (-not (Test-Path -LiteralPath $ld)) { continue }
      foreach ($f in (Get-ChildItem -LiteralPath $ld -File)) {
        if ($f.FullName.Length -ge 260) { $skipped++; continue }
        $files++
        foreach ($l in (Get-Content -LiteralPath $f.FullName -Encoding UTF8)) {
          if ($l -match 'Successfully connected \(transport: \w+\) in (\d+)ms') { $ok += [int]$Matches[1] }
          if ($l -match 'Connection timeout triggered after') { $fail++ }
        }
      }
    }
    $line = "- {0}: logs={1} ok={2} timeouts={3}" -f $n, $files, $ok.Count, $fail
    if ($ok.Count) { $sorted = $ok | Sort-Object; $line += " connect ms min/median/max={0}/{1}/{2}" -f $sorted[0], $sorted[[int]($sorted.Count / 2)], $sorted[-1] }
    if ($skipped) { $line += " (skipped $skipped path(s) over the Windows length limit)" }
    $line
  }
}
