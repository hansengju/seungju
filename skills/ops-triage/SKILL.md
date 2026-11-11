---
name: ops-triage
description: >-
  윈도우 서버·PC 에서 "프로그램이 죽는다/반복 오류/느리다/서비스가 안 뜬다" 를 운영 관점으로 원인 추적할 때 먼저 로드한다.
  이벤트 로그(응용 프로그램 오류 1000·1001, 서비스 7000·7031) 로 크래시를 확정하고, 앱 로그 마지막 줄·예외 코드
  (0x0EEDFADE 델파이 미처리 예외 등)·소켓 오류(10054/10060)·메모리·SQL Server 상태를 같은 시각으로 맞춰
  방아쇠(외부)와 근본(코드 결함)을 나눠 보고한다. 네이티브 PowerShell·T-SQL(읽기 전용)만 쓴다.
when_to_use: 크래시, 프로그램 죽음, 응용 프로그램 오류, 이벤트 뷰어, 이벤트 로그, 0eedfade, Socket Error, 10054, 10060, Connection reset, 메모리 부족, 서버 느림, SQL Express, MSSQL 메모리, 서비스 시작 실패, 7000, WER, 로그 분석, 반복 오류
---

# 운영 원인 추적 (Windows · Delphi · SQL Server)

## 0. 원칙

- **증거 순서**: OS 기록(이벤트 로그·작업 관리자·성능 카운터) → 앱 로그 원문 줄 → 추론. 앱 로그에 없다고 "증거 없음" 이라 말하지 않는다 — OS 쪽부터 본다.
- **같은 시각으로 맞춘다**: 이벤트 시각 ±1~2초의 앱 로그 마지막 줄을 붙여야 "원인" 이라고 쓸 수 있다(L1.6). 한쪽만 있으면 "가설".
- **방아쇠 vs 근본을 나눈다**: 예) 방아쇠 = 서버가 연결을 끊음(10054) / 근본 = 그 예외를 잡지 않아 프로세스가 죽음.
- **읽기 전용**: 설정 변경(SQL `max server memory`, 서비스 복구 정책 등)은 R3 — 사용자 승인 후. 운영 DB 쓰기 금지(M4).
- 대용량 로그(수백 MB)는 통째로 읽지 않는다. 시각·키워드로 잘라 본다.

## 1. 크래시 확정 — 이벤트 로그

```powershell
# 응용 프로그램 오류(1000) · WER(1001) — 최근 3일
Get-WinEvent -FilterHashtable @{LogName='Application'; Id=1000; StartTime=(Get-Date).AddDays(-3)} |
  ForEach-Object { $p = $_.Properties
    [pscustomobject]@{ Time=$_.TimeCreated; App=$p[0].Value; Ver=$p[1].Value; Module=$p[3].Value
                       Code=$p[6].Value; Offset=$p[7].Value; Path=$p[10].Value } } | Format-Table -AutoSize
# 서비스 제어 관리자: 7000 시작 실패 · 7031/7034 비정상 종료
Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Service Control Manager'; Id=7000,7031,7034; StartTime=(Get-Date).AddDays(-3)} |
  Select-Object TimeCreated, Id, @{n='Msg';e={($_.Message -split "`r?`n")[0]}}
```

이벤트 1000 의 EventData 순서: AppName, AppVersion, AppTimeStamp, ModuleName, ModuleVersion, ModuleTimeStamp,
ExceptionCode, FaultingOffset, ProcessId, ProcessCreationTime, AppPath, ModulePath …

| 예외 코드 | 뜻 | 다음 할 일 |
|---|---|---|
| `0x0EEDFADE` | 델파이 예외가 끝까지 안 잡혀 OS 로 올라옴(모듈은 보통 KERNELBASE.dll) | 앱 로그 마지막 줄의 예외 클래스(EIdSocketError 등)로 원인 특정 → 그 호출 경로의 try-except 확인 |
| `0xC0000005` | 접근 위반(해제된 메모리·nil 사용) | 오프셋·모듈로 위치 특정, 해제 후 사용 의심 |
| `0xC00000FD` | 스택 오버플로(무한 재귀) | 재귀·깊은 콜스택 |
| `0xC0000409` | 보안 검사 실패/즉시 종료(fail-fast) | 런타임 무결성 오류 |
| `0xE0434352` | .NET CLR 예외 | .NET 이벤트 1026 의 스택 |

## 2. 앱 로그 대조

```powershell
# cp949 로그: PS 5.1 의 -Encoding Default = ANSI(cp949). 크래시 직전 줄만
Select-String -Path 'X:\path\DEBUG_20260630.log' -Pattern '^\d+ / 07:21:(0|1)' -Encoding Default | Select-Object -Last 20
# 예외 파일이 있는 날/없는 날을 비교 — 없으면 예외 핸들러조차 못 돌고 즉사한 것
Get-ChildItem 'X:\path' -Filter 'Exception_*.log'
```

| 소켓 오류 | 뜻 |
|---|---|
| 10054 | WSAECONNRESET — 상대가 연결을 끊음(RST) |
| 10060 | WSAETIMEDOUT — 응답 시간 초과 |
| 10061 | WSAECONNREFUSED — 상대가 받지 않음(포트 닫힘·서비스 다운) |
| 11001 | WSAHOST_NOT_FOUND — 이름 해석 실패 |

`file` 명령은 cp949 로그를 iso-8859-1 로 잘못 보고한다 — 인코딩 판단 근거로 쓰지 않는다.

## 3. 자원 압박 (메모리)

```powershell
$os = Get-CimInstance Win32_OperatingSystem
'{0:N1} / {1:N1} GB 사용' -f (($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB), ($os.TotalVisibleMemorySize/1MB)
Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name, Id, @{n='WS_MB';e={[int]($_.WorkingSet64/1MB)}}
Get-Counter '\Memory\Available MBytes','\Memory\Pages/sec' -SampleInterval 2 -MaxSamples 5
```

지금 값은 지금 상태일 뿐이다. 사건 시각의 값이 없으면 "그 시각 메모리 압박" 은 가설로 쓴다(재현 시 위 카운터를 그 시각에 기록).

## 4. SQL Server (읽기 전용)

`sqlcmd -S .\SQLEXPRESS -E -Q "<쿼리>"` (sqlcmd 가 있을 때) 또는 SSMS.

```sql
SELECT SERVERPROPERTY('Edition') AS edition, SERVERPROPERTY('ProductVersion') AS ver;
SELECT physical_memory_in_use_kb/1024 AS used_mb, memory_utilization_percentage FROM sys.dm_os_process_memory;
SELECT name, value_in_use FROM sys.configurations WHERE name = 'max server memory (MB)';
SELECT TOP 10 wait_type, wait_time_ms FROM sys.dm_os_wait_stats ORDER BY wait_time_ms DESC;
EXEC xp_readerrorlog 0, 1, N'memory';   -- 'deadlock', 'lock' 도 같은 방식
```

- Express 는 버퍼 풀 상한이 있다(Microsoft 에디션별 용량 제한 문서: 2016 SP1 이후 1410MB). 작업 관리자의 SQL 사용량이 그 근처면 상한 도달로 본다.
- `sp_lock`·`sys.dm_tran_locks` 는 **지금** 의 잠금만 보인다 — 과거 사건 시각의 잠금 부재 증명이 아니다.

## 5. 보고 형식

사건마다 한 줄: `이벤트 시각 · 프로세스 · 예외 코드 · 앱 로그 마지막 줄(인용) · 자원 상태` → 아래에
"방아쇠 / 근본 / 확정·가설 구분 / 고칠 곳(파일·함수) / 다음 확인 1개". 결론부터 짧게.

## 6. 관련 도구 (보안·개발 연계)

- 크래시 난 실행파일의 서명·버전: `sigcheck -a -h <exe>` — **첫 실행 때 Sysinternals 약관 창** 이 뜬다. 약관 동의(`-accepteula`)는 사용자 확인 후.
- 의존성 취약점: `osv-scanner scan source -r <프로젝트 폴더>`
- 비밀값: git commit/push 때 `sec_gate` 훅이 gitleaks 로 자동 검사. 수동은 `gitleaks git <저장소> --redact`.
- 델파이 소스에서 호출 경로·try-except 확인은 delphi-cms 스킬(dlens)로.

## 7. 실제로 틀렸던 것 (181 로그 분석 — 로그 날짜 2026-06-29·30)

- 서버 프로세스 로그에 메모리 줄이 없다고 "서버 메모리는 검증 불가" 라고 했다 → 작업 관리자(81% 사용, SQL 1.27GB)가 증거였다. OS 쪽을 먼저 봤어야 했다.
- 같은 PC 의 클라이언트·서버를 구분하지 않고 "네트워크 이상" 으로 뭉뚱그리기 쉽다 → 어느 프로세스가 끊었는지(RST 주체)부터 나눈다.
- 1.5M 줄 로그를 통째로 읽으려 하지 말 것 — 예외 로그(작음) → 이벤트 시각 → 그 시각 줄 순서로 좁힌다.
