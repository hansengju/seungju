# -*- coding: utf-8 -*-
"""하네스 효과 측정 요약 — 훅이 남긴 기록(harness-logs)과 harness.v2.xml 위반 기록을 합쳐 본다 (읽기 전용).

  python ~/.claude/tools/harness_report.py              전체 기간
  python ~/.claude/tools/harness_report.py --since 2026-10-01

보는 것 (구조 개편 7단계 측정 지표):
  - 사용자 정정 발화 건수 (corrections.jsonl) — 줄어야 한다
  - K6 차단 · Delphi 도구 호출 · 스킬 로드 안내 효과
  - 주장 게이트(기록 전용): 응답당 증거 없는 강한 주장 건수
  - paths 실험: InstructionsLoaded 의 path_glob_match 발생 여부
  - 훅 오류 로그 크기 (조용한 fail-open 감지)
  - harness.v2.xml violations 상위
"""
import argparse
import collections
import glob
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HOME = os.path.join(os.path.expanduser("~"), ".claude")
LOG = os.path.join(HOME, "harness-logs")


def load(path, since):
    out = []
    for p in sorted(glob.glob(path)):
        for line in open(p, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if since and (r.get("ts") or "")[:10] < since:
                continue
            out.append(r)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", help="YYYY-MM-DD 이후만")
    a = ap.parse_args()
    ev = load(os.path.join(LOG, "events-*.jsonl"), a.since)
    corr = load(os.path.join(LOG, "corrections.jsonl"), a.since)
    sessions = {r.get("session") for r in ev if r.get("session")}
    print("[범위] harness-logs 이벤트 %d건 · 세션 %d개 · 기간 %s ~ %s" % (
        len(ev), len(sessions), min((r["ts"][:10] for r in ev if r.get("ts")), default="-"),
        max((r["ts"][:10] for r in ev if r.get("ts")), default="-")))
    c = collections.Counter(r.get("ev") for r in ev)
    print("이벤트:", dict(c.most_common()))

    prompts = c.get("UserPromptSubmit", 0)
    print("\n## 사용자 정정")
    print("  정정 발화 %d건 / 프롬프트 %d건 (%.1f%%)" % (len(corr), prompts, 100.0 * len(corr) / max(1, prompts)))
    for r in corr[-5:]:
        print("   ", r.get("ts"), r.get("match"), "|", (r.get("prompt_head") or "")[:60].replace("\n", " "))

    tools = collections.Counter(r.get("tool") for r in ev if r.get("ev") == "PostToolUse")
    delphi = sum(1 for r in ev if r.get("ev") == "PostToolUse" and r.get("delphi"))
    print("\n## 도구")
    print("  호출 %d건 (서브에이전트 %d) · Delphi 관련 %d · K6 차단 %d" % (
        sum(tools.values()), sum(1 for r in ev if r.get("ev") == "PostToolUse" and r.get("agent_id")), delphi, c.get("K6Deny", 0)))
    print("  상위:", dict(tools.most_common(8)))

    gate = [r for r in ev if r.get("ev") == "ClaimGate" and not r.get("agent_id")]
    if gate:
        flagged = [r["flagged"] for r in gate]
        print("\n## 주장 게이트 (기록 전용, 메인 응답만)")
        print("  응답 %d개 · 증거 없는 강한 주장 평균 %.2f · 1건 이상인 응답 %.0f%%" % (
            len(gate), sum(flagged) / len(gate), 100.0 * sum(1 for f in flagged if f) / len(gate)))

    il = [r for r in ev if r.get("ev") == "InstructionsLoaded"]
    glob_hits = [r for r in il if r.get("load_reason") == "path_glob_match"]
    print("\n## paths 실험 (rules/probe-*.md)")
    print("  InstructionsLoaded %d건 · path_glob_match %d건" % (len(il), len(glob_hits)))
    for r in glob_hits[:5]:
        print("   ", os.path.basename(r.get("file_path", "")), "←", r.get("trigger_file_path"), r.get("globs"))
    if not glob_hits:
        print("   (아직 발동 기록 없음 — 새 세션에서 D:\\K 파일을 읽으면 결론이 난다)")

    print("\n## 훅 오류 로그")
    for p in sorted(glob.glob(os.path.join(LOG, "*-errors.log"))):
        n = sum(1 for _ in open(p, encoding="utf-8", errors="replace"))
        print("  %s  %d줄" % (os.path.basename(p), n))
    if not glob.glob(os.path.join(LOG, "*-errors.log")):
        print("  없음")

    xml = os.path.join(HOME, "harness.v2.xml")
    if os.path.exists(xml):
        ms = re.findall(r'<m id="([^"]+)"\s+hits="(\d+)"\s+violations="(\d+)"', open(xml, encoding="utf-8").read())
        top = sorted(((int(v), k) for k, h, v in ms if int(v)), reverse=True)[:8]
        print("\n## harness.v2.xml violations 상위")
        print("  " + " · ".join("%s %d" % (k, v) for v, k in top))


if __name__ == "__main__":
    main()
