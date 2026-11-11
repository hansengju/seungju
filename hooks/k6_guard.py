# -*- coding: utf-8 -*-
"""PreToolUse(Edit|Write|NotebookEdit) — K6 기계 차단 (구조 개편 3단계, 2026-09-29).

cp949(= UTF-8 로 풀리지 않는) Delphi 파일(.pas .dfm .dpr .inc .dpk)을 Edit/Write 도구로 고치려 하면 막는다.
Edit/Write 도구는 UTF-8 로 다시 써서 한글이 깨진다(사고 I-2026-05-08-1). ASCII·UTF-8 파일과 새 파일은 통과.
훅이 죽으면 차단하지 않고 진행한다(fail-open) — 오류는 harness-logs/k6-errors.log 에 남긴다.
"""
import datetime
import json
import os
import sys

EXT = (".pas", ".dfm", ".dpr", ".inc", ".dpk")
LOG_DIR = os.environ.get("HARNESS_LOG_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "harness-logs")
REASON = ("[K6] cp949 Delphi 파일은 Edit/Write 도구로 고치지 않는다(UTF-8 로 다시 써져 한글이 깨진다). "
          "delphi-cms 스킬 '편집 절차': Python 으로 raw=open(p,'rb').read() → raw.decode('cp949').split('\\r\\n') "
          "→ 앵커 줄 검증 → 아래에서 위로 편집 → '\\r\\n'.join(...).encode('cp949') 저장 → 왕복·CRLF·BOM 확인. "
          "편집 전 <파일>.bak.YYYYMMDD 백업.")


def is_cp949(path):
    raw = open(path, "rb").read()
    if raw[:3] == b"\xef\xbb\xbf" or raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return False
    try:
        raw.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def main():
    d = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    ti = d.get("tool_input") or {}
    p = ti.get("file_path") or ti.get("notebook_path") or ""
    if not p.lower().endswith(EXT) or not os.path.isfile(p):
        return
    if is_cp949(p):
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": REASON}}, ensure_ascii=True))
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, "events-%s.jsonl" % datetime.date.today().strftime("%Y%m")), "ab") as f:
            f.write((json.dumps({"ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                                 "ev": "K6Deny", "session": d.get("session_id"), "agent_id": d.get("agent_id"),
                                 "tool": d.get("tool_name"), "target": p}, ensure_ascii=False) + "\n").encode("utf-8"))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "k6-errors.log"), "a", encoding="utf-8") as f:
                f.write("%s %r\n" % (datetime.datetime.now().isoformat(timespec="seconds"), e))
        except Exception:
            pass
    sys.exit(0)
