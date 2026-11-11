---
name: mcp-health
description: >-
  Claude Code(Windows)의 MCP 서버 연결을 점검·진단할 때 먼저 로드한다. "MCP 연결 확인해줘 / 재시작했어 확인해 /
  MCP 가 안 붙는다 / CONNECT_TIMEOUT / 버전 고정·업데이트" 요청에 쓴다. 점검 스크립트 한 번으로 앱 시작 시각·
  MCP_TIMEOUT·서버별 설정 버전 vs 실제 실행 버전·이번 세션 연결 결과를 보고, 서버별 가장 가벼운 실제 호출로
  "연결됨" 을 증명한다. 로그 위치·시간 초과 판독·버전 고정 절차·이 PC 에서 실제로 틀렸던 것을 담고 있다.
when_to_use: MCP 연결, MCP 확인, MCP 안 됨, 연결 실패, 연결 시간 초과, CONNECT_TIMEOUT, MCP_TIMEOUT, 재시작했어, 앱 재실행, ReVa 연결, playwright 연결, context7 연결, omniroute, graphify, npx @latest, MCP 버전 고정, MCP 업데이트
---

# MCP 연결 점검 (Claude Code · Windows)

## 0. 원칙

- **"연결됨" = 실제 호출이 응답했다.** 설정 파일·도구 목록만 보고 말하지 않는다. 호출을 못 했으면 "프로세스·도구 등록까지 확인" 으로 낮춘다(L1.6).
- **MCP 연결 ≠ 백엔드 정상.** MCP 가 응답해도 뒤의 데몬이 죽어 있을 수 있다(예: omniroute 응답 안의 `fetch failed`).
- **설정을 바꿨으면 "재시작 반영" 을 따로 증명한다** — 실행 중인 프로세스 명령줄이 설정과 같아야 한다(스크립트의 MISMATCH 표시).

## 1. 한 번에 보기

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\.claude\skills\mcp-health\scripts\mcp_health.ps1" -Cwd "<세션 작업 폴더>" -History
```

- `app` — Claude 프로세스 중 가장 이른 시작 시각(재시작 여부 판단).
- `MCP_TIMEOUT` — 서버 기동 대기 한도. 지금 `~/.claude/settings.json` 의 env 에 `90000`(기본 30000).
- 서버마다 `config`(설정 명령) · `running`(실제 실행 명령의 버전 문자열·최근 시작 시각) · `pin`(버전 고정 여부) · `last`(이 세션 폴더 로그의 한도·시도 횟수·결과).
- `running` 에 **MISMATCH** → 설정만 바뀌고 아직 재시작 전. `-History` → 모든 세션 로그의 성공·시간 초과 횟수와 기동 시간 분포.
- 설정의 env 값·키처럼 생긴 인자는 출력하지 않는다. 스크립트는 영문만 쓴다(PowerShell 5.1 이 BOM 없는 .ps1 을 cp949 로 읽어 한글이 깨짐).

## 2. 서버별 가장 가벼운 실제 호출

| 서버 | 호출 | 정상 반응 |
|---|---|---|
| context7 | `resolve-library-id` (아무 라이브러리명) | 후보 목록 |
| sequential-thinking | `sequentialthinking` 1단계, `nextThoughtNeeded=false` | `thoughtNumber:1` JSON |
| playwright | `browser_tabs` list → **반드시 `browser_close`** | `about:blank` 탭 → "No open tabs" (브라우저가 실제로 뜬다) |
| ReVa | `list-project-files` folderPath `/` | `items:[]` 등 JSON |
| graphify | `graph_stats` | 그래프가 없는 폴더면 `graph.json not found` — 이것도 서버가 응답한 것 |
| omniroute | `omniroute_get_health` | `degraded: fetch failed` 면 MCP 는 붙었고 **데몬(127.0.0.1:20128)이 꺼짐** → `Get-NetTCPConnection -LocalPort 20128 -State Listen` 로 확인 |

## 3. 로그 판독

- 위치: `%LOCALAPPDATA%\claude-cli-nodejs\Cache\<세션 폴더 경로의 영숫자 외 문자를 - 로 바꾼 이름>\mcp-logs-<서버명>\<UTC 시각>.jsonl`
  (예: `C:\Users\hanse\Desktop\tmp` → `C--Users-hanse-Desktop-tmp`). 파일명 시각은 UTC — 한국 시간은 +9.
- 핵심 줄: `Starting connection with timeout of Nms` · `Successfully connected (transport: stdio) in Nms` ·
  `Connection timeout triggered after Nms` · `Connection failed (CONNECT_TIMEOUT)` · `Server stderr: …`
- **시간 초과 판독**: 실패 시점의 `Server stderr` 마지막 줄이 기동 단계(예: `Initializing PyGhidra...`)에 멈춰 있으면 고장이 아니라 **기동이 한도보다 느린 것**. 한도는 `MCP_TIMEOUT`(ms).
- 일부 세션 폴더는 경로가 Windows 길이 한도를 넘어 읽히지 않는다 — 집계 시 건너뛴 수를 같이 보고한다.

## 4. 버전 고정·업데이트

1. 지금 실제로 쓰는 버전: `%LOCALAPPDATA%\npm-cache\_npx\*\node_modules\<패키지>\package.json` 의 version.
2. `~/.claude.json` 을 먼저 백업(`.claude.json.bak.<날짜>_<사유>`) → `mcpServers.<이름>.args` 의 패키지 인자만 Edit 도구로 `@<버전>` 으로 바꾼다.
   **PowerShell `ConvertTo-Json` 으로 다시 쓰지 않는다**(기본 깊이 2 라 중첩 설정이 잘린다).
3. 검증: JSON 파싱 + `git diff --no-index --numstat <백업> <현재>` 가 바꾼 줄 수와 같은지 → 앱 재시작 → 스크립트로 `running` = `config`.
4. 올릴 때도 버전을 지정하고 사용자 확인 후에만 한다(공급망). 현재 고정: context7 4.6.0 · playwright 0.0.85 · sequential-thinking 2.1.1.

## 5. 서버별 메모

- **ReVa**: PyGhidra(자바) 기동이 느리다 — 성공 기동 11.5~28.6초(중앙값 21.9초, 성공 16회). 30초 한도 시절 시간 초과 55회(로그 72개 기준). 90초 한도 첫 재시작(2026-11-12)은 21.9초에 1회로 연결. 세션마다 1개씩 뜨고 하나에 약 0.5GB. `server/discover` 검증 경고는 무해(클라이언트가 이후 건너뜀). 설치 구성은 메모리 `reference_reva_mcp_install`.
- **npx 서버(context7·playwright·sequential-thinking)·omniroute** 도 30초 한도 시절 시간 초과가 있었다(context7 24회 · omniroute 15회 · sequential-thinking 8회 · playwright 7회). 앱 재시작 직후처럼 한꺼번에 뜰 때 몰린다.
- **omniroute**: MCP 브리지(`mcp-server.mjs`)와 데몬(127.0.0.1:20128)이 따로다. `omniroute update` 는 다운그레이드라 쓰지 않는다(메모리 `project_omniroute_gateway`).

## 6. 실제로 틀렸던 것 (2026-11-12)

- 사용자가 재시작했다고 한 뒤에도 앱 프로세스가 01:05 시작 그대로였고, MCP 도 고정 전 명령으로 떠 있었다(원인 미확인) → 시작 시각과 `running`/`config` 비교로 판정한다. 말로 "재시작됨" 을 받아 쓰지 않는다.
- playwright 는 호출하면 브라우저가 뜬다 → 확인 후 바로 닫는다(백그라운드 0, L7.6).
- "MCP 연결 OK" 를 "기능 정상" 으로 말하면 안 된다 — omniroute 는 연결됐지만 데몬이 꺼져 있었다.
