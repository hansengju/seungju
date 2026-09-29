# -*- coding: utf-8 -*-
"""UserPromptSubmit 훅: 매 프롬프트마다 하네스(Strategic Code Guardian) 적용을 강제 주입.

ensure_ascii=True 로 ASCII-only JSON 출력 → Windows cp949 파이프에서도 한글 안 깨짐.
"""
import json

REMINDER = (
    "[하네스 v2.1 강제 — 이번 턴에 반드시 적용]\n"
    "1) 응답 첫 줄에 적용 Rule ID 명시 (예: 적용 규칙: L0.1, L4.6, I2)\n"
    "2) 명시한 룰을 실제로 follow — 응답 끝에 L0.3 자기점검 1줄\n"
    "3) 코드/설정 변경 직전 L4.6 4-check: (a)호출지점 grep (b)외부 API 시그니처 "
    "(c)플랫폼 quirk(Windows/cp949/PS5.1) (d)기존 동작 보존 증명\n"
    "4) 변경 후 V게이트 통과: V1 구문 · V3 타입 · V4 테스트(신규 실패 0)\n"
    "5) 작업 종료 시 Phase6 보고: TL;DR 3줄 + (변경파일/리스크/게이트/선택이유/미해결/롤백좌표)\n"
    "6) 불변: 추측금지(I1) · 비밀값 노출금지(I2) · 인코딩 보존(I3) · 요청 범위 밖 금지(I6)"
)

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": REMINDER,
    }
}, ensure_ascii=True))
