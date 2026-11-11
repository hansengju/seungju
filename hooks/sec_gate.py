# -*- coding: utf-8 -*-
"""PreToolUse(Bash|PowerShell) — 보안 게이트 S1: git commit / git push 직전 비밀값 검사 (2026-11-12, devsecops).

  commit : 스테이징된 변경을 gitleaks 로 검사한다. 같은 명령에 -a/--all 이나 앞선 git add 가 있으면
           추적 중인 미스테이징 변경도 본다. 같은 명령에서 새로 add 하는 '새 파일' 은 못 본다 → push 에서 잡는다.
  push   : 원격에 아직 없는 커밋 전체(<src> --not --remotes)를 검사한다 — 밖으로 나가기 직전의 마지막 문.
발견되면 그 명령을 막고(deny) 규칙ID·파일:줄만 알린다. 값은 출력하지 않는다(--redact, I2).
gitleaks 가 없으면 막지 않고 사용자에게 경고(systemMessage)한다.
push 검사가 시간 초과·오류로 끝나지 못하면 사용자에게 묻는다(ask).
훅 자체가 죽으면 진행한다(fail-open) — 오류는 harness-logs/sec_gate-errors.log 에 남긴다.
오탐 예외(.gitleaksignore)는 사용자 확인 후에만 추가한다(I5).
"""
import datetime
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
LOG_DIR = os.environ.get("HARNESS_LOG_DIR") or os.path.join(HOME, ".claude", "harness-logs")
RUN_TIMEOUT = 45
LEAK_RC = 3  # gitleaks --exit-code: 0=깨끗 · 3=발견 · 그 밖=도구 오류
NOWIN = 0x08000000 if os.name == "nt" else 0  # CREATE_NO_WINDOW
QTOK = r"""(?:"[^"]*"|'[^']*'|[^\s;&|()]+)"""
GIT_RE = re.compile(r"\bgit(?:\.exe)?(?P<pre>(?:\s+(?:-C\s+%s|-c\s+%s|--no-pager|--git-dir=%s|--work-tree=%s))*)"
                    r"\s+(?P<act>commit|push)\b(?P<rest>[^;&|\r\n]*)" % (QTOK, QTOK, QTOK, QTOK), re.I)
C_RE = re.compile(r"-C\s+(%s)" % QTOK)
CD_RE = re.compile(r"(?:^|[;&|(]|\s)(?:cd|chdir|pushd|Set-Location|sl)(?:\s+-(?:Path|LiteralPath))?\s+(%s)" % QTOK, re.I)
ADD_RE = re.compile(r"\bgit(?:\.exe)?\b[^;&|\r\n]*?\s(?:add|stage)\b", re.I)
ASSIGN_PS = re.compile(r"\$(\w+)\s*=\s*(%s)" % QTOK)                    # PowerShell: $c = "..."
ASSIGN_SH = re.compile(r"(?:^|[;&|\s])([A-Za-z_]\w*)=(%s)" % QTOK)      # bash: c=... / c="..."
TOK_RE = re.compile(r"""("[^"]*"|'[^']*'|\S+)""")
FIX = ("조치: 값을 지우거나 환경변수·커밋 제외(.gitignore) 설정 파일로 옮긴 뒤 다시 시도한다. "
       "이미 커밋된 값이면 히스토리 수정이 필요하다(R5 — 사용자 승인 후). 값 자체를 출력·인용하지 않는다(I2). "
       "오탐으로 보이면 사용자에게 알리고, .gitleaksignore 예외 추가는 사용자 확인 후에만 한다(I5).")


def unq(tok):
    tok = tok.strip()
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
        tok = tok[1:-1]
    return tok


def assigns(prefix):
    """같은 명령 앞부분의 변수 대입을 모은다 — git -C $c commit 처럼 변수로 경로를 넘기는 경우."""
    v = {}
    for m in ASSIGN_PS.finditer(prefix):
        v[m.group(1).lower()] = unq(m.group(2))
    for m in ASSIGN_SH.finditer(prefix):
        v.setdefault(m.group(1).lower(), unq(m.group(2)))
    return v


def expand(p, var=None):
    if var:
        p = re.sub(r"\$\{(\w+)\}|\$(\w+)\b(?!:)", lambda m: var.get((m.group(1) or m.group(2)).lower(), m.group(0)), p)
    p = re.sub(r"\$env:(\w+)", lambda m: os.environ.get(m.group(1), m.group(0)), p, flags=re.I)
    p = re.sub(r"^(?:\$HOME|\$\{HOME\})(?=[\\/]|$)", lambda m: HOME, p)
    m = re.match(r"^/([a-zA-Z])(/.*)?$", p)  # Git Bash 경로 /c/Users → C:/Users
    if m:
        p = m.group(1).upper() + ":" + (m.group(2) or "/")
    return os.path.expanduser(os.path.expandvars(p))


def work_dir(cmd, m, cwd):
    """(경로, 해석실패여부). 변수를 끝내 못 풀면 해석실패 — 조용히 건너뛰지 않고 호출부가 경고/확인한다(I7)."""
    var = assigns(cmd[:m.start()])
    base = cwd or os.getcwd()
    cds = list(CD_RE.finditer(cmd[:m.start()]))
    parts = ([unq(cds[-1].group(1))] if cds else []) + [unq(c.group(1)) for c in C_RE.finditer(m.group("pre") or "")]
    for part in parts:
        e = expand(part, var)
        if "$" in e:
            return None, True
        base = os.path.join(base, e)
    return os.path.normpath(base), False


def git_top(d):
    if not os.path.isdir(d):
        return None
    p = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True, timeout=10,
                       creationflags=NOWIN)
    if p.returncode != 0:
        return None
    return os.path.normpath(p.stdout.decode("utf-8", "replace").strip())


def find_gitleaks():
    if "SEC_GATE_GITLEAKS" in os.environ:  # 시험용 강제 경로
        v = os.environ["SEC_GATE_GITLEAKS"]
        return v if os.path.isfile(v) else None
    w = shutil.which("gitleaks")
    if w:
        return w
    # 앱이 설치 전에 떠서 PATH 가 갱신 안 된 경우 — winget 설치 위치를 직접 본다
    la = os.environ.get("LOCALAPPDATA", "")
    cands = [os.path.join(la, "Microsoft", "WinGet", "Links", "gitleaks.exe")]
    cands += sorted(glob.glob(os.path.join(la, "Microsoft", "WinGet", "Packages", "Gitleaks.Gitleaks_*", "gitleaks.exe")))
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def leaks(gl, repo, extra):
    p = subprocess.run([gl, "git", repo, "--redact", "--no-banner", "--exit-code", str(LEAK_RC),
                        "-f", "json", "-r", "-"] + extra,
                       capture_output=True, timeout=RUN_TIMEOUT, creationflags=NOWIN)
    if p.returncode == 0:
        return []
    if p.returncode != LEAK_RC:
        raise RuntimeError("gitleaks rc=%d %s" % (p.returncode, p.stderr.decode("utf-8", "replace")[-300:]))
    rows = json.loads(p.stdout.decode("utf-8", "replace").strip() or "[]")
    return [(r.get("RuleID", "?"), r.get("File", "?"), r.get("StartLine", 0), (r.get("Commit") or "")[:7]) for r in rows]


def commit_all(rest):
    for t in (unq(x) for x in TOK_RE.findall(rest)):
        if t == "--all" or re.fullmatch(r"-[A-Za-z]*a[A-Za-z]*", t):
            return True
    return False


def push_src(rest):
    toks = [unq(t) for t in TOK_RE.findall(rest)]
    opts = [t for t in toks if t.startswith("-")]
    pos = [t for t in toks if not t.startswith("-")]
    if any(o in ("--all", "--mirror", "--branches") for o in opts):
        return "--all"
    if len(pos) >= 2:
        return pos[1].lstrip("+").split(":")[0] or None  # ':branch' = 원격 삭제 → 보낼 커밋 없음
    return "HEAD"


def out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=True))


def decide(event, reason):
    out({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": event,
                                "permissionDecisionReason": reason}})


def log(d, acts, repos, n, decision):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, "events-%s.jsonl" % datetime.date.today().strftime("%Y%m")), "ab") as f:
        f.write((json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                             "ev": "SecGate", "session": d.get("session_id"), "agent_id": d.get("agent_id"),
                             "tool": d.get("tool_name"), "actions": acts, "repos": repos, "findings": n,
                             "decision": decision}, ensure_ascii=False) + "\n").encode("utf-8"))


def main():
    d = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    if d.get("tool_name") not in ("Bash", "PowerShell"):
        return
    cmd = (d.get("tool_input") or {}).get("command") or ""
    if "git" not in cmd.lower():
        return
    jobs, seen, unresolved = [], set(), []
    for m in GIT_RE.finditer(cmd):
        act = m.group("act").lower()
        wd, bad = work_dir(cmd, m, d.get("cwd"))
        if bad:
            unresolved.append(act)
            continue
        repo = git_top(wd)
        if not repo:
            continue
        if act == "commit":
            specs = [["--pre-commit", "--staged"]]
            if commit_all(m.group("rest")) or ADD_RE.search(cmd[:m.start()]):
                specs.append(["--pre-commit"])
        else:
            src = push_src(m.group("rest"))
            if not src:
                continue
            specs = [["--log-opts", "%s --not --remotes" % src]]
        for s in specs:
            k = (act, repo, tuple(s))
            if k not in seen:
                seen.add(k)
                jobs.append((act, repo, s))
    if not jobs and not unresolved:
        return
    acts = sorted({a for a, _, _ in jobs} | set(unresolved))
    repos = sorted({r for _, r, _ in jobs})
    if not jobs:
        if "push" in unresolved:
            log(d, acts, repos, -1, "ask-unresolved-path")
            decide("ask", "[보안 S1] git push 의 저장소 경로(변수)를 해석하지 못해 비밀값 검사를 못 했다. "
                          "경로를 직접 적어 다시 실행하거나, 사용자 확인 후에만 진행한다.")
        else:
            log(d, acts, repos, -1, "allow-unresolved-path")
            out({"systemMessage": "[보안 S1] git commit 의 저장소 경로(변수)를 해석하지 못해 비밀값 검사를 건너뛰었다. push 단계에서 다시 검사된다."})
        return
    gl = find_gitleaks()
    if not gl:
        log(d, acts, repos, -1, "skip-no-gitleaks")
        out({"systemMessage": "[보안 S1] gitleaks 를 찾지 못해 git %s 비밀값 검사를 건너뛰었다. "
                              "설치: winget install --id Gitleaks.Gitleaks --exact" % "/".join(acts)})
        return
    found, errors = [], []
    for act, repo, s in jobs:
        try:
            found += [(act, f) for f in leaks(gl, repo, s)]
        except Exception as e:
            errors.append((act, repr(e)[:200]))
    errors += [(a, "경로 변수 해석 실패") for a in unresolved]
    uniq = []
    for act, f in found:
        if (f[0], f[1], f[2]) not in [(u[1][0], u[1][1], u[1][2]) for u in uniq]:
            uniq.append((act, f))
    if uniq:
        lines = ["  %s  %s:%s%s" % (f[0], f[1], f[2], (" @" + f[3]) if f[3] else "") for _, f in uniq[:10]]
        more = len(uniq) - len(lines)
        reason = ("[보안 S1] gitleaks: 비밀값 의심 %d건 → git %s 차단 (값은 가림).\n%s%s\n%s"
                  % (len(uniq), "/".join(sorted({a for a, _ in uniq})), "\n".join(lines),
                     ("\n  …외 %d건" % more) if more > 0 else "", FIX))
        log(d, acts, repos, len(uniq), "deny")
        decide("deny", reason)
    elif any(a == "push" for a, _ in errors):
        log(d, acts, repos, -1, "ask-scan-error")
        decide("ask", "[보안 S1] push 전 비밀값 검사를 끝내지 못했다(%s). 사용자 확인 후에만 진행한다." % errors[0][1])
    elif errors:
        log(d, acts, repos, -1, "allow-scan-error")
        out({"systemMessage": "[보안 S1] commit 전 비밀값 검사 오류로 건너뜀(%s). push 단계에서 다시 검사된다." % errors[0][1]})
    else:
        log(d, acts, repos, 0, "allow")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "sec_gate-errors.log"), "a", encoding="utf-8") as f:
                f.write("%s %r\n" % (datetime.datetime.now().isoformat(timespec="seconds"), e))
        except Exception:
            pass
    sys.exit(0)
