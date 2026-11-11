# -*- coding: utf-8 -*-
"""Stop 훅 — 주장 게이트 (구조 개편 4단계, 2026-09-29).

최종 응답에서 '강한 주장'(부재·불가·전수·원인·정상 보증) 문장을 찾고, 같은 문장(±1)에 증거 표시
(파일:줄·N행·URL·검색 범위·측정 횟수·'미확인/미검증/추정')가 없으면 기록한다.

MODE (harness-logs/claim_gate_mode.txt 한 줄):
  observe(기본) — 기록만 한다. 응답을 막지 않는다.
  enforce      — 턴당 1회(stop_hook_active 로 확인) 되돌려 보강하게 한다.
재생 시험(오보 원문 재현율·정상 응답 오탐률) 기준을 통과할 때만 enforce 로 바꾼다.
"""
import datetime
import json
import os
import re
import sys

LOG_DIR = os.environ.get("HARNESS_LOG_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "harness-logs")

STRONG = re.compile(
    r"(없습니다|없다\b|없음|0건|전혀|전수|모든 경로|아무 데서도|유일한|한 겹|"
    r"불가능|넣을 수 없|할 수 없습니다|안 됩니다|안 된다|못 합니다|고장|응답 없|동작하지 않|"
    r"원인은|때문입니다|확정|항상|절대|"
    r"정상입니다|정상\b|이상 없|문제 없|옳았|취약|구멍|통과해버|느립니다|느림|줄어듭니다|줄일 수 있)")
EVIDENCE = re.compile(
    r"[\w\-]+\.(pas|dfm|dpr|py|md|xml|json|ts|js|jsonl|txt|dproj):\d+|\b\d+(~\d+)?\s*(행|줄)\b|\bL\d{2,}\b|https?://|"
    r"범위|파일\s*\d+\s*개|\d+\s*개\s*파일|\d+\s*건\s*중|중\s*\d+\s*건|전체\s*\d+|"
    r"\d+\s*회|재측정|실측|측정|n\s*=\s*\d+|대조|"
    r"미확인|미검증|추정|가설|가능성|보입니다|것 같|확인 못|확인하지 못|"
    r"\[(활성|블록주석|라인주석|조건부|도달불가)|dlens|원문")
CODE_FENCE = re.compile(r"```.*?```", re.S)
SPLIT = re.compile(r"\n+|(?<=[.!?。])\s+|(?<=다\.)\s*")


def sentences(text):
    text = CODE_FENCE.sub(" ", text or "")
    out = []
    for part in SPLIT.split(text):
        s = part.strip(" -*>|#\t")
        if len(s) >= 6 and not s.startswith(">"):
            out.append(s)
    return out


def judge(text):
    """증거 없는 강한 주장 문장 목록 (앞뒤 1문장까지 증거로 인정)."""
    ss = sentences(text)
    bad = []
    for i, s in enumerate(ss):
        if not STRONG.search(s):
            continue
        near = " ".join(ss[max(0, i - 1):i + 2])
        if not EVIDENCE.search(near):
            bad.append(s[:160])
    return bad


def mode():
    try:
        return open(os.path.join(LOG_DIR, "claim_gate_mode.txt"), encoding="utf-8").read().strip() or "observe"
    except OSError:
        return "observe"


def main():
    d = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    msg = d.get("last_assistant_message") or ""
    bad = judge(msg)
    m = mode()
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(os.path.join(LOG_DIR, "events-%s.jsonl" % datetime.date.today().strftime("%Y%m")), "ab") as f:
        f.write((json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "ev": "ClaimGate",
                             "session": d.get("session_id"), "agent_id": d.get("agent_id"), "mode": m,
                             "stop_hook_active": d.get("stop_hook_active"), "flagged": len(bad)},
                            ensure_ascii=False) + "\n").encode("utf-8"))
    if bad and m == "enforce" and not d.get("stop_hook_active"):
        reason = ("[주장 게이트] 아래 문장은 강한 주장인데 증거 표시(파일:줄·검색 범위·측정 횟수·'미확인')가 없다. "
                  "증거를 붙이거나 '이 범위에서 확인됨/미확인' 으로 강도를 낮춰 다시 써라:\n- " + "\n- ".join(bad[:4]))
        sys.stdout.write(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "claim-errors.log"), "a", encoding="utf-8") as f:
                f.write("%s %r\n" % (datetime.datetime.now().isoformat(timespec="seconds"), e))
        except Exception:
            pass
    sys.exit(0)
