# -*- coding: utf-8 -*-
"""관찰 전용 훅 (구조 개편 1단계, 2026-09-29).

여러 훅 이벤트에서 공통으로 불린다. 모델에게 아무것도 주입하지 않고 차단도 하지 않는다.
~/.claude/harness-logs/events-YYYYMM.jsonl 에 한 줄씩 남긴다.

기록하는 것 : 이벤트명, 도구명, 대상 경로, 크기·건수, Delphi/빌드/검색 여부 플래그
기록하지 않는 것 : 명령 원문, 파일 내용, 대화 본문 (I2 — 비밀값이 섞일 수 있다)

예외는 전부 삼키고 exit 0 — 관찰 훅이 작업을 막으면 안 된다.
대신 오류는 harness-logs/observe-errors.log 에 남겨 조용히 꺼지는 것을 감지한다(I7).
"""
import datetime
import json
import locale
import os
import re
import sys
import traceback

LOG_DIR = os.environ.get("HARNESS_LOG_DIR") or os.path.join(os.path.expanduser("~"), ".claude", "harness-logs")

DELPHI_RE = re.compile(r"\.(pas|dfm|dpr|dproj|inc)\b|(^|[\\/\"'\s])[dD]:[\\/]+K([\\/]|\b)", re.I)
BUILD_RE = re.compile(r"\b(dcc32|dcc64|msbuild|rsvars)\b", re.I)
SEARCH_RE = re.compile(r"\b(grep|rg|findstr|Select-String)\b", re.I)

# 4단계(주장 게이트) 기준선용 — 문장은 저장하지 않고 건수만 센다
STRONG_RE = re.compile(r"없습니다|없다|0건|전수|항상|모든 경로|불가능|불가|고장|원인은|확정|도달 ?불가")
EVIDENCE_RE = re.compile(r"\w\.(pas|dfm|py|md|xml|json|ts|js):\d+|:\d+행|\d+행|https?://|미확인|미검증|추정")
CORRECTION_RE = re.compile(r"틀렸|아니잖|아니라니까|검증했어|제대로 안|빠뜨렸|거짓|잘못 ?알|다시 확인")


def now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def write(rec):
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, "events-%s.jsonl" % datetime.date.today().strftime("%Y%m"))
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0))
    try:
        os.write(fd, line)
    finally:
        os.close(fd)


def target_of(tool, ti):
    """도구 입력에서 대상 경로만 뽑는다. 명령 원문은 돌려주지 않는다."""
    for k in ("file_path", "path", "notebook_path"):
        if isinstance(ti.get(k), str):
            return ti[k]
    if tool == "Glob" and isinstance(ti.get("pattern"), str):
        return ti["pattern"]
    return None


def tool_record(d):
    tool = d.get("tool_name", "")
    ti = d.get("tool_input") or {}
    tr = d.get("tool_response")
    rec = {"tool": tool, "target": target_of(tool, ti)}
    blob = json.dumps(ti, ensure_ascii=False)
    rec["delphi"] = bool(DELPHI_RE.search(blob))
    if tool in ("Bash", "PowerShell"):
        cmd = ti.get("command", "") or ""
        rec["build"] = bool(BUILD_RE.search(cmd))
        rec["search"] = bool(SEARCH_RE.search(cmd))
    if tool == "Grep":
        rec["search"] = True
        rec["glob"] = ti.get("glob")
    rec["resp_type"] = type(tr).__name__
    rec["resp_keys"] = sorted(tr.keys())[:12] if isinstance(tr, dict) else None
    rec["resp_len"] = len(json.dumps(tr, ensure_ascii=False)) if tr is not None else 0
    for k in ("tool_use_id", "duration_ms"):
        if k in d:
            rec[k] = d[k]
    return rec


def text_counts(msg):
    msg = msg or ""
    return {"len": len(msg), "strong": len(STRONG_RE.findall(msg)),
            "evidence": len(EVIDENCE_RE.findall(msg))}


def self_test():
    """settings.json 에 등록된 훅 스크립트가 실제로 있는지 본다. 없으면 목록을 돌려준다."""
    missing = []
    try:
        p = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
        with open(p, "r", encoding="utf-8") as f:
            s = json.load(f)
        for groups in (s.get("hooks") or {}).values():
            for g in groups:
                for h in g.get("hooks", []):
                    for a in h.get("args", []) or []:
                        if a.lower().endswith(".py") and not os.path.exists(a):
                            missing.append(a)
    except Exception as e:  # settings.json 자체가 깨졌으면 그것도 알린다
        missing.append("settings.json 읽기 실패: %s" % e)
    return missing


def main():
    raw = sys.stdin.buffer.read()
    d = json.loads(raw.decode("utf-8", errors="replace")) if raw.strip() else {}
    ev = d.get("hook_event_name", "?")
    rec = {"ts": now(), "ev": ev, "session": d.get("session_id"),
           "agent_id": d.get("agent_id"), "agent_type": d.get("agent_type")}

    out = None
    if ev == "SessionStart":
        rec["source"] = d.get("source")
        rec["cwd"] = d.get("cwd")
        rec["env"] = {"stdin_enc": getattr(sys.stdin, "encoding", None),
                      "preferred": locale.getpreferredencoding(False),
                      "PYTHONIOENCODING": os.environ.get("PYTHONIOENCODING"),
                      "utf8_mode": sys.flags.utf8_mode, "py": sys.version.split()[0]}
        missing = self_test()
        rec["missing_hooks"] = missing
        if missing:  # 조용한 fail-open 방지: 사용자에게만 보이는 경고
            out = {"systemMessage": "[하네스] 등록된 훅 스크립트가 없습니다: " + ", ".join(missing)}
    elif ev == "InstructionsLoaded":
        for k in ("file_path", "memory_type", "load_reason", "globs", "trigger_file_path", "parent_file_path"):
            if k in d:
                rec[k] = d[k]
    elif ev in ("PostToolUse", "PostToolUseFailure"):
        rec.update(tool_record(d))
    elif ev in ("Stop", "SubagentStop"):
        rec["stop_hook_active"] = d.get("stop_hook_active")
        rec["msg"] = text_counts(d.get("last_assistant_message"))
        bt = d.get("background_tasks")
        rec["bg"] = [{"type": t.get("type"), "status": t.get("status")} for t in bt] if isinstance(bt, list) else None
        rec["crons"] = len(d.get("session_crons") or []) if d.get("session_crons") is not None else None
    elif ev == "UserPromptSubmit":
        p = d.get("prompt") or ""
        rec["prompt_len"] = len(p)
        rec["correction"] = bool(CORRECTION_RE.search(p))

    write(rec)
    if out:
        sys.stdout.write(json.dumps(out, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "observe-errors.log"), "a", encoding="utf-8") as f:
                f.write(now() + "\n" + traceback.format_exc() + "\n")
        except Exception:
            pass
    sys.exit(0)
