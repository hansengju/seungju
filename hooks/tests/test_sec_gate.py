# -*- coding: utf-8 -*-
"""sec_gate(보안 S1) · assist 의존성 안내(보안 S2) 합성 시험 (2026-11-12).
임시 저장소·임시 로그 폴더만 쓴다. 가짜 비밀값은 실행 때 무작위로 만든다 —
이 파일 자체에는 비밀값 모양 문자열이 없다(이 파일을 커밋할 때 게이트에 걸리지 않게)."""
import json
import os
import secrets
import string
import subprocess
import sys
import tempfile
import time

H = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
tmp = tempfile.mkdtemp(prefix="secgate_")
env = dict(os.environ, HARNESS_LOG_DIR=os.path.join(tmp, "logs"))
env.pop("PYTHONIOENCODING", None)  # 실제 훅 환경처럼
env.pop("SEC_GATE_GITLEAKS", None)


def git(*a, cwd):
    return subprocess.run(["git"] + list(a), cwd=cwd, capture_output=True)


def fake_token():
    al = string.ascii_letters + string.digits
    return "gh" + "p_" + "".join(secrets.choice(al) for _ in range(36))


def run(script, payload, extra_env=None):
    e = dict(env, **(extra_env or {}))
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, os.path.join(H, script)], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                       capture_output=True, env=e)
    ms = (time.perf_counter() - t0) * 1000
    o = p.stdout.decode("utf-8", "replace").strip()
    return p.returncode, (json.loads(o) if o else None), ms


def dec(o):
    return ((o or {}).get("hookSpecificOutput") or {}).get("permissionDecision")


def reason(o):
    return ((o or {}).get("hookSpecificOutput") or {}).get("permissionDecisionReason", "")


cases = []


def check(name, got, want):
    cases.append((name, got == want, got, want))


# 저장소 준비: bare 원격 + 작업 저장소 + 저장소 밖 폴더
remote = os.path.join(tmp, "remote.git")
repo = os.path.join(tmp, "repo")
other = os.path.join(tmp, "elsewhere")
subprocess.run(["git", "init", "-q", "--bare", remote], capture_output=True)
os.makedirs(repo)
os.makedirs(other)
git("init", "-q", "-b", "main", cwd=repo)
for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"), ("core.autocrlf", "false")):
    git("config", k, v, cwd=repo)
git("remote", "add", "origin", remote, cwd=repo)
open(os.path.join(repo, "app.py"), "w").write("print('hello')\n")
git("add", "app.py", cwd=repo)
git("commit", "-q", "-m", "init", cwd=repo)
git("push", "-q", "-u", "origin", "main", cwd=repo)


def P(cmd, cwd=repo, tool="Bash"):
    return {"tool_name": tool, "tool_input": {"command": cmd}, "cwd": cwd, "session_id": "sg"}


# 1) 깨끗한 커밋
open(os.path.join(repo, "app.py"), "a").write("x = 1\n")
git("add", "app.py", cwd=repo)
rc, o, ms_clean = run("sec_gate.py", P('git commit -m "clean"'))
check("S1: 깨끗한 스테이징 → 통과(출력 없음)", o, None)
git("commit", "-q", "-m", "clean", cwd=repo)

# 2) 비밀값을 새 파일로 스테이징
tok = fake_token()
open(os.path.join(repo, "settings_local.py"), "w").write('TOKEN = "%s"\n' % tok)
git("add", "settings_local.py", cwd=repo)
rc, o, ms_leak = run("sec_gate.py", P('git commit -m "add config"'))
check("S1: 비밀값 스테이징 → deny", dec(o), "deny")
check("S1: 사유에 파일:줄", "settings_local.py:1" in reason(o), True)
check("S1: 사유에 값 원문 없음", tok in reason(o), False)

# 3) git -C <repo> (현재 폴더는 저장소 밖)
rc, o, _ = run("sec_gate.py", P('git -C "%s" commit -m x' % repo, cwd=other))
check("S1: git -C <repo> commit → deny", dec(o), "deny")

# 4) cd 후 커밋 (PowerShell 구분자 ;)
rc, o, _ = run("sec_gate.py", P('cd "%s"; git commit -m x' % repo, cwd=other, tool="PowerShell"))
check("S1: cd <repo>; git commit → deny", dec(o), "deny")

# 5) git 아닌 명령 / 6) 저장소 밖
rc, o, _ = run("sec_gate.py", P("dir"))
check("S1: git 아닌 명령 → 출력 없음", o, None)
rc, o, _ = run("sec_gate.py", P("git commit -m x", cwd=other))
check("S1: 저장소 밖 → 출력 없음", o, None)

# 스테이징을 비우고, 추적 중인 파일에 미스테이징 비밀값
git("reset", "-q", cwd=repo)
os.remove(os.path.join(repo, "settings_local.py"))
tok2 = fake_token()
open(os.path.join(repo, "app.py"), "a").write('KEY = "%s"\n' % tok2)

# 7) 일반 commit — 미스테이징 변경은 커밋되지 않으므로 막지 않는다
rc, o, _ = run("sec_gate.py", P('git commit -m "nothing staged"'))
check("S1: 미스테이징 비밀값 + 일반 commit → 통과(오탐 방지)", o, None)
# 8) commit -am / 9) add && commit
rc, o, _ = run("sec_gate.py", P('git commit -am "all"'))
check("S1: commit -am → 미스테이징도 검사 → deny", dec(o), "deny")
rc, o, _ = run("sec_gate.py", P("git add -A && git commit -m x"))
check("S1: git add && git commit → deny", dec(o), "deny")

# 10) push — 시험 준비로 직접 커밋해 둔 뒤(이 시험은 훅 단독 실행) push 판정
git("commit", "-q", "-am", "leak", cwd=repo)
rc, o, ms_push = run("sec_gate.py", P("git push origin main"))
check("S1: 원격에 없는 커밋에 비밀값 → push deny", dec(o), "deny")
check("S1: push 사유에 커밋 해시", " @" in reason(o), True)
# 11) 원격 브랜치 삭제 push → 보낼 커밋 없음
rc, o, _ = run("sec_gate.py", P("git push origin :old-branch"))
check("S1: 원격 삭제 push → 출력 없음", o, None)
# 12) gitleaks 없음
rc, o, _ = run("sec_gate.py", P("git push"), {"SEC_GATE_GITLEAKS": os.path.join(tmp, "none.exe")})
check("S1: gitleaks 없음 → 경고(systemMessage)", "gitleaks" in ((o or {}).get("systemMessage") or ""), True)
check("S1: gitleaks 없음 → 차단 안 함", dec(o), None)
# 13) 이상 입력
rc, o, _ = run("sec_gate.py", {"garbage": True})
check("S1: 이상 입력 → exit 0, 출력 없음", (rc, o), (0, None))
# 14) 로그에 값이 남지 않음
logdir = os.path.join(tmp, "logs")
logtxt = "".join(open(os.path.join(logdir, f), encoding="utf-8").read() for f in os.listdir(logdir) if f.startswith("events-"))
check("S1: 이벤트 로그에 값 원문 없음", (tok in logtxt) or (tok2 in logtxt), False)
check("S1: 이벤트 로그에 deny 기록", '"decision": "deny"' in logtxt, True)

# assist — 보안 S2 의존성 안내
ctx = lambda o: ((o or {}).get("hookSpecificOutput") or {}).get("additionalContext", "")  # noqa: E731
pj = os.path.join(tmp, "web", "package.json")
rc, o, ms_a = run("assist.py", {"tool_name": "Edit", "tool_input": {"file_path": pj}, "session_id": "a1"})
check("S2: package.json Edit → osv-scanner 안내", "osv-scanner scan source" in ctx(o), True)
rc, o, _ = run("assist.py", {"tool_name": "Write", "tool_input": {"file_path": pj}, "session_id": "a1"})
check("S2: 같은 폴더 두 번째 → 반복 없음", o, None)
rc, o, _ = run("assist.py", {"tool_name": "Write", "tool_input": {"file_path": os.path.join(tmp, "py", "requirements-dev.txt")},
                             "session_id": "a1"})
check("S2: 다른 폴더 requirements-dev.txt → 안내", "osv-scanner" in ctx(o), True)
rc, o, _ = run("assist.py", {"tool_name": "Edit", "tool_input": {"file_path": os.path.join(tmp, "main.py")}, "session_id": "a1"})
check("S2: 일반 파일 Edit → 출력 없음", o, None)
rc, o, _ = run("assist.py", {"tool_name": "Edit", "tool_input": {"file_path": "D:\\K\\x\\uMain.pas"}, "session_id": "a2"})
check("S2: Delphi 파일 Edit → 출력 없음(기존 동작 보존)", o, None)

fails = 0
for name, ok, got, want in cases:
    print("%s  %s%s" % ("OK  " if ok else "FAIL", name, "" if ok else "   got=%r want=%r" % (str(got)[:300], want)))
    fails += 0 if ok else 1
print("\n지연: 깨끗한 commit %.0fms · 비밀값 commit %.0fms · push %.0fms · assist %.0fms" % (ms_clean, ms_leak, ms_push, ms_a))
print("%d/%d 통과 → %s" % (len(cases) - fails, len(cases), "PASS" if not fails else "FAIL %d" % fails))
