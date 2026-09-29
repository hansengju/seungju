# -*- coding: utf-8 -*-
"""dlens 회귀 시험 — 합성 코드만 쓴다(회사 소스 복사 금지).

각 시험은 실제로 틀렸던 판정 유형을 재현한다.
  1차: 2026-09 세션 오보(주석·DFM·if 분기 안 패치 등)
  2차: 반증 시험 워크플로(wf_37381f61)가 D:\\K 2,151개 파일에서 찾은 도구 결함 23건의 유형
  python tests/test_dlens.py      → 끝에 PASS / FAIL n
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import dlens  # noqa: E402

PAS = r"""unit uFixture;

interface

{$IFNDEF UNICODE}
  {$DEFINE USESET}
{$ENDIF}

type
  TFoo = class(TForm)
    procedure btn_RegClick(Sender: TObject);
  end;
  EMine = class(Exception);
  TJ = class
    class function Parse<T: record>(const S: string): T;
  end;
  TProcRef = reference to procedure;
  TRec = record
    a: Integer;
    case Integer of
      0: (b: Integer);
  end;
  CP_Send = function(pName: PAnsiChar; nSize: Double{Integer}; nMode: Integer): Integer;

implementation

procedure TFoo.btn_RegClick(Sender: TObject);
var
  s, sBic: string;
  LocalVarLine: Integer;
begin
  s := '{ 문자열 안 중괄호 }';
  CallAfterString;
  { 블록주석 시작
    ShowMessage('debug');
  블록주석 끝 }
  (*
    validCheckData_TR_FXD0037(DataSet);
  *)
  // LineCommented;
  {$IFDEF DEBUG}
  DebugOnly;
  {$ELSE}
  ReleaseOnly;
  {$ENDIF}
  {$IFDEF USESET}
  SetOnly;
  {$ENDIF}
  {$IFNDEF USESET}
  NoSetOnly;
  {$ENDIF}
  if sBic = '' then
  begin
    InsideBicEmpty;
  end;
  AfterBicBlock;
  if s = 'x' then
    SingleBody;
  if s = 'z' then
    ContinuedCall(1,
      ContinuationArg);
  for nChk := 2 to 5 do
    if s = 'w' then
    begin
      InsideForIf;
    end;
  case nChk of
    1:
      CaseLabelBody;
  end;
  if s = 'y' then Exit;
  StillReachable;
  try
    TryBody;
    Exit;
  finally
    FinallyReachable;
  end;
  try
    raise Exception.Create(
      'multi line message' + s);
  except
    ExceptReachable;
  end;
  while True do
  begin
    Break;
    DeadAfterBreak;
  end;
  begin
    raise Exception.Create(
      'arg line is not dead');
    DeadAfterRaise;
  end;
  begin
    Exit;
    DeadAfterExit;
  end;
  {$IFDEF DEBUG}
  if s = 'dbg' then
  {$ELSE}
  if s = 'rel' then
  {$ENDIF}
  begin
    BranchBody;
  end;
  {$IFDEF DEBUG}
  if s = 'only dbg' then
  {$ELSE}
  ElseBranchStmt;
  {$ENDIF}
  if Assigned(s) then
    R1 := 1
  else
  {$IFDEF WIDEX}
    R2 := 2
  {$ELSE}
    ElseBranchOnly := 3
  {$ENDIF};
  case nChk of
    7:
      {$IFDEF NGX}
      NgBody;
      {$ELSE}
      NonNgBody;
      {$ENDIF}
  end;
  {$IFDEF PASSX}
  if s = 'p' then
  {$ENDIF}
    MaybeBody;
  {$IFDEF CPUX64}
  X64Only;
  {$ELSE}
  X86Only;
  {$ENDIF}
  if s = 'e' then X := 1
  else ElseLineStmt := 2;
  if s = 't'
  then ThenLineStmt := 1;
  if s = 'q' then
  begin
    E1;
  end else EndElseStmt := True;
  try
    if s = 'f' then
      TryIfBody;
  finally // FinAfterIf
    FinBody;
  end;
  case nChk of
    1: One;
  else
    CaseElse1;
    CaseElse2;
  end;
  if s = 'd' then
  begin
    Exit;
  end else AfterEndElse;
  begin
    Exit;
  end; // LoneEndAfterExit
  try
    Exit;
  finally // FinKw
    FinKeywordBody;
  end;
  Foo; { 꼬리 주석 }
end;

function AsmFunc: Integer;
asm
  MOV EAX, 1
end;

procedure AfterAsm;
var
  AfterAsmVar: Integer;
begin
  AfterAsmBody;
end;

procedure WithLabel;
label Lbl;
begin
  goto Lbl;
  Exit;
  DeadBeforeLabel;
Lbl:
  AfterLabel;
end;

procedure Outer;
  procedure Inner;
  begin
    InnerBody;
  end;
begin
  OuterBody;
end;

end.
"""

PAS_UNBAL = r"""unit uUnbal;

interface

implementation

procedure UnbalancedA;
begin
{$IFDEF DBGX}
  if a then begin
{$ELSE}
  if b then begin
{$ENDIF}
    Xx;
  end;
end;

procedure AfterUnbalanced;
begin
  AfterUnbalancedBody;
end;

end.
"""

DFM = """object frmFoo: TfrmFoo
  Left = 0
  object pnlTop: TPanel
    Left = 0
    inline frame_CNTY_CD: TFrameEdit
      Left = 8
      inherited Edt: TcxButtonEdit
        Left = 0
        Properties.OnEditValueChanged = btn_RegClick
      end
    end
    object btn_Reg: TcxButton
      OnClick = btn_RegClick
    end
  end
end
"""


def line_no(text, needle):
    for i, l in enumerate(text.split("\n"), 1):
        if needle in l:
            return i
    raise AssertionError("fixture 에 없음: " + needle)


def main():
    tmp = tempfile.mkdtemp(prefix="dlens_")
    pas = os.path.join(tmp, "uFixture.pas")
    open(pas, "wb").write(PAS.replace("\n", "\r\n").encode("cp949"))  # 실제 D:\K 처럼 cp949 + CRLF
    dfm = os.path.join(tmp, "uFixture.dfm")
    open(dfm, "wb").write(DFM.replace("\n", "\r\n").encode("cp949"))

    s = dlens.Src(pas)
    L = lambda needle: line_no(PAS, needle)  # noqa: E731
    lab = lambda needle, src=s: src.classify(L(needle))[0]  # noqa: E731
    nest = lambda needle, src=s: src.nesting(L(needle))  # noqa: E731

    cases = []

    def check(name, got, want):
        cases.append((name, got == want, got, want))

    # ── 1차: 세션 오보 유형 ──
    check("블록주석 { } 안 ShowMessage", lab("ShowMessage('debug')"), "블록주석 { }")
    check("(* *) 안 validCheckData", lab("validCheckData_TR_FXD0037"), "블록주석 (* *)")
    check("// 라인주석", lab("// LineCommented"), "라인주석 //")
    check("문자열 안 { 뒤 코드는 활성", lab("CallAfterString"), "활성")
    ln_s = L("s := '{ 문자열 안 중괄호 }'")
    lab_s, det_s = s.classify(ln_s, s.pos_of(ln_s, s.lines[ln_s - 1].index("문자열")))
    check("문자열 안 매치 → 활성 + 설명", (lab_s, "문자열 리터럴 안" in det_s), ("활성", True))
    lab_d, det_d = s.classify(L("DebugOnly"))
    check("{$IFDEF DEBUG} 값 미상 → 활성·조건부", (lab_d, "조건부" in det_d), ("활성", True))
    s_rel = dlens.Src(pas, undefs=["DEBUG"])
    check("--undef DEBUG → DebugOnly 비활성", lab("DebugOnly", s_rel), "조건부 비활성")
    check("--undef DEBUG → ReleaseOnly 활성", lab("ReleaseOnly", s_rel), "활성")
    s_dbg = dlens.Src(pas, defines=["DEBUG"])
    check("--define DEBUG → ReleaseOnly 비활성", lab("ReleaseOnly", s_dbg), "조건부 비활성")
    chain_in = nest("InsideBicEmpty")[0]
    check("InsideBicEmpty 는 if sBic='' 안", any("if" in d and "sBic = ''" in d for _b, d in chain_in), True)
    check("AfterBicBlock 은 if 밖(routine 직속)", [d.split(":")[0] for _b, d in nest("AfterBicBlock")[0]], ["routine 본문"])
    check("SingleBody 는 if 단문 본문", bool((nest("SingleBody;")[1] or "").startswith("if")), True)
    check("if..then Exit 뒤 StillReachable 활성", lab("StillReachable"), "활성")
    check("Exit; 뒤 DeadAfterExit 도달불가", lab("DeadAfterExit"), "도달불가 추정")
    check("routine 머리 = 정의/선언", "정의/선언" in s.classify(L("procedure TFoo.btn_RegClick"))[1], True)
    check("블록 균형(underflow 0, 끝 깊이 0)", (s.underflow, s.final_depth), (0, 0))
    check("중첩 routine Inner 본문 인식", any("Inner" in d for _b, d in nest("InnerBody")[0]), True)
    check("Outer 본문 인식", any("본문: Outer" in d for _b, d in nest("OuterBody")[0]), True)
    check("Foo; { 꼬리 } → 활성·줄 일부 주석", "줄 일부 주석" in s.classify(L("Foo; {"))[1], True)
    check("cp949 판정", s.info["enc"], "cp949")

    # ── 2차: 반증 시험에서 나온 결함 유형 ──
    # (a) 조건부 안의 {$DEFINE} — 10.4 는 UNICODE 기본 → USESET 은 정의 안 됨
    #     건너뛴 DEFINE 의 심볼은 '없음' 이 아니라 '모름'(프로젝트 옵션이 정의할 수 있다) → 확정하지 않는다
    lab_b, det_b = s.classify(L("SetOnly"))
    check("기본심볼: 꺼진 분기의 DEFINE 는 적용 안 함 → SetOnly 값 미상", (lab_b, "미상" in det_b), ("활성", True))
    s_u = dlens.Src(pas, undefs=["USESET"])
    check("--undef USESET: 꺼진 DEFINE 가 덮어쓰지 않음 → SetOnly 비활성", lab("SetOnly", s_u), "조건부 비활성")
    check("--undef USESET: NoSetOnly 활성", lab("NoSetOnly", s_u), "활성")
    s_nu = dlens.Src(pas, undefs=["UNICODE"], builtin=False)
    check("UNICODE 끔 → DEFINE 적용 → NoSetOnly 비활성", lab("NoSetOnly", s_nu), "조건부 비활성")
    check("UNICODE 끔 → SetOnly 확정 활성(미상 아님)", s_nu.classify(L("SetOnly")), ("활성", ""))
    s_nb = dlens.Src(pas, builtin=False)
    lab_nb, det_nb = s_nb.classify(L("SetOnly"))
    check("--no-builtin: SetOnly 는 값 미상(확정 금지)", (lab_nb, "미상" in det_nb), ("활성", True))
    # (b) 여러 줄 raise/Exit 문장의 인자 줄은 도달불가가 아니다
    check("raise 인자 연속줄은 활성", lab("'arg line is not dead'"), "활성")
    check("raise 문장 끝난 뒤 DeadAfterRaise 도달불가", lab("DeadAfterRaise"), "도달불가 추정")
    # (c) try..finally / try..except 절은 Exit·raise 뒤에도 도달한다
    check("Exit 뒤 finally 절 활성", lab("FinallyReachable"), "활성")
    check("raise 뒤 except 절 활성", lab("ExceptReachable"), "활성")
    check("try 안 raise 인자 줄 활성", lab("'multi line message'"), "활성")
    # (d) Break 뒤 도달불가
    check("Break; 뒤 DeadAfterBreak 도달불가", lab("DeadAfterBreak"), "도달불가 추정")
    # (e) begin 줄 자체는 단문 본문이 아니다
    check("if 다음 begin 줄은 단문 본문 아님", s.nesting(L("if sBic = ''") + 1)[1], None)
    # (f) 단문 머리 연쇄: for .. do if .. then begin 안
    chain_fi = [d for _b, d in nest("InsideForIf")[0]]
    check("for→if 단문 머리 연쇄가 감싼 구조에 나온다", any("단문 머리 for" in d for d in chain_fi), True)
    # (g) 여러 줄 문장의 연속줄도 단문 본문으로 판정
    single_c = nest("ContinuationArg")[1] or ""
    check("연속줄 → 단문 본문(if) + 연속줄 표시", single_c.startswith("if") and "연속줄" in single_c, True)
    # (h) case 라벨 본문
    check("case 라벨 본문", (nest("CaseLabelBody")[1] or "").startswith("case 라벨"), True)
    # (i) routine 선언부(var 절)는 최상위가 아니다
    check("var 절 줄 → routine 선언부", any("선언부: TFoo.btn_RegClick" in d for _b, d in nest("LocalVarLine")[0]), True)
    # (j) 중첩 routine 안 → 바깥 routine 선언부도 나온다
    check("Inner 본문 안 → Outer 선언부 포함", any("선언부: Outer" in d for _b, d in nest("InnerBody")[0]), True)
    # (k) 조건부 분기가 섞인 머리 — 분기를 정하면 그 분기 머리
    hdr_dbg = [d for _b, d in s_dbg.nesting(L("BranchBody"))[0]]
    hdr_rel = [d for _b, d in s_rel.nesting(L("BranchBody"))[0]]
    check("--define DEBUG → 머리 if s = 'dbg'", any("'dbg'" in d for d in hdr_dbg), True)
    check("--undef DEBUG → 머리 if s = 'rel'", any("'rel'" in d for d in hdr_rel), True)
    check("분기 미정이면 [주의] 표시", s.nesting(L("BranchBody"))[2], True)
    check("분기를 정하면 [주의] 없음", s_dbg.nesting(L("BranchBody"))[2], False)
    # (k-2) {$ELSE} 분기의 독립 문장을 {$IFDEF} 분기 if 의 단문 본문으로 보지 않는다
    single_x = s.nesting(L("ElseBranchStmt"))[1] or ""
    check("다른 분기의 머리는 단문 머리로 쓰지 않음", single_x.startswith("아님"), True)
    # (l) reference to procedure / 타입 선언은 routine 으로 세지 않는다
    check("reference to procedure 는 routine 아님", all("TProcRef" not in n for n, _l in s.routines), True)

    # ── 3차: 반증 시험 2차(wf_89eb42c8)에서 나온 결함 유형 ──
    single_eb = nest("ElseBranchOnly")[1] or ""
    check("else 분기 줄: else 머리, 연속줄 표시 없음", single_eb.startswith("else") and "연속줄" not in single_eb, True)
    check("case 라벨 + 조건부 분기 → case 라벨 유지", (nest("NonNgBody")[1] or "").startswith("case 라벨"), True)
    check("미상 분기의 머리 → [주의]", nest("MaybeBody")[2], True)
    check("Win32: CPUX64 분기 확정 비활성", lab("X64Only"), "조건부 비활성")
    check("Win32: X86Only 확정 활성(미상 아님)", s.classify(L("X86Only")), ("활성", ""))
    check("else 로 시작하는 줄 → else 본문", (nest("ElseLineStmt")[1] or "").startswith("else"), True)
    check("then 으로 시작하는 줄 → if 본문", (nest("ThenLineStmt")[1] or "").startswith("if"), True)
    check("end else 문장 → else 본문", (nest("EndElseStmt")[1] or "").startswith("else"), True)
    check("finally 줄은 앞 if 의 연속줄이 아님", nest("// FinAfterIf")[1], None)
    check("case else 목록 두 번째 문장", (nest("CaseElse2")[1] or "").startswith("case else 목록"), True)
    check("Exit 뒤 end else 문장은 활성", lab("AfterEndElse"), "활성")
    check("Exit 뒤 단독 end; 는 도달불가 아님", lab("// LoneEndAfterExit"), "활성")
    check("Exit 뒤 finally 키워드 줄 활성", lab("// FinKw"), "활성")
    check("asm 본문 routine 뒤 선언부 누수 없음",
          [d for _b, d in nest("AfterAsmVar")[0]], ["routine 선언부: AfterAsm (머리 %d행)" % L("procedure AfterAsm")])
    check("goto 레이블 뒤 활성", lab("AfterLabel"), "활성")
    check("goto 레이블 앞 Exit 뒤는 도달불가", lab("DeadBeforeLabel"), "도달불가 추정")
    check("제네릭 <T: record> 는 record 블록 아님", any("record 선언" in d for _b, d in nest("AfterAsmBody")[0]), False)
    ub = os.path.join(tempfile.mkdtemp(prefix="dlens_ub_"), "uUnbal.pas")  # callers 범위 시험과 섞이지 않게 별도 폴더
    open(ub, "wb").write(PAS_UNBAL.replace("\n", "\r\n").encode("cp949"))
    su = dlens.Src(ub)
    Lu = lambda needle: line_no(PAS_UNBAL, needle)  # noqa: E731
    check("분기별 begin 수 다름 → 불균형 경고", bool(su.nesting(Lu("AfterUnbalancedBody"))[3]), True)
    check("end. 가 남은 블록을 삼키지 않음(끝 깊이>0)", su.final_depth > 0, True)
    su_d = dlens.Src(ub, defines=["DBGX"])
    check("분기를 정하면 균형·경고 없음", (su_d.final_depth, bool(su_d.nesting(Lu("AfterUnbalancedBody"))[3])), (0, False))

    # ── CLI 경유 ──
    py = sys.executable
    tool = os.path.join(HERE, "..", "scripts", "dlens.py")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    run = lambda *args: subprocess.run([py, tool] + list(args), capture_output=True, env=env).stdout.decode("utf-8")  # noqa: E731
    out = run("dfm", dfm, "frame_CNTY_CD")
    check("DFM inline frame_CNTY_CD 발견", "inline frame_CNTY_CD: TFrameEdit" in out, True)
    out2 = run("dfm", dfm, "Edt")
    check("DFM inherited Edt 부모 경로", "frame_CNTY_CD" in out2 and "inherited Edt" in out2, True)
    out3 = run("callers", "btn_RegClick", tmp)
    check("callers 범위 표기", "[범위] 파일 2개" in out3, True)
    check("callers DFM OnClick 배선", "OnClick = btn_RegClick" in out3 and out3.count("[DFM 이벤트 배선]") == 2, True)
    out4 = run("grep", "ShowMessage|validCheckData", tmp)
    check("grep 결과에 주석 라벨", "블록주석 { }" in out4 and "블록주석 (* *)" in out4, True)
    out5 = run("grep", "NoSuchThing", tmp)
    check("0건이면 범위 한정 문구", "범위 안에 이 텍스트가 없다는 뜻일 뿐" in out5, True)
    # (m) 한 줄의 첫 매치가 주석이어도 뒤 매치가 코드면 활성
    out6 = run("grep", r"\bInteger\b", pas)
    line6 = [l for l in out6.splitlines() if "CP_Send" in l]
    check("첫 매치 주석·뒤 매치 코드 → 활성", bool(line6) and "[활성" in line6[0], True)
    # (n) 시그니처 안 타입 참조는 '정의/선언' 이 아니다
    out7 = run("grep", r"\bTObject\b", pas)
    line7 = [l for l in out7.splitlines() if "TFoo.btn_RegClick" in l]
    check("시그니처 안 TObject → 선언 시그니처 안 참조", bool(line7) and "선언 시그니처 안 참조" in line7[0], True)

    fails = 0
    for name, ok, got, want in cases:
        print("%s  %s%s" % ("OK  " if ok else "FAIL", name, "" if ok else "   got=%r want=%r" % (got, want)))
        fails += 0 if ok else 1
    print("\n%d/%d 통과 → %s" % (len(cases) - fails, len(cases), "PASS" if fails == 0 else "FAIL %d" % fails))
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
