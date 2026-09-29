---
name: delphi-cms
description: >-
  Delphi 10.4 CMS 업무화면(D:\K — PAY/EXC/BCA/REC/SET 화면, 05. Popup, 02. Library) 분석·수정 전용.
  .pas/.dfm/.dpr/.dproj 를 읽거나 고치기 전, "이 코드 실행돼?/어디서 호출돼?/막혀 있어?/수정 가능해?"
  같은 판정을 하기 전, dcc32/F2613 빌드 오류를 볼 때 먼저 로드한다. 주석·조건부컴파일·DFM 선언을
  사람 눈 대신 판정하는 dlens 도구와, 이 코드베이스에서 실제로 틀렸던 함정 목록을 담고 있다.
when_to_use: 델파이, 해외송금, 대량송금, 당발송금, ERP 가져오기, 엑셀 업로드, 전문(TR_FXD), 팝업, uTrTransList, SetError, ERP_ERROR, cp949 파일 편집
allowed-tools: Bash(python ${CLAUDE_SKILL_DIR}/scripts/dlens.py *) Bash(PYTHONIOENCODING=utf-8 python ${CLAUDE_SKILL_DIR}/scripts/dlens.py *)
---

# Delphi CMS (D:\K) 작업 규칙

판정은 **dlens 가 한다.** 눈으로 `//` 만 보고 "활성"이라고 말하지 않는다.
`D:\K` 는 대부분 **cp949 + CRLF** 다(03. PT .pas 441개 중 cp949 395).

```
python "${CLAUDE_SKILL_DIR}/scripts/dlens.py" <명령> ...
```

| 하려는 말 | 먼저 돌릴 것 |
|---|---|
| "이 줄은 실행된다 / 주석이다" | `live <파일> <줄>` |
| "여기서 호출된다 / 아무 데서도 안 쓴다" | `callers <식별자> <폴더>` (DFM 이벤트 배선 포함) |
| "이 패치는 if 안에 들어갔다 / 밖이다" | `nest <파일> <줄>` |
| "검색했더니 N건" | `grep <정규식> <경로>` — 줄마다 라벨과 [범위] 가 붙는다 |
| "DFM 에 그 컴포넌트가 없다" | `dfm <dfm파일> <이름>` (object·inline·inherited 3종) |
| "이 파일 편집해도 되나" | `enc <파일>` |

**신뢰도(2026-09-29 실측)**: D:\K 2,151개 파일 대상 반증 시험 2회(에이전트 53개).
주석·문자열·지시어 판정(`live` 라벨)은 **반례 0건**이라 근거로 인용해도 된다.
구조(`nest`)·도달불가 추정은 휴리스틱이다 — 반례 43건을 고쳤지만 남은 오판이 있을 수 있으니, 결론을 좌우하면 원문을 함께 본다.

조건부 컴파일: Delphi 10.4 Win32 기본 심볼(UNICODE·MSWINDOWS·WIN32·VER340 등)은 켜진 것으로, 다른 플랫폼·버전
심볼(CPUX64·WIN64·NEXTGEN·VER330 등)은 꺼진 것으로 본다.
프로젝트 심볼(DEBUG·KEBHanaSA 등)은 모른다 → 결과에 "심볼 값 미상"이 붙으면 `.dproj` 의 `DCC_Define` 을 확인해
`--define X` / `--undef X` 로 다시 돌린다. [주의] 가 붙은 구조 판정은 분기를 정하기 전까지 확정하지 않는다.

## 주장 규칙 — 증거 범위를 넘는 말을 하지 않는다

1. **0건은 "그 범위 안에 그 텍스트가 없다"까지만.** 함수 안 0건을 "경로 전체에 없다"로 올리지 않는다.
   경로를 말하려면 `callers` 로 호출 체인을 따라가고, 거친 파일 목록을 적는다.
2. **파일마다 따로 확인한다.** 형제 화면(당발 ↔ 대량)의 결론을 옮기지 않는다. 같은 이름 함수라도 내용이 다르다.
3. **서브에이전트·워크플로 결과는 미검증이다.** 사용자에게 전하기 전에 핵심 주장의 파일:줄을 dlens 나 원문으로 다시 확인한다.
   확인 못 한 것은 "(에이전트 주장·미검증)"이라고 적는다.
4. **"가능 / 불가 / 취약 / 원인은" 결론은 확인 전까지 가설이다.** 특히 "수정 가능", "막혀 있다"는
   호출부가 넘기는 파라미터와 대상 목록을 확인한 뒤에만 단정한다(→ references/pitfalls.md #8).
5. **빌드 오류 원인은 로그 전문을 받은 뒤에 말한다.** 첫 Fatal 줄과 dcc32 명령의 `-LU` 목록을 대조한다(→ references/build.md).

## 편집 절차 (cp949 파일)

- **Read/Edit/Write 도구로 cp949 파일을 고치지 않는다(K6).** Read 는 보기 용도로만(한글은 깨져 보인다).
- Python 으로: `raw = open(p,'rb').read()` → BOM 없음 확인 → `raw.decode('cp949').split('\r\n')`
  → **앵커 줄 내용 검증**(줄 번호 + 기대 문자열, 어긋나면 중단) → **아래에서 위로** 삽입/치환
  → `'\r\n'.join(...).encode('cp949')` 저장 → 저장본 cp949 왕복·CRLF 수·단독 LF 0·BOM 없음 확인.
- 편집 전 백업: `<파일>.bak.YYYYMMDD` (이미 있으면 덮어쓰지 않는다).
- 편집 후 **삽입한 줄마다 `nest`** 로 감싼 구조를 보고서에 적는다 — 의도한 분기 안/밖인지.
- 이 PC 에는 Delphi 가 없다. 컴파일 검증(V1/V3)은 **미검증**으로 보고하고 빌드 PC 확인을 요청한다.

## 이 코드베이스의 구조 (자세히는 references/)

- 검증 함수(`ValidityCheck_FEXCEL_MT/MX` 등)는 중첩 프로시저 `SetError` 로 행에 `ERP_ERROR='Y'` 와
  `ERP_ERROR_MSG` 를 쌓는다. **그 자리에서 막지 않는다.** 차단은 `btn_RegClick` 의 오류 행 검사가 한다.
- 팝업은 `iiCom.iMsg.MsgWarning(...)` 후 `Exit;` 로 막는다(행 표시 방식이 아님).
- 수정 팝업 `EXC0102020_01` 은 두 화면이 함께 쓰고, **등록된 목록(`tv_RegSongGeumList`)** 을 받는다.
- 화면별 사실: `references/screens/*.md` · 공통 패턴: `references/patterns.md` · 경로: `references/k-map.md`
- **references 의 줄 번호는 적은 날 기준이다.** 쓰기 전에 `python "${CLAUDE_SKILL_DIR}/scripts/verify_refs.py"` 로
  근거 줄이 아직 맞는지 확인하고, 어긋난 항목은 다시 찾은 뒤 쓴다.

## 틀렸던 것에서 배운 것

`references/pitfalls.md` — 2026-09 세션에서 사용자가 바로잡은 8건. 같은 유형의 판정을 하기 전에 읽는다.
정정이 새로 생기면 근거(파일:줄)와 함께 여기에 추가한다.
