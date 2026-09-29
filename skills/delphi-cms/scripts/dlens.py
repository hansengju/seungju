# -*- coding: utf-8 -*-
"""dlens — Delphi 소스 판정 도구 (읽기 전용, 파일을 절대 고치지 않는다).

사람 눈 대신 이 도구가 판정한다. 결과에는 항상 [범위] 가 붙는다.

  dlens enc     <파일...>                       인코딩·BOM·줄바꿈 (편집 경로 결정용)
  dlens live    <파일> <줄> [<줄>...]           활성 / 주석(// { } (* *)) / 조건부({$IF..}) / 도달불가 추정
  dlens nest    <파일> <줄>                     그 줄을 감싼 routine·if·begin 체인, 단문 본문 여부
  dlens grep    <정규식> <경로...> [-i] [--ext pas,dpr,inc]   검색 + 줄마다 판정 라벨 + 요약
  dlens callers <식별자> <경로...> [--ext ...]  단어 단위 검색 + 정의/참조/DFM 이벤트 배선 구분
  dlens dfm     <dfm파일> [<이름>]              object / inline / inherited 선언과 부모 경로

한계(휴리스틱): 조건부 심볼 값은 모른다(--define / --undef 로 지정). goto·asm 내부·
포함 파일({$I})은 따라가지 않는다. 불확실하면 [판정불가] 나 [주의] 를 출력한다.
"""
import argparse
import bisect
import os
import re
import sys

try:
    sys.stdout.reconfigure(errors="replace")
except Exception:
    pass

CODE, LCOM, BCOM, PCOM, STR, DIR = range(6)
STATE_NAME = {LCOM: "라인주석 //", BCOM: "블록주석 { }", PCOM: "블록주석 (* *)", STR: "문자열 안", DIR: "컴파일 지시어"}
SPECIAL = re.compile(r"//|\{|\(\*|'")
TOKEN = re.compile(r"&?[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|:=|<>|<=|>=|\.\.|[;:=(),.\[\]^@+\-*/<>]|'")
ROUTINE_KW = ("procedure", "function", "constructor", "destructor", "operator")


# ───────────────────────── 파일 읽기 ─────────────────────────
def read_text(path):
    raw = open(path, "rb").read()
    info = {"bytes": len(raw), "bom": None}
    if raw[:3] == b"\xef\xbb\xbf":
        info["bom"], enc, text = "UTF-8", "utf-8", raw[3:].decode("utf-8", "replace")
    elif raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        info["bom"], enc, text = "UTF-16", "utf-16", raw.decode("utf-16", "replace")
    else:
        try:
            text = raw.decode("utf-8")
            enc = "utf-8" if any(b > 127 for b in raw) else "ascii"
        except UnicodeDecodeError:
            enc, text = "cp949", raw.decode("cp949", "replace")
    info["enc"] = enc
    info["crlf"] = raw.count(b"\r\n")
    info["lone_lf"] = raw.count(b"\n") - info["crlf"]
    info["binary_dfm"] = raw[:4] == b"TPF0" or raw[:2] == b"\xff\x0a"
    return text, info


class Src:
    """한 파일의 문자 상태 · 줄 오프셋 · 조건부 스택 · 블록 구조를 한 번에 계산한다."""

    def __init__(self, path, defines=(), undefs=(), preread=None):
        self.path = path
        self.text, self.info = preread if preread else read_text(path)
        t = self.text
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", t)]
        self.lines = t.split("\n")
        self.defines = {d.upper() for d in defines}
        self.undefs = {d.upper() for d in undefs}
        self.underflow = 0
        self._lex()
        self._cond_events()
        self._structure()

    # ── 문자 단위 상태 (코드 / 주석 3종 / 문자열 / 지시어) ──
    def _lex(self):
        t, n = self.text, len(self.text)
        st = bytearray(n)
        self.comments, self.directives = [], []
        i = 0
        while i < n:
            m = SPECIAL.search(t, i)
            if not m:
                break
            i, tok = m.start(), m.group()
            if tok == "//":
                j = t.find("\n", i)
                j = n if j < 0 else j
                st[i:j] = bytes([LCOM]) * (j - i)
            elif tok == "{":
                j = t.find("}", i + 1)
                j = n if j < 0 else j + 1
                kind = DIR if t.startswith("{$", i) else BCOM
                st[i:j] = bytes([kind]) * (j - i)
                (self.directives if kind == DIR else self.comments).append(
                    (i, t[i + 2:j - 1]) if kind == DIR else (BCOM, i, j))
            elif tok == "(*":
                j = t.find("*)", i + 2)
                j = n if j < 0 else j + 2
                kind = DIR if t.startswith("(*$", i) else PCOM
                st[i:j] = bytes([kind]) * (j - i)
                (self.directives if kind == DIR else self.comments).append(
                    (i, t[i + 3:j - 2]) if kind == DIR else (PCOM, i, j))
            else:  # 문자열 '...'  ('' 는 이스케이프, 줄을 넘지 않음)
                j = i + 1
                while j < n:
                    if t[j] == "'":
                        if j + 1 < n and t[j + 1] == "'":
                            j += 2
                            continue
                        j += 1
                        break
                    if t[j] == "\n":
                        break
                    j += 1
                st[i:j] = bytes([STR]) * (j - i)
            i = max(j, i + 1)
        self.state = st

    def _cond_events(self):
        stack, self.cond_pos, self.cond_snap = [], [], []
        for pos, body in self.directives:
            m = re.match(r"\s*([A-Za-z]+)\s*(.*)", body, re.S)
            if not m:
                continue
            kw, arg = m.group(1).upper(), m.group(2).strip()
            sym = (arg.split() or [""])[0].upper()
            if kw in ("IFDEF", "IFNDEF", "IFOPT"):
                stack.append({"kw": kw, "arg": sym, "branch": "then"})
            elif kw == "IF":
                stack.append({"kw": "IF", "arg": arg[:40], "branch": "then"})
            elif kw == "ELSE" and stack:
                stack[-1] = dict(stack[-1], branch="else")
            elif kw == "ELSEIF" and stack:
                stack[-1] = dict(stack[-1], branch="elseif")
            elif kw in ("ENDIF", "IFEND") and stack:
                stack.pop()
            elif kw == "DEFINE" and sym:
                self.defines.add(sym)
                continue
            elif kw == "UNDEF" and sym:
                self.defines.discard(sym)
                self.undefs.add(sym)
                continue
            else:
                continue
            end = self.text.find("}", pos)
            self.cond_pos.append(end + 1 if end >= 0 else pos + 1)
            self.cond_snap.append([dict(f) for f in stack])

    def cond_at(self, pos):
        k = bisect.bisect_right(self.cond_pos, pos) - 1
        return self.cond_snap[k] if k >= 0 else []

    def eval_cond(self, frames):
        """모든 프레임 참 → 'on' / 하나라도 거짓 → 'off' / 모르는 것이 있으면 'unknown'."""
        res = "on"
        for f in frames:
            if f["kw"] in ("IFDEF", "IFNDEF") and f["branch"] in ("then", "else"):
                if f["arg"] in self.defines:
                    val = True
                elif f["arg"] in self.undefs:
                    val = False
                else:
                    res = "unknown"
                    continue
                truth = val if f["kw"] == "IFDEF" else not val
                if f["branch"] == "else":
                    truth = not truth
                if not truth:
                    return "off"
            else:
                res = "unknown"
        return res

    def line_of(self, pos):
        return bisect.bisect_right(self.line_starts, pos)

    def pos_of(self, line, col=0):
        return self.line_starts[line - 1] + col

    def comment_span(self, pos):
        for _kind, s, e in self.comments:
            if s <= pos < e:
                return self.line_of(s), self.line_of(max(s, e - 1))
        return None

    # ── 블록 구조 (코드 영역 토큰만) ──
    def _tokens(self):
        st, toks = self.state, []
        for m in TOKEN.finditer(self.text):
            p = m.start()
            if st[p] == CODE:
                toks.append((m.group().lstrip("&").lower(), p))
            elif st[p] == STR and (p == 0 or st[p - 1] != STR):
                toks.append(("<str>", p))
        return toks

    def _structure(self):
        toks = self.toks = self._tokens()
        nlines = len(self.lines)
        stack, pending = [], []
        self.snap = [None] * (nlines + 2)
        self.prev_tok = [None] * (nlines + 2)
        self.first_tok = [None] * (nlines + 2)
        self.routines = []
        last_line, prev, section, paren, stmt_start = 0, None, None, 0, True
        for idx, (tk, p) in enumerate(toks):
            ln = self.line_of(p)
            if ln != last_line:
                for L in range(last_line + 1, ln + 1):
                    self.snap[L] = [dict(b) for b in stack]
                self.prev_tok[ln], self.first_tok[ln] = prev, idx
                last_line = ln

            if tk == "(":
                paren += 1
            elif tk == ")":
                paren = max(0, paren - 1)

            if tk in ("interface", "implementation", "initialization", "finalization") and prev != "=":
                section = tk

            if stmt_start and paren == 0 and tk in ("exit", "raise", "abort", "halt") and stack:
                top = stack[-1]
                if top["kind"] in ("begin", "try", "repeat") and top.get("exit") is None:
                    top["exit"] = ln

            if tk in ROUTINE_KW and prev not in ("=", "of", ":", "(", ","):
                inside_type = any(b["kind"] in ("class", "record", "interface") for b in stack)
                if not inside_type and section != "interface":
                    name = self._routine_name(idx)
                    pending.append((name, ln, len(stack)))
                    self.routines.append((name, ln))
            elif tk == "begin":
                if pending and len(stack) == pending[-1][2]:
                    name, hl, _d = pending.pop()
                    stack.append(self._blk("begin", ln, hl, "routine", name))
                else:
                    hl, what = self._header_of(idx)
                    stack.append(self._blk("begin", ln, hl, what))
            elif tk in ("try", "asm", "repeat"):
                hl, what = self._header_of(idx)
                stack.append(self._blk(tk, ln, hl, what))
            elif tk == "case":
                if not (stack and stack[-1]["kind"] == "record"):
                    hl, what = self._header_of(idx)
                    stack.append(self._blk("case", ln, hl, what))
            elif tk == "record":
                stack.append(self._blk("record", ln, ln, "record"))
            elif tk in ("class", "object", "interface", "dispinterface") and prev in ("=", "packed"):
                if not self._is_forward_type(idx):
                    stack.append(self._blk("interface" if tk == "interface" else "class", ln, ln, tk))
            elif tk == "end":
                if stack:
                    stack.pop()
                elif not (idx + 1 < len(toks) and toks[idx + 1][0] == "."):  # 유닛 끝 'end.' 은 짝 없음이 정상
                    self.underflow += 1
            elif tk == "until" and stack and stack[-1]["kind"] == "repeat":
                stack.pop()

            stmt_start = tk in (";", "begin", "try", "finally", "except", "repeat") and paren == 0
            prev = tk
        for L in range(last_line + 1, nlines + 2):
            self.snap[L] = [dict(b) for b in stack]
        self.final_depth = len(stack)

    @staticmethod
    def _blk(kind, line, hdr, what, routine=None):
        return {"kind": kind, "line": line, "hdr": hdr, "what": what, "routine": routine, "exit": None}

    def _routine_name(self, idx):
        j = idx + 1
        while j < len(self.toks) and self.toks[j][0] not in ("(", ";", ":") and j - idx < 8:
            j += 1
        if idx + 1 >= len(self.toks) or j >= len(self.toks):
            return "?"
        return re.sub(r"\s+", "", self.text[self.toks[idx + 1][1]:self.toks[j][1]]) or "?"

    def _is_forward_type(self, idx):
        j = idx + 1
        if j >= len(self.toks):
            return True
        if self.toks[j][0] in (";", "of"):
            return True
        if self.toks[j][0] == "(":
            depth = 0
            while j < len(self.toks):
                depth += {"(": 1, ")": -1}.get(self.toks[j][0], 0)
                if depth == 0:
                    break
                j += 1
            return j + 1 < len(self.toks) and self.toks[j + 1][0] == ";"
        return False

    def _header_of(self, idx):
        """begin/try/case 앞의 제어문 머리(if/for/while/with/on, else, case 라벨)를 찾는다."""
        if idx == 0:
            return self.line_of(self.toks[0][1]), "block"
        pt = self.toks[idx - 1][0]
        if pt in ("then", "do"):
            j, paren = idx - 2, 0
            while j >= 0:
                tk = self.toks[j][0]
                if tk == ")":
                    paren += 1
                elif tk == "(":
                    paren -= 1
                elif paren == 0 and tk in (";", "begin", "try", "then", "else", "do", "repeat", "finally", "except"):
                    break
                elif paren == 0 and tk in ("if", "for", "while", "with", "on"):
                    return self.line_of(self.toks[j][1]), tk
                j -= 1
            return self.line_of(self.toks[idx - 1][1]), pt
        if pt == "else":
            return self.line_of(self.toks[idx - 1][1]), "else"
        if pt == ":":
            return self.line_of(self.toks[idx - 1][1]), "case-label"
        return self.line_of(self.toks[idx][1]), "block"

    # ── 판정 ──
    def first_code_pos(self, line):
        s = self.pos_of(line)
        e = self.line_starts[line] - 1 if line < len(self.line_starts) else len(self.text)
        for p in range(s, e):
            if self.state[p] in (CODE, STR) and not self.text[p].isspace():
                return p
        return None

    def classify(self, line, pos=None):
        if line < 1 or line > len(self.lines):
            return "판정불가", "줄 번호 범위 밖 (1~%d)" % len(self.lines)
        txt = self.lines[line - 1]
        s = self.pos_of(line)
        if pos is None:
            pos = self.first_code_pos(line)
            if pos is None:
                nonsp = [p for p in range(s, s + len(txt)) if not self.text[p].isspace()]
                if not nonsp:
                    k = self.state[s] if s < len(self.state) else CODE
                    if k in (BCOM, PCOM):
                        a, b = self.comment_span(s) or (line, line)
                        return STATE_NAME[k], "%d~%d행 블록 안 빈 줄" % (a, b)
                    return "빈 줄", ""
                pos = nonsp[0]
        k = self.state[pos]
        if k in (BCOM, PCOM):
            a, b = self.comment_span(pos) or (line, line)
            return STATE_NAME[k], "%d~%d행" % (a, b)
        if k in (LCOM, DIR):
            return STATE_NAME[k], ""
        # 문자열 리터럴은 코드 영역에만 생긴다 → 줄은 코드로 판정하고, 매치 위치만 설명으로 남긴다
        extra = ["매치 위치는 문자열 리터럴 안"] if k == STR else []
        frames = self.cond_at(pos)
        if frames:
            desc = " > ".join("{$%s %s}%s" % (f["kw"], f["arg"], "" if f["branch"] == "then" else "·" + f["branch"])
                              for f in frames)
            ev = self.eval_cond(frames)
            if ev == "off":
                return "조건부 비활성", desc
            if ev == "unknown":
                extra.append("조건부 " + desc + " (심볼 값 미상 — --define/--undef)")
        dead = [b for b in (self.snap[line] or []) if b.get("exit") and b["exit"] < line]
        if dead:
            return "도달불가 추정", "%d행 Exit/raise 뒤 (%d행에서 시작한 블록)" % (dead[-1]["exit"], dead[-1]["line"])
        if re.match(r"\s*(class\s+)?(procedure|function|constructor|destructor)\b", txt, re.I):
            extra.append("정의/선언")
        rest = set(self.state[pos:s + len(txt)])
        if rest & {LCOM, BCOM, PCOM}:
            extra.append("줄 일부 주석")
        return "활성", " · ".join(extra)

    def nesting(self, line):
        chain = []
        for b in self.snap[line] or []:
            hdr = self.lines[b["hdr"] - 1].strip()[:110] if b["hdr"] else ""
            if b["what"] == "routine":
                chain.append((b["line"], "routine 본문: %s (머리 %d행)" % (b["routine"], b["hdr"])))
            elif b["kind"] in ("class", "record", "interface"):
                chain.append((b["line"], "%s 선언" % b["kind"]))
            else:
                chain.append((b["line"], "%s ← %s %d행: %s" % (b["kind"], b["what"], b["hdr"], hdr)))
        single = None
        pt, i = self.prev_tok[line], self.first_tok[line]
        if pt in ("then", "do") and i is not None:
            hl, what = self._header_of(i)
            single = "%s %d행: %s" % (what, hl, self.lines[hl - 1].strip()[:110])
        elif pt == "else" and i is not None:
            hl = self.line_of(self.toks[i - 1][1])
            single = "else %d행: %s" % (hl, self.lines[hl - 1].strip()[:110])
        return chain, single


# ───────────────────────── 명령 ─────────────────────────
def iter_files(paths, exts):
    for p in paths:
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in sorted(files):
                    if f.rsplit(".", 1)[-1].lower() in exts:
                        yield os.path.join(root, f)


def label_str(lab, det):
    return "[%s%s]" % (lab, (" · " + det) if det else "")


def cmd_enc(a):
    for p in a.files:
        _t, i = read_text(p)
        print("%s  enc=%s BOM=%s CRLF=%d 단독LF=%d bytes=%d%s" % (
            p, i["enc"], i["bom"] or "없음", i["crlf"], i["lone_lf"], i["bytes"],
            " (바이너리 DFM)" if i["binary_dfm"] else ""))
    print("[편집 경로] cp949 파일은 Read/Edit/Write 금지(K6) → Python 으로 cp949 명시 읽기·쓰기 + 저장 후 왕복 검증")


def cmd_live(a):
    s = Src(a.file, a.define, a.undef)
    print("[범위] %s (%s, %d줄)" % (a.file, s.info["enc"], len(s.lines)))
    for ln in a.lines:
        lab, det = s.classify(ln)
        body = s.lines[ln - 1].strip()[:100] if 0 < ln <= len(s.lines) else ""
        print("%d  %s  %s" % (ln, label_str(lab, det), body))


def cmd_nest(a):
    s = Src(a.file, a.define, a.undef)
    ln = a.line
    lab, det = s.classify(ln)
    print("[범위] %s (%s, %d줄)" % (a.file, s.info["enc"], len(s.lines)))
    if not 0 < ln <= len(s.lines):
        print("[판정불가] 줄 번호 범위 밖")
        return
    print("%d  %s  %s" % (ln, label_str(lab, det), s.lines[ln - 1].strip()[:100]))
    chain, single = s.nesting(ln)
    print("감싼 구조 (바깥 → 안):")
    if not chain:
        print("  (없음 — 최상위)")
    for i, (bl, desc) in enumerate(chain):
        print("  %s%d행  %s" % ("  " * i, bl, desc))
    print("단문 본문(begin 없이 바로 딸린 줄): %s" % (single or "아님"))
    if s.underflow or s.final_depth:
        print("[주의] 블록 균형 불일치(underflow=%d, 파일 끝 남은 깊이=%d) — 구조 판정 신뢰도 낮음"
              % (s.underflow, s.final_depth))


def run_search(rx, paths, exts, defines, undefs):
    files = list(iter_files(paths, exts))
    cnt, rows = {}, []
    for f in files:
        try:
            pre = read_text(f)
            if not rx.search(pre[0]):
                continue
            if f.lower().endswith(".dfm"):
                for n, line in enumerate(pre[0].split("\n"), 1):
                    if rx.search(line):
                        kind = "DFM 이벤트 배선" if re.match(r"\s*On\w+\s*=", line) else "DFM"
                        rows.append((f, n, kind, "", line.strip()))
                        cnt[kind] = cnt.get(kind, 0) + 1
                continue
            s = Src(f, defines, undefs, preread=pre)
            for n, line in enumerate(s.lines, 1):
                m = rx.search(line)
                if not m:
                    continue
                lab, det = s.classify(n, s.pos_of(n, m.start()))
                rows.append((f, n, lab, det, line.strip()))
                key = "정의/선언" if (lab == "활성" and "정의/선언" in det) else lab
                cnt[key] = cnt.get(key, 0) + 1
        except Exception as e:
            rows.append((f, 0, "판정불가", str(e)[:60], ""))
            cnt["판정불가"] = cnt.get("판정불가", 0) + 1
    return files, rows, cnt


def common_base(paths):
    try:
        b = os.path.commonpath([os.path.abspath(p) for p in paths])
        return b if os.path.isdir(b) else os.path.dirname(b)
    except ValueError:
        return None


def print_search(desc, files, rows, cnt, base):
    print("[범위] 파일 %d개 · %s" % (len(files), desc))
    for f, n, lab, det, txt in rows:
        rel = os.path.relpath(f, base) if base else f
        print("%s:%d  %s  %s" % (rel, n, label_str(lab, det), txt[:100]))
    if not rows:
        print("(0건 — 위 범위 안에 이 텍스트가 없다는 뜻일 뿐. 호출 체인·동적 호출·범위 밖 파일은 미확인)")
    print("[요약] " + (" · ".join("%s %d" % kv for kv in sorted(cnt.items())) if cnt else "0건"))


def cmd_grep(a):
    rx = re.compile(a.pattern, re.I if a.i else 0)
    exts = tuple(e.strip().lower() for e in a.ext.split(","))
    files, rows, cnt = run_search(rx, a.paths, exts, a.define, a.undef)
    print_search("패턴 /%s/%s · 확장자 %s" % (a.pattern, "i" if a.i else "", ",".join(exts)),
                 files, rows, cnt, common_base(a.paths))


def cmd_callers(a):
    rx = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(a.symbol), re.I)
    exts = tuple(e.strip().lower() for e in a.ext.split(","))
    files, rows, cnt = run_search(rx, a.paths, exts, a.define, a.undef)
    print_search("식별자 '%s'(단어·대소문자 무시) · 확장자 %s" % (a.symbol, ",".join(exts)),
                 files, rows, cnt, common_base(a.paths))


def cmd_dfm(a):
    text, info = read_text(a.file)
    if info["binary_dfm"]:
        print("[판정불가] 바이너리 DFM — 텍스트로 변환한 뒤 다시")
        return
    decl = re.compile(r"^\s*(object|inline|inherited)\s+(\w+)(?:\s*:\s*([\w.]+))?", re.I)
    stack, hits, total = [], [], 0
    for n, line in enumerate(text.split("\n"), 1):
        m = decl.match(line)
        if m:
            total += 1
            kind, name, typ = m.group(1).lower(), m.group(2), m.group(3) or "?"
            if a.name is None or name.lower() == a.name.lower():
                hits.append((n, kind, name, typ, " > ".join(x[1] for x in stack)))
            stack.append((kind, name))
        elif re.match(r"^\s*item\s*$", line, re.I):
            stack.append(("item", "item"))
        elif re.match(r"^\s*end(\s*>)?\s*$", line, re.I) and stack:
            stack.pop()
    print("[범위] %s (%s) · 선언 %d개 · object|inline|inherited 모두 검색" % (a.file, info["enc"], total))
    for n, kind, name, typ, parent in hits:
        print("%d  %s %s: %s   부모: %s" % (n, kind, name, typ, parent or "(최상위)"))
    if not hits:
        print("(0건 — 이 파일 안에 그 이름의 선언 없음. inherited 폼이면 부모 DFM 도 확인)")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="dlens", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cond_opts(p):
        p.add_argument("--define", action="append", default=[], help="참으로 볼 조건부 심볼")
        p.add_argument("--undef", action="append", default=[], help="거짓으로 볼 조건부 심볼")

    p = sub.add_parser("enc")
    p.add_argument("files", nargs="+")
    p = sub.add_parser("live")
    p.add_argument("file")
    p.add_argument("lines", nargs="+", type=int)
    cond_opts(p)
    p = sub.add_parser("nest")
    p.add_argument("file")
    p.add_argument("line", type=int)
    cond_opts(p)
    p = sub.add_parser("grep")
    p.add_argument("pattern")
    p.add_argument("paths", nargs="+")
    p.add_argument("-i", action="store_true")
    p.add_argument("--ext", default="pas,dpr,inc")
    cond_opts(p)
    p = sub.add_parser("callers")
    p.add_argument("symbol")
    p.add_argument("paths", nargs="+")
    p.add_argument("--ext", default="pas,dpr,inc,dfm")
    cond_opts(p)
    p = sub.add_parser("dfm")
    p.add_argument("file")
    p.add_argument("name", nargs="?")
    a = ap.parse_args(argv)
    {"enc": cmd_enc, "live": cmd_live, "nest": cmd_nest, "grep": cmd_grep,
     "callers": cmd_callers, "dfm": cmd_dfm}[a.cmd](a)


if __name__ == "__main__":
    main()
