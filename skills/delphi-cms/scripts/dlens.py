# -*- coding: utf-8 -*-
"""dlens — Delphi 소스 판정 도구 (읽기 전용, 파일을 절대 고치지 않는다).

사람 눈 대신 이 도구가 판정한다. 결과에는 항상 [범위] 가 붙는다.

  dlens enc     <파일...>                       인코딩·BOM·줄바꿈 (편집 경로 결정용)
  dlens live    <파일> <줄> [<줄>...]           활성 / 주석(// { } (* *)) / 조건부({$IF..}) / 도달불가 추정
  dlens nest    <파일> <줄>                     그 줄을 감싼 routine·if·begin 체인, 단문 본문 여부
  dlens grep    <정규식> <경로...> [-i] [--ext pas,dpr,inc]   검색 + 줄마다 판정 라벨 + 요약
  dlens callers <식별자> <경로...> [--ext ...]  단어 단위 검색 + 정의/참조/DFM 이벤트 배선 구분
  dlens dfm     <dfm파일> [<이름>]              object / inline / inherited 선언과 부모 경로

조건부 컴파일: Delphi 10.4 Win32 기본 심볼(UNICODE MSWINDOWS WIN32 CPUX86 CPU386 VER340
CONDITIONALEXPRESSIONS)은 켜진 것으로 본다(--no-builtin 으로 끔). 프로젝트 심볼(DEBUG 등)은
모른다 → --define / --undef 로 지정. {$DEFINE}/{$UNDEF} 는 그 자리의 조건을 따져 순서대로 적용한다.

한계(휴리스틱): goto·asm 내부·포함 파일({$I})은 따라가지 않는다. 불확실하면 [판정불가] 나 [주의] 를 낸다.
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
COMMENT_LABELS = {STATE_NAME[LCOM], STATE_NAME[BCOM], STATE_NAME[PCOM], STATE_NAME[DIR]}
SPECIAL = re.compile(r"//|\{|\(\*|'")
TOKEN = re.compile(r"&?[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|:=|<>|<=|>=|\.\.|[;:=(),.\[\]^@+\-*/<>]|'")
ROUTINE_KW = ("procedure", "function", "constructor", "destructor", "operator")
EXIT_KW = ("exit", "raise", "abort", "halt", "break", "continue")
STMT_BOUND = (";", "begin", "then", "do", "else", "try", "finally", "except", "repeat", "of", ":")
BUILTIN = ("UNICODE", "MSWINDOWS", "WIN32", "CPUX86", "CPU386", "VER340", "CONDITIONALEXPRESSIONS")
HEADER_RE = re.compile(r"^\s*(?:class\s+)?(?:procedure|function|constructor|destructor|operator)\s+([A-Za-z_][\w.]*)", re.I)
DFM_EVENT_RE = re.compile(r"^\s*(?:\w+\.)*On\w+\s*=\s*('?)[A-Za-z_]")


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
    """한 파일의 문자 상태 · 조건부 스택 · 블록 구조를 한 번에 계산한다."""

    def __init__(self, path, defines=(), undefs=(), preread=None, builtin=True):
        self.path = path
        self.text, self.info = preread if preread else read_text(path)
        t = self.text
        self.line_starts = [0] + [m.end() for m in re.finditer(r"\n", t)]
        self.lines = t.split("\n")
        self.true = {d.upper() for d in (tuple(BUILTIN) if builtin else ()) + tuple(defines)}
        self.false = {d.upper() for d in undefs}
        self.true -= self.false
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
                if t.startswith("{$", i):
                    st[i:j] = bytes([DIR]) * (j - i)
                    self.directives.append((i, j, t[i + 2:j - 1]))
                else:
                    st[i:j] = bytes([BCOM]) * (j - i)
                    self.comments.append((BCOM, i, j))
            elif tok == "(*":
                j = t.find("*)", i + 2)
                j = n if j < 0 else j + 2
                if t.startswith("(*$", i):
                    st[i:j] = bytes([DIR]) * (j - i)
                    self.directives.append((i, j, t[i + 3:j - 2]))
                else:
                    st[i:j] = bytes([PCOM]) * (j - i)
                    self.comments.append((PCOM, i, j))
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

    # ── 조건부 컴파일: 위치 순서대로 평가 ──
    def _sym(self, s):
        return True if s in self.true else False if s in self.false else None

    @staticmethod
    def eval_frames(frames):
        """모든 프레임 참 → 'on' / 하나라도 거짓 → 'off' / 모르는 것이 있으면 'unknown'."""
        res = "on"
        for f in frames:
            v = f["val"]
            if v is None or f["branch"] == "elseif":
                res = "unknown"
                continue
            truth = v if f["branch"] == "then" else not v
            if not truth:
                return "off"
        return res

    def _cond_events(self):
        stack, self.cond_pos, self.cond_snap = [], [], []
        for pos, end, body in self.directives:
            m = re.match(r"\s*([A-Za-z]+)\s*(.*)", body, re.S)
            if not m:
                continue
            kw, arg = m.group(1).upper(), m.group(2).strip()
            sym = (re.split(r"[\s}]", arg) or [""])[0].upper()
            if kw in ("IFDEF", "IFNDEF"):
                v = self._sym(sym)
                val = v if kw == "IFDEF" or v is None else not v
                stack.append({"kw": kw, "arg": sym, "branch": "then", "val": val, "id": pos})
            elif kw in ("IF", "IFOPT"):
                stack.append({"kw": kw, "arg": arg[:40], "branch": "then", "val": None, "id": pos})
            elif kw == "ELSE" and stack:
                stack[-1] = dict(stack[-1], branch="else")
            elif kw == "ELSEIF" and stack:
                stack[-1] = dict(stack[-1], branch="elseif")
            elif kw in ("ENDIF", "IFEND") and stack:
                stack.pop()
            elif kw in ("DEFINE", "UNDEF") and sym:
                ev = self.eval_frames(stack)
                if ev == "on":
                    (self.true.add if kw == "DEFINE" else self.true.discard)(sym)
                    (self.false.discard if kw == "DEFINE" else self.false.add)(sym)
                elif ev == "unknown":  # 켜질지 모르는 자리의 DEFINE → 그 심볼은 이제 모름
                    self.true.discard(sym)
                    self.false.discard(sym)
                continue
            else:
                continue
            self.cond_pos.append(end)
            self.cond_snap.append([dict(f) for f in stack])

    def cond_at(self, pos):
        k = bisect.bisect_right(self.cond_pos, pos) - 1
        return self.cond_snap[k] if k >= 0 else []

    def exclusive(self, pos_a, pos_b):
        """두 위치가 같은 조건부 지시어의 서로 다른 분기에 있으면 True — 한 빌드에 함께 컴파일되지 않는다."""
        fa = {f["id"]: f["branch"] for f in self.cond_at(pos_a)}
        return any(fa.get(f["id"]) not in (None, f["branch"]) for f in self.cond_at(pos_b))

    def unknown_at(self, pos):
        fr = self.cond_at(pos)
        return bool(fr) and self.eval_frames(fr) == "unknown"

    def line_of(self, pos):
        return bisect.bisect_right(self.line_starts, pos)

    def pos_of(self, line, col=0):
        return self.line_starts[line - 1] + col

    def comment_span(self, pos):
        for _kind, s, e in self.comments:
            if s <= pos < e:
                return self.line_of(s), self.line_of(max(s, e - 1))
        return None

    # ── 블록 구조 (코드 영역 토큰만, 확실히 꺼진 조건부 분기는 뺀다) ──
    def _tokens(self):
        st, toks = self.state, []
        for m in TOKEN.finditer(self.text):
            p = m.start()
            if st[p] == CODE:
                tk = m.group().lstrip("&").lower()
            elif st[p] == STR and (p == 0 or st[p - 1] != STR):
                tk = "<str>"
            else:
                continue
            frames = self.cond_at(p)
            if frames and self.eval_frames(frames) == "off":
                continue
            toks.append((tk, p))
        return toks

    def _structure(self):
        toks = self.toks = self._tokens()
        nlines = len(self.lines)
        stack, pending = [], []
        self.snap = [None] * (nlines + 2)
        self.psnap = [None] * (nlines + 2)
        self.first_tok = [None] * (nlines + 2)
        self.routines = []
        last_line, prev, section, paren, stmt_start = 0, None, None, 0, True
        for idx, (tk, p) in enumerate(toks):
            ln = self.line_of(p)
            if ln != last_line:
                for L in range(last_line + 1, ln + 1):
                    self.snap[L] = [dict(b) for b in stack]
                    self.psnap[L] = list(pending)
                self.first_tok[ln] = idx
                last_line = ln

            if tk == "(":
                paren += 1
            elif tk == ")":
                paren = max(0, paren - 1)

            if tk in ("interface", "implementation", "initialization", "finalization") and prev != "=":
                section = tk

            # 직접 문장의 Exit/raise/Break/Continue — 그 문장이 끝나는 ';' 부터 뒤가 도달불가
            if stmt_start and paren == 0 and tk in EXIT_KW and stack:
                top = stack[-1]
                frames = self.cond_at(p)
                if (top["kind"] in ("begin", "try", "repeat") and top.get("exit") is None
                        and not (frames and self.eval_frames(frames) == "unknown")):
                    top["exit_pending"] = True
            if tk == ";" and paren == 0 and stack and stack[-1].get("exit_pending"):
                stack[-1]["exit"], stack[-1]["exit_pending"] = ln, False
            if tk in ("finally", "except") and stack and stack[-1]["kind"] == "try":
                stack[-1]["exit"], stack[-1]["exit_pending"] = None, False  # 예외·정리 절은 도달한다

            if tk in ROUTINE_KW and prev not in ("=", "of", ":", "(", ",", ":=", "to"):
                inside_type = any(b["kind"] in ("class", "record", "interface") for b in stack)
                if not inside_type and section != "interface":
                    name = self._routine_name(idx)
                    pending.append((name, ln, len(stack)))
                    self.routines.append((name, ln))
            elif tk in ("forward", "external") and prev == ";" and pending and ln - pending[-1][1] <= 3:
                pending.pop()
            elif tk == "begin":
                if pending and len(stack) == pending[-1][2]:
                    name, hl, _d = pending.pop()
                    stack.append(self._blk("begin", ln, hl, "routine", None, name))
                else:
                    hl, what, j = self._header_of(idx)
                    stack.append(self._blk("begin", ln, hl, what, j))
            elif tk in ("try", "asm", "repeat"):
                hl, what, j = self._header_of(idx)
                stack.append(self._blk(tk, ln, hl, what, j))
            elif tk == "case":
                if not (stack and stack[-1]["kind"] == "record"):
                    hl, what, j = self._header_of(idx)
                    stack.append(self._blk("case", ln, hl, what, j))
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
            self.psnap[L] = list(pending)
        self.final_depth = len(stack)

    @staticmethod
    def _blk(kind, line, hdr, what, hdr_idx=None, routine=None):
        return {"kind": kind, "line": line, "hdr": hdr, "what": what, "hdr_idx": hdr_idx,
                "routine": routine, "exit": None, "exit_pending": False}

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
        """토큰 idx 로 시작하는 문장/블록의 머리. (머리 줄, 종류, 머리 토큰 위치)."""
        if idx == 0:
            return self.line_of(self.toks[0][1]), "block", 0
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
                    return self.line_of(self.toks[j][1]), tk, j
                j -= 1
            return self.line_of(self.toks[idx - 1][1]), pt, idx - 1
        if pt == "else":
            return self.line_of(self.toks[idx - 1][1]), "else", idx - 1
        if pt == ":":
            return self.line_of(self.toks[idx - 1][1]), "case-label", idx - 1
        return self.line_of(self.toks[idx][1]), "block", idx

    def _outer_single_heads(self, j):
        """머리 토큰 j 가 다시 then/do/else 에 딸린 단문이면, 바깥 머리들을 (바깥→안) 모은다."""
        out, guard = [], 0
        while j and j > 0 and guard < 30:
            guard += 1
            pt = self.toks[j - 1][0]
            if pt in ("then", "do"):
                hl, what, j2 = self._header_of(j)
                out.append((hl, "단문 머리 %s %d행: %s" % (what, hl, self.lines[hl - 1].strip()[:100])))
                j = j2
            elif pt == "else":
                hl = self.line_of(self.toks[j - 1][1])
                out.append((hl, "단문 머리 else %d행" % hl))
                break
            else:
                break
        return list(reversed(out))

    def _stmt_start(self, i):
        """토큰 i 가 속한 문장의 시작 토큰 위치 (여러 줄 문장·괄호 안 연속줄 대응)."""
        k, paren = i, 0
        while k > 0:
            t = self.toks[k - 1][0]
            if t == ")":
                paren += 1
            elif t == "(":
                if paren > 0:
                    paren -= 1
            elif paren == 0 and t in STMT_BOUND:
                break
            k -= 1
        return k

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
        whole = pos is None
        if whole:
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
        extra = ["매치 위치는 문자열 리터럴 안"] if k == STR else []
        frames = self.cond_at(pos)
        if frames:
            desc = " > ".join("{$%s %s}%s" % (f["kw"], f["arg"], "" if f["branch"] == "then" else "·" + f["branch"])
                              for f in frames)
            ev = self.eval_frames(frames)
            if ev == "off":
                return "조건부 비활성", desc
            if ev == "unknown":
                extra.append("조건부 " + desc + " (심볼 값 미상 — --define/--undef)")
        dead = [b for b in (self.snap[line] or []) if b.get("exit") and b["exit"] < line]
        if dead:
            return "도달불가 추정", "%d행 Exit/raise/Break 문장 뒤 (%d행에서 시작한 블록)" % (dead[-1]["exit"], dead[-1]["line"])
        hm = HEADER_RE.match(txt)
        if hm:
            name_s, name_e = s + hm.start(1), s + hm.end(1)
            extra.append("정의/선언" if whole or name_s <= pos < name_e else "선언 시그니처 안 참조")
        rest = set(self.state[s:s + len(txt)])
        if rest & {LCOM, BCOM, PCOM}:
            extra.append("줄 일부 주석")
        return "활성", " · ".join(extra)

    def nesting(self, line):
        entries = []
        for name, hl, _d in self.psnap[line] or []:
            entries.append((hl, "routine 선언부: %s (머리 %d행)" % (name, hl)))
        mixed = False
        for b in self.snap[line] or []:
            hdr = self.lines[b["hdr"] - 1].strip()[:100] if b["hdr"] else ""
            if b["what"] == "routine":
                entries.append((b["line"], "routine 본문: %s (머리 %d행)" % (b["routine"], b["hdr"])))
                continue
            if b["kind"] in ("class", "record", "interface"):
                entries.append((b["line"], "%s 선언" % b["kind"]))
                continue
            if b.get("hdr_idx") is not None and b["what"] in ("if", "for", "while", "with", "on", "else"):
                entries.extend(self._outer_single_heads(b["hdr_idx"]))
            entries.append((b["line"], "%s ← %s %d행: %s" % (b["kind"], b["what"], b["hdr"], hdr)))
            if b.get("hdr_idx") is not None:
                mixed |= self.unknown_at(self.toks[b["hdr_idx"]][1])
        entries.sort(key=lambda e: e[0])

        single = None
        i = self.first_tok[line]
        if i is not None and self.toks[i][0] not in ("begin", "try", "case", "repeat", "asm", "end"):
            k = self._stmt_start(i)
            pt = self.toks[k - 1][0] if k > 0 else None
            heads = []
            if pt in ("then", "do"):
                hl, what, j = self._header_of(k)
                heads = self._outer_single_heads(j) + [(hl, "%s %d행: %s" % (what, hl, self.lines[hl - 1].strip()[:100]))]
            elif pt == "else":
                hl = self.line_of(self.toks[k - 1][1])
                heads = [(hl, "else %d행" % hl)]
            elif pt == ":" and (self.snap[line] or []) and self.snap[line][-1]["kind"] == "case":
                hl = self.line_of(self.toks[k - 1][1])
                heads = [(hl, "case 라벨 %d행: %s" % (hl, self.lines[hl - 1].strip()[:100]))]
            if heads and pt in ("then", "do", "else", ":") and self.exclusive(self.toks[k][1], self.toks[k - 1][1]):
                # 이 문장과 바로 앞 머리가 같은 {$IF..} 의 다른 분기 → 어느 빌드에서도 함께 컴파일되지 않는다
                heads, single = [], "아님 (앞 머리 %d행은 다른 조건부 분기라 함께 컴파일되지 않음)" % self.line_of(self.toks[k - 1][1])
            if heads:
                single = " → ".join(h[1] for h in heads)
                if self.line_of(self.toks[k][1]) != line:
                    single += "  (이 줄은 %d행에서 시작한 문장의 연속줄)" % self.line_of(self.toks[k][1])
        pos = self.first_code_pos(line)
        mixed |= bool(pos is not None and self.unknown_at(pos))
        return entries, single, mixed


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


def make_src(a, path, preread=None):
    return Src(path, a.define, a.undef, preread=preread, builtin=not a.no_builtin)


def cmd_enc(a):
    for p in a.files:
        _t, i = read_text(p)
        print("%s  enc=%s BOM=%s CRLF=%d 단독LF=%d bytes=%d%s" % (
            p, i["enc"], i["bom"] or "없음", i["crlf"], i["lone_lf"], i["bytes"],
            " (바이너리 DFM)" if i["binary_dfm"] else ""))
    print("[편집 경로] cp949 파일은 Read/Edit/Write 금지(K6) → Python 으로 cp949 명시 읽기·쓰기 + 저장 후 왕복 검증")


def scope_line(a, s):
    sym = "기본심볼 " + ("끔" if a.no_builtin else "켬(10.4 Win32)")
    if a.define or a.undef:
        sym += " · define=%s undef=%s" % (",".join(a.define) or "-", ",".join(a.undef) or "-")
    return "[범위] %s (%s, %d줄) · %s" % (a.file, s.info["enc"], len(s.lines), sym)


def cmd_live(a):
    s = make_src(a, a.file)
    print(scope_line(a, s))
    for ln in a.lines:
        lab, det = s.classify(ln)
        body = s.lines[ln - 1].strip()[:100] if 0 < ln <= len(s.lines) else ""
        print("%d  %s  %s" % (ln, label_str(lab, det), body))


def cmd_nest(a):
    s = make_src(a, a.file)
    ln = a.line
    print(scope_line(a, s))
    if not 0 < ln <= len(s.lines):
        print("[판정불가] 줄 번호 범위 밖")
        return
    lab, det = s.classify(ln)
    print("%d  %s  %s" % (ln, label_str(lab, det), s.lines[ln - 1].strip()[:100]))
    entries, single, mixed = s.nesting(ln)
    print("감싼 구조 (바깥 → 안):")
    if not entries:
        print("  (없음 — 최상위)")
    for i, (bl, desc) in enumerate(entries):
        print("  %s%d행  %s" % ("  " * i, bl, desc))
    print("단문 본문(begin 없이 딸린 문장): %s" % (single or "아님"))
    if mixed:
        print("[주의] 값을 모르는 조건부 분기 안/근처 — 구조는 양쪽 분기 토큰을 합쳐 계산했다. --define/--undef 로 분기를 정하면 정확해진다")
    if s.underflow or s.final_depth:
        print("[주의] 블록 균형 불일치(underflow=%d, 파일 끝 남은 깊이=%d) — 구조 판정 신뢰도 낮음"
              % (s.underflow, s.final_depth))


def run_search(a, rx, paths, exts):
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
                        m = DFM_EVENT_RE.match(line)
                        kind = ("DFM 이벤트 배선(스크립트 문자열)" if m.group(1) else "DFM 이벤트 배선") if m else "DFM"
                        rows.append((f, n, kind, "", line.strip()))
                        cnt[kind] = cnt.get(kind, 0) + 1
                continue
            s = make_src(a, f, preread=pre)
            for n, line in enumerate(s.lines, 1):
                labels = [s.classify(n, s.pos_of(n, m.start())) for m in rx.finditer(line)]
                if not labels:
                    continue
                code = [x for x in labels if x[0] not in COMMENT_LABELS]
                lab, det = code[0] if code else labels[0]
                if code and len(code) < len(labels) and "줄 일부 주석" not in det:
                    det = (det + " · " if det else "") + "같은 줄 다른 매치는 주석"
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


def print_search(a, desc, files, rows, cnt, base):
    sym = "기본심볼 " + ("끔" if a.no_builtin else "켬(10.4 Win32)")
    print("[범위] 파일 %d개 · %s · %s" % (len(files), desc, sym))
    for f, n, lab, det, txt in rows:
        rel = os.path.relpath(f, base) if base else f
        print("%s:%d  %s  %s" % (rel, n, label_str(lab, det), txt[:100]))
    if not rows:
        print("(0건 — 위 범위 안에 이 텍스트가 없다는 뜻일 뿐. 호출 체인·동적 호출·범위 밖 파일은 미확인)")
    print("[요약] " + (" · ".join("%s %d" % kv for kv in sorted(cnt.items())) if cnt else "0건"))


def cmd_grep(a):
    rx = re.compile(a.pattern, re.I if a.i else 0)
    exts = tuple(e.strip().lower() for e in a.ext.split(","))
    files, rows, cnt = run_search(a, rx, a.paths, exts)
    print_search(a, "패턴 /%s/%s · 확장자 %s" % (a.pattern, "i" if a.i else "", ",".join(exts)),
                 files, rows, cnt, common_base(a.paths))


def cmd_callers(a):
    rx = re.compile(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(a.symbol), re.I)
    exts = tuple(e.strip().lower() for e in a.ext.split(","))
    files, rows, cnt = run_search(a, rx, a.paths, exts)
    print_search(a, "식별자 '%s'(단어·대소문자 무시) · 확장자 %s" % (a.symbol, ",".join(exts)),
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
        p.add_argument("--no-builtin", action="store_true", help="Delphi 10.4 Win32 기본 심볼을 켜지 않는다")

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
