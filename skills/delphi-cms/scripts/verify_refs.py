# -*- coding: utf-8 -*-
"""references/*.md 의 근거 표시가 지금도 맞는지 기계적으로 확인한다 (읽기 전용).

  〔경로 <경로>〕                 → 그 경로가 있어야 한다
  〔<경로>:<줄> "<문자열>"〕     → 그 파일 그 줄에 그 문자열이 있어야 한다 (공백·대소문자 무시)
  〔@X:<줄> "<문자열>"〕         → 같은 md 안의  [@X]: <경로>  정의를 쓴다

  python scripts/verify_refs.py            → 항목별 OK/FAIL, 끝에 요약. FAIL 이 있으면 exit 1
"""
import glob
import os
import re
import sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "..", "references")
ALIAS = re.compile(r"^\[@(\w+)\]:\s*(.+?)\s*$", re.M)
PATHREF = re.compile(r"〔경로 ([A-Za-z]:[^〕]+)〕")  # 드라이브 문자로 시작하는 것만 (설명문 예시 제외)
LINEREF = re.compile(r"〔(@\w+|[A-Za-z]:[^〕]+?):(\d+) \"(.+?)\"〕")
_cache = {}


def lines_of(path):
    if path not in _cache:
        raw = open(path, "rb").read()
        if raw[:3] == b"\xef\xbb\xbf":
            text = raw[3:].decode("utf-8", "replace")
        else:
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                text = raw.decode("cp949", "replace")
        _cache[path] = [l.rstrip("\r") for l in text.split("\n")]
    return _cache[path]


def norm(s):
    return re.sub(r"\s+", "", s).lower()


def main():
    ok = fail = 0
    for md in sorted(glob.glob(os.path.join(REF, "**", "*.md"), recursive=True)):
        body = open(md, encoding="utf-8").read()
        alias = {k: v for k, v in ALIAS.findall(body)}
        rel = os.path.relpath(md, REF)
        for p in PATHREF.findall(body):
            good = os.path.exists(p)
            ok, fail = ok + good, fail + (not good)
            print("%s  %s  경로 %s" % ("OK  " if good else "FAIL", rel, p))
        for src, ln, tok in LINEREF.findall(body):
            path = alias.get(src[1:]) if src.startswith("@") else src
            n = int(ln)
            if not path:
                good, why = False, "별칭 %s 정의 없음" % src
            elif not os.path.exists(path):
                good, why = False, "파일 없음"
            else:
                L = lines_of(path)
                if n > len(L):
                    good, why = False, "줄 범위 밖 (%d줄)" % len(L)
                else:
                    good = norm(tok) in norm(L[n - 1])
                    why = "" if good else "실제: " + L[n - 1].strip()[:90]
                    if not good:
                        near = [i + 1 for i, l in enumerate(L) if norm(tok) in norm(l)]
                        if near:
                            why += "  → 지금은 %s행에 있음" % ",".join(map(str, near[:5]))
            ok, fail = ok + good, fail + (not good)
            print("%s  %s  %s:%s \"%s\" %s" % ("OK  " if good else "FAIL", rel, src, ln, tok[:40], why))
    print("\n근거 %d개 중 OK %d · FAIL %d → %s" % (ok + fail, ok, fail, "PASS" if fail == 0 else "줄 번호 갱신 필요"))
    return fail


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
