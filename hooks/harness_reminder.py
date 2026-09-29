# -*- coding: utf-8 -*-
"""UserPromptSubmit 훅: 매 턴 하네스(Strategic Code Guardian) 핵심 안내를 주입한다.

2026-09-29 구조 개편 3단계(사용자 결정):
  - 뺀 것: '응답 첫 줄 Rule ID 명시', 'L0.3 자기점검 1줄' — 117회 중 위반을 한 번도 잡지 못했고 형식만 남았다.
  - 넣은 것: 주장 강도 = 증거 범위, L1.5 liveness, 정정 발화 감지(기록 + 재확인 지시).
stdin 은 바이트로 받아 UTF-8 로 푼다(훅 stdin 기본 인코딩이 cp949).
ensure_ascii=True 로 ASCII-only JSON 출력 → Windows cp949 파이프에서도 한글 안 깨짐.
"""
import datetime
import json
import os
import re
import sys

LOG_DIR = os.environ.get("HARNESS_LOG_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "harness-logs")
CORRECTION_RE = re.compile(r"틀렸|틀린 거|아니잖|아니라니까|검증했어|확인했어\?|제대로 안|대충 보|빠뜨렸|빠졌잖|거짓|"
                           r"잘못 (알|말|했|봤)|또 틀|왜 .{0,20}(안 ?했|말했)")

REMINDER = (
    "[하네스 — 이번 턴]\n"
    "1) 주장 강도 = 증거 범위: '없다/전수/항상/불가/고장/원인은' 에는 검색 범위(파일 N개·경로)·측정 횟수·대조군을 붙이고, "
    "부족하면 '이 범위에서 확인됨/미확인' 으로 낮춘다. 서브에이전트·워크플로 결과는 원문 재확인 전까지 '미검증'.\n"
    "2) grep 매치를 '실행/호출된다' 고 말하기 전 liveness 확인(L1.5): 주석 // { } (* *) · {$IFDEF} · 선행 Exit · 정의/호출. "
    "Delphi 는 delphi-cms 스킬의 dlens 결과를 인용.\n"
    "3) 코드/설정 변경 전 L4.6 4-check(호출지점·외부 API·플랫폼 quirk·기존 동작 보존), 변경 후 V1·V3·V4, "
    "끝나면 Phase6 보고(TL;DR 3줄 + 변경파일/리스크/게이트/선택이유/미해결/롤백좌표).\n"
    "4) 불변: I1 추측 금지 · I2 비밀값 노출 금지 · I3 인코딩 보존 · I6 요청 범위 밖 금지."
)
CORRECTION = (
    "\n[하네스 — 사용자 정정 감지] 직전 답의 근거를 원문·도구로 다시 확인한다. 틀렸으면 무엇이 왜 틀렸는지 한 줄로 정정하고"
    " (변명·장황한 사과 없이) harness.v2.xml 의 해당 룰 violations 와 I1 에 기록한다."
)


def main():
    raw = sys.stdin.buffer.read()
    try:
        d = json.loads(raw.decode("utf-8", errors="replace")) if raw.strip() else {}
    except ValueError:
        d = {}
    prompt = d.get("prompt") or ""
    text = REMINDER
    m = CORRECTION_RE.search(prompt)
    if m:
        text += CORRECTION
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "corrections.jsonl"), "ab") as f:
                f.write((json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                                     "session": d.get("session_id"), "match": m.group(0),
                                     "prompt_head": prompt[:200]}, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception:
            pass
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": text}}, ensure_ascii=True))


if __name__ == "__main__":
    main()
