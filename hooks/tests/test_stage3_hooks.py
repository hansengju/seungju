# -*- coding: utf-8 -*-
"""3단계 훅 합성 시험 — 실제 로그와 섞이지 않게 임시 폴더를 쓴다. 회사 소스는 복사하지 않는다(합성 파일)."""
import json
import os
import subprocess
import sys
import tempfile
import time

H = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
tmp = tempfile.mkdtemp(prefix="st3_")
env = dict(os.environ, HARNESS_LOG_DIR=os.path.join(tmp, "logs"))
env.pop("PYTHONIOENCODING", None)  # 실제 훅 환경처럼 stdin cp949

cp = os.path.join(tmp, "uCp.pas")
open(cp, "wb").write("unit uCp;\r\n{ 한글 주석 }\r\nimplementation\r\nprocedure A;\r\nbegin\r\n  { ShowMessage('x');\r\n  }\r\n  Live;\r\nend;\r\nend.\r\n".encode("cp949"))
u8 = os.path.join(tmp, "uU8.pas")
open(u8, "wb").write("unit uU8;\r\n// 한글\r\nend.\r\n".encode("utf-8"))
asc = os.path.join(tmp, "uAsc.dfm")
open(asc, "wb").write(b"object F: TF\r\nend\r\n")


def run(script, payload):
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, os.path.join(H, script)], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, env=env)
    ms = (time.perf_counter() - t0) * 1000
    out = p.stdout.decode("utf-8", "replace").strip()
    return p.returncode, (json.loads(out) if out else None), ms


cases = []


def check(name, got, want):
    cases.append((name, got == want, got, want))


# K6 가드
rc, o, ms = run("k6_guard.py", {"tool_name": "Edit", "tool_input": {"file_path": cp}, "session_id": "t"})
check("K6: cp949 .pas Edit → deny", (o or {}).get("hookSpecificOutput", {}).get("permissionDecision"), "deny")
rc, o, _ = run("k6_guard.py", {"tool_name": "Write", "tool_input": {"file_path": u8}, "session_id": "t"})
check("K6: UTF-8 .pas → 통과", o, None)
rc, o, _ = run("k6_guard.py", {"tool_name": "Edit", "tool_input": {"file_path": asc}, "session_id": "t"})
check("K6: ASCII .dfm → 통과", o, None)
rc, o, _ = run("k6_guard.py", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(tmp, "new.pas")}, "session_id": "t"})
check("K6: 새 파일 → 통과", o, None)
rc, o, _ = run("k6_guard.py", {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(tmp, "a.py")}, "session_id": "t"})
check("K6: 비Delphi → 통과", o, None)
rc, o, _ = run("k6_guard.py", {"garbage": True})
check("K6: 이상 입력 → exit 0, 출력 없음", (rc, o), (0, None))

# assist
ctx = lambda o: ((o or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")  # noqa: E731
grep_out = "%s:6:  { ShowMessage('x');\n%s:8:  Live;" % (cp, cp)
rc, o, ms_g = run("assist.py", {"tool_name": "Grep", "tool_input": {"pattern": "ShowMessage|Live", "path": tmp},
                                "tool_response": {"content": grep_out, "mode": "content"}, "session_id": "s1", "cwd": tmp})
c = ctx(o)
check("assist: Grep 결과에 블록주석 라벨", "uCp.pas:6 → [블록주석 { }" in c, True)
check("assist: Grep 결과에 활성 라벨", "uCp.pas:8 → [활성" in c, True)
check("assist: 스킬 미로드 → 로드 안내 1회", "delphi-cms 스킬을 먼저 로드" in c, True)
rc, o, _ = run("assist.py", {"tool_name": "Grep", "tool_input": {"pattern": "Live", "path": tmp},
                             "tool_response": {"content": grep_out}, "session_id": "s1", "cwd": tmp})
check("assist: 같은 세션 두 번째 → 안내 반복 없음", "delphi-cms 스킬을 먼저 로드" in ctx(o), False)
run("assist.py", {"tool_name": "Skill", "tool_input": {"skill": "delphi-cms"}, "session_id": "s2"})
rc, o, _ = run("assist.py", {"tool_name": "Read", "tool_input": {"file_path": cp}, "tool_response": {"type": "text"}, "session_id": "s2"})
check("assist: 스킬 로드된 세션 → 안내 없음", o, None)
rc, o, _ = run("assist.py", {"tool_name": "Bash", "tool_input": {"command": "ls /tmp"}, "tool_response": {"stdout": "a\nb"}, "session_id": "s3"})
check("assist: 비Delphi Bash → 출력 없음", o, None)
rc, o, _ = run("assist.py", {"tool_name": "PowerShell", "tool_input": {"command": "dcc32 -B x.dpr"},
                             "tool_response": {"stdout": "Fatal"}, "session_id": "s2"})
check("assist: 빌드 명령 → 빌드 절차 안내", "-LU" in ctx(o), True)
rc, o, _ = run("assist.py", {"tool_name": "Agent", "tool_input": {"prompt": "x"}, "tool_response": {"content": "y"}, "session_id": "s4"})
check("assist: Agent 결과 → 미검증 표시", "에이전트 주장·미검증" in ctx(o), True)
rc, o, _ = run("assist.py", {"tool_name": "Bash", "tool_input": {"command": "python dlens.py grep x D:/K"},
                             "tool_response": {"stdout": "[범위] 파일 1개\nuCp.pas:6  [블록주석]"}, "session_id": "s2"})
check("assist: dlens 출력에는 중복 라벨 안 붙임", "dlens 자동 판정" in ctx(o), False)
rc, o, _ = run("assist.py", {"x": 1})
check("assist: 이상 입력 → exit 0", rc, 0)

# reminder
rc, o, ms_r = run("harness_reminder.py", {"prompt": "다음 작업 해줘", "session_id": "r"})
t = ctx(o)
check("reminder: Rule ID 머리줄 지시 없음", "Rule ID" in t, False)
check("reminder: L0.3 줄 지시 없음", "L0.3" in t, False)
check("reminder: 주장 강도·L1.5 포함", "주장 강도" in t and "L1.5" in t, True)
check("reminder: 평소엔 정정 문구 없음", "정정 감지" in t, False)
rc, o, _ = run("harness_reminder.py", {"prompt": "지금 나한테 거짓을 말하고 있잖아 검증했어?", "session_id": "r"})
check("reminder: 정정 발화 → 재확인 지시", "정정 감지" in ctx(o), True)
logf = os.path.join(tmp, "logs", "corrections.jsonl")
check("reminder: 정정 기록 1건", os.path.exists(logf) and len(open(logf, encoding="utf-8").read().splitlines()), 1)
check("reminder: 출력은 ASCII JSON", all(ord(ch) < 128 for ch in json.dumps(o, ensure_ascii=True)), True)

fails = 0
for name, ok, got, want in cases:
    print("%s  %s%s" % ("OK  " if ok else "FAIL", name, "" if ok else "   got=%r want=%r" % (str(got)[:200], want)))
    fails += 0 if ok else 1
print("\n지연: K6 %.0fms · assist(Grep 판정) %.0fms · reminder %.0fms" % (ms, ms_g, ms_r))
print("%d/%d 통과 → %s" % (len(cases) - fails, len(cases), "PASS" if not fails else "FAIL %d" % fails))
