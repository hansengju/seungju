# -*- coding: utf-8 -*-
"""PostToolUse(Grep|Read|Bash|PowerShell|Skill|Agent) — 위험한 순간에만 도구 결과 옆에 한두 줄 붙인다
(구조 개편 3단계, 2026-09-29). 차단하지 않는다.

  1) Delphi 검색 결과(파일:줄) → 줄마다 dlens 판정 라벨 (주석 { } (* *) · 조건부 · 도달불가 추정 …)
  2) 세션에서 D:\\K Delphi 를 처음 건드렸는데 delphi-cms 스킬이 안 불렸으면 → 한 번만 로드 안내
  3) 서브에이전트(Agent) 결과 → "미검증 — 원문 재확인 전 인용 금지"
  4) dcc32/msbuild 빌드 명령 → 빌드 오류 절차 안내

Delphi 와 무관한 호출은 입력만 읽고 바로 끝난다. 훅이 죽으면 아무것도 붙이지 않는다(fail-open),
오류는 harness-logs/assist-errors.log 에 남긴다.
"""
import datetime
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
LOG_DIR = os.environ.get("HARNESS_LOG_DIR") or os.path.join(HOME, ".claude", "harness-logs")
SKILL_SCRIPTS = os.path.join(HOME, ".claude", "skills", "delphi-cms", "scripts")
DELPHI_RE = re.compile(r"\.(pas|dfm|dpr|dproj|inc|dpk)\b|(^|[\\/\"'\s=])[dD]:[\\/]+K([\\/]|\b)", re.I)
BUILD_RE = re.compile(r"\b(dcc32|dcc64|msbuild)\b", re.I)
HIT_RE = re.compile(r"^(?P<p>(?:[A-Za-z]:)?[^:\r\n]*?\.(?:pas|dpr|inc|dpk)):(?P<n>\d+)[:\-]", re.I | re.M)
MAX_FILES, MAX_LINES, MAX_CHARS = 6, 40, 3500


def state_path(session):
    # 서브에이전트도 부모와 같은 session_id 로 들어온다 → agent_id 까지 붙여 따로 센다
    return os.path.join(LOG_DIR, "state", "%s.json" % re.sub(r"[^\w-]", "_", session or "none"))


def load_state(session):
    try:
        return json.load(open(state_path(session), encoding="utf-8"))
    except Exception:
        return {}


def save_state(session, st):
    os.makedirs(os.path.dirname(state_path(session)), exist_ok=True)
    json.dump(st, open(state_path(session), "w", encoding="utf-8"))


def response_text(tr):
    if isinstance(tr, str):
        return tr
    if isinstance(tr, dict):
        parts = [tr.get(k) for k in ("content", "stdout", "output")]
        return "\n".join(p for p in parts if isinstance(p, str))
    return ""


def annotate(text, base_dir, single_file=None):
    """출력 속 '파일:줄' 을 dlens 로 판정해 짧은 라벨 목록을 만든다.
    single_file: Grep 에 파일 하나를 줬을 때 — 출력이 '줄:내용' 으로만 나온다."""
    if "[범위]" in text:  # 이미 dlens 출력 — 두 번 붙이지 않는다
        return None
    hits = []
    if single_file:
        hits = [(os.path.normpath(single_file), int(m.group(1))) for m in re.finditer(r"^(\d+)[:\-]", text, re.M)]
    for m in HIT_RE.finditer(text):
        p = m.group("p").strip()
        if not os.path.isabs(p) and base_dir:
            p = os.path.join(base_dir, p)
        hits.append((os.path.normpath(p), int(m.group("n"))))
    if not hits:
        return None
    sys.path.insert(0, SKILL_SCRIPTS)
    import dlens  # noqa: E402  (필요할 때만 불러온다)
    out, cache, files = [], {}, []
    for p, n in hits:
        if len(out) >= MAX_LINES:
            break
        if p not in cache:
            if len(files) >= MAX_FILES or not os.path.isfile(p):
                continue
            try:
                cache[p] = dlens.Src(p)
            except Exception:
                continue
            files.append(p)
        lab, det = cache[p].classify(n)
        out.append("  %s:%d → [%s%s]" % (os.path.basename(p), n, lab, (" · " + det) if det else ""))
    if not out:
        return None
    body = "\n".join(out)
    if len(body) > MAX_CHARS:
        body = body[:MAX_CHARS] + "\n  …(생략)"
    more = len(hits) - len(out)
    return ("[dlens 자동 판정 — 이 라벨을 근거로 인용하라. '활성' 이 아닌 줄을 '실행된다' 고 말하지 않는다]\n" + body
            + ("\n  (나머지 %d건은 판정 생략 — 필요하면 dlens grep 으로)" % more if more > 0 else ""))


def main():
    d = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace") or "{}")
    tool = d.get("tool_name", "")
    ti = d.get("tool_input") or {}
    tr = d.get("tool_response")
    session = "%s-%s" % (d.get("session_id"), d.get("agent_id") or "main")
    notes = []

    if tool == "Skill":
        if str(ti.get("skill", "")).split(":")[-1] == "delphi-cms":
            st = load_state(session)
            st["skill"] = True
            save_state(session, st)
        return
    if tool == "Agent":
        notes.append("[하네스] 위 결과는 서브에이전트 출력이다 — 사용자에게 전하기 전에 핵심 주장(파일:줄·수치·가능/불가·원인)을 "
                     "원문이나 도구로 다시 확인하고, 확인 못 한 것은 '(에이전트 주장·미검증)' 으로 적는다.")
    else:
        blob = json.dumps(ti, ensure_ascii=False)
        text = response_text(tr)
        delphi = bool(DELPHI_RE.search(blob)) or bool(HIT_RE.search(text[:20000]))
        if not delphi:
            return
        st = load_state(session)
        if not st.get("skill") and not st.get("nudged"):
            notes.append("[하네스] D:\\K Delphi 작업 감지 — delphi-cms 스킬을 먼저 로드하라(Skill 도구). "
                         "판정은 dlens(live/nest/callers/dfm)로 하고 결과 라벨을 인용한다.")
            st["nudged"] = True
            save_state(session, st)
        if tool in ("Bash", "PowerShell") and BUILD_RE.search(ti.get("command", "") or ""):
            notes.append("[하네스] 빌드 오류 원인은 로그 전문에서 첫 Fatal/Error 줄과 dcc32 -LU 목록을 대조한 뒤에 말한다 "
                         "(delphi-cms references/build.md).")
        if tool in ("Grep", "Bash", "PowerShell"):
            gp = ti.get("path") if tool == "Grep" else None
            single = gp if gp and os.path.isfile(gp) and re.search(r"\.(pas|dpr|inc|dpk)$", gp, re.I) else None
            base = gp if gp and os.path.isdir(gp) else (os.path.dirname(gp) if gp else d.get("cwd"))
            a = annotate(text, base, single)
            if a:
                notes.append(a)
    if notes:
        sys.stdout.write(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                                            "additionalContext": "\n".join(notes)}}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            with open(os.path.join(LOG_DIR, "assist-errors.log"), "a", encoding="utf-8") as f:
                f.write("%s %r\n" % (datetime.datetime.now().isoformat(timespec="seconds"), e))
        except Exception:
            pass
    sys.exit(0)
