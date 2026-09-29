# -*- coding: utf-8 -*-
"""observe.py 합성 입력 시험 — 실제 로그와 섞이지 않게 임시 폴더에 쓴다."""
import json
import os
import subprocess
import sys
import tempfile
import time

HOOK = os.path.join(os.path.expanduser("~"), ".claude", "hooks", "observe.py")
tmp = tempfile.mkdtemp(prefix="obs_")
env = dict(os.environ, HARNESS_LOG_DIR=tmp)
env.pop("PYTHONIOENCODING", None)  # 훅 프로세스가 이 값을 못 받는 경우를 재현

CASES = [
    ("read_delphi", {"hook_event_name": "PostToolUse", "session_id": "t", "tool_name": "Read",
                     "tool_input": {"file_path": "D:\\K\\90. Program\\03. PT\\x\\uA.pas"},
                     "tool_response": {"type": "text", "file": {"content": "비밀값 sk-xxx"}}, "tool_use_id": "u1"}),
    ("bash_grep", {"hook_event_name": "PostToolUse", "session_id": "t", "tool_name": "Bash",
                   "tool_input": {"command": "grep -n showmessage 'D:/K/90. Program/uA.pas' TOKEN=abc"},
                   "tool_response": {"stdout": "12: showmessage", "stderr": ""}}),
    ("ps_build", {"hook_event_name": "PostToolUse", "session_id": "t", "tool_name": "PowerShell",
                  "tool_input": {"command": "dcc32 -LU foo x.dpr"}, "tool_response": "ok"}),
    ("stop", {"hook_event_name": "Stop", "session_id": "t", "stop_hook_active": False,
              "last_assistant_message": "원인은 -LU 누락입니다. 전수 확인했고 없습니다. uA.pas:12 참고, 미확인 1건",
              "background_tasks": [{"id": "1", "type": "workflow", "status": "running"}], "session_crons": []}),
    ("session", {"hook_event_name": "SessionStart", "session_id": "t", "source": "startup", "cwd": "C:\\x"}),
    ("instr", {"hook_event_name": "InstructionsLoaded", "session_id": "t", "file_path": "C:\\r.md",
               "memory_type": "User", "load_reason": "path_glob_match", "globs": ["D:/K/**"],
               "trigger_file_path": "D:\\K\\a.pas"}),
    ("prompt", {"hook_event_name": "UserPromptSubmit", "session_id": "t", "prompt": "그거 틀렸잖아 검증했어?"}),
    ("garbage", None),
]

fails = 0
for name, payload in CASES:
    data = b"{not json" if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, HOOK], input=data, capture_output=True, env=env)
    ms = (time.perf_counter() - t0) * 1000
    ok = p.returncode == 0
    fails += 0 if ok else 1
    print("%-12s exit=%d %5.0fms stdout=%r" % (name, p.returncode, ms, p.stdout.decode("utf-8", "replace")[:80]))

print("\n== 기록 내용 ==")
logs = [f for f in os.listdir(tmp) if f.startswith("events-")]
recs = [json.loads(l) for f in logs for l in open(os.path.join(tmp, f), encoding="utf-8")]
for r in recs:
    print(json.dumps(r, ensure_ascii=False)[:260])

blob = open(os.path.join(tmp, logs[0]), encoding="utf-8").read()
print("\n== 검사 ==")
checks = {
    "레코드 7개(garbage 제외)": len(recs) == 7,
    "비밀값·명령 원문 미기록": all(s not in blob for s in ("sk-xxx", "TOKEN=abc", "showmessage", "-LU foo")),
    "read_delphi: delphi=True": recs[0].get("delphi") is True and recs[0].get("target", "").endswith("uA.pas"),
    "bash_grep: search·delphi": recs[1].get("search") is True and recs[1].get("delphi") is True,
    "ps_build: build=True": recs[2].get("build") is True,
    "stop: strong=3 evidence=2 bg=workflow": recs[3]["msg"]["strong"] >= 3 and recs[3]["msg"]["evidence"] >= 2 and recs[3]["bg"][0]["type"] == "workflow",
    "session: missing_hooks=[]": recs[4].get("missing_hooks") == [],
    "instr: path_glob_match": recs[5].get("load_reason") == "path_glob_match",
    "prompt: correction=True, 본문 미기록": recs[6].get("correction") is True and "틀렸" not in blob,
    "garbage: 오류 로그 기록": os.path.exists(os.path.join(tmp, "observe-errors.log")),
    "한글 정상(UTF-8)": "path_glob_match" in blob and recs[4]["env"]["py"] is not None,
}
for k, v in checks.items():
    print("  %s  %s" % ("OK  " if v else "FAIL", k))
    fails += 0 if v else 1
print("\nenv seen by hook:", recs[4]["env"])
print("RESULT:", "PASS" if fails == 0 else "FAIL %d" % fails)
