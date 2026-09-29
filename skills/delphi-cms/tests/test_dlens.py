# -*- coding: utf-8 -*-
"""dlens 회귀 시험 — 합성 코드만 쓴다(회사 소스 복사 금지).

각 시험은 이번 세션에서 실제로 틀렸던 판정 유형을 재현한다.
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

type
  TFoo = class(TForm)
    procedure btn_RegClick(Sender: TObject);
  end;
  EMine = class(Exception);
  TRec = record
    a: Integer;
    case Integer of
      0: (b: Integer);
  end;

implementation

procedure TFoo.btn_RegClick(Sender: TObject);
var
  s, sBic: string;
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
  if sBic = '' then
  begin
    InsideBicEmpty;
  end;
  AfterBicBlock;
  if s = 'x' then
    SingleBody;
  if s = 'y' then Exit;
  StillReachable;
  begin
    Exit;
    DeadAfterExit;
  end;
  Foo; { 꼬리 주석 }
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

DFM = """object frmFoo: TfrmFoo
  Left = 0
  object pnlTop: TPanel
    Left = 0
    inline frame_CNTY_CD: TFrameEdit
      Left = 8
      inherited Edt: TcxButtonEdit
        Left = 0
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
    lab = lambda needle: s.classify(L(needle))[0]  # noqa: E731

    cases = []

    def check(name, got, want):
        cases.append((name, got == want, got, want))

    # 1) 오보#1 유형: { } 블록주석 안의 호출
    check("블록주석 { } 안 ShowMessage", lab("ShowMessage('debug')"), "블록주석 { }")
    # 2) (* *) 블록주석 안의 호출 (validCheckData 사례)
    check("(* *) 안 validCheckData", lab("validCheckData_TR_FXD0037"), "블록주석 (* *)")
    # 3) 라인주석
    check("// 라인주석", lab("// LineCommented"), "라인주석 //")
    # 4) 문자열 안 { 는 주석 시작이 아니다
    check("문자열 안 { 뒤 코드는 활성", lab("CallAfterString"), "활성")
    # 4-b) 매치가 문자열 리터럴 안이어도 그 줄은 살아 있는 코드다 (FieldByName('ERP_ERROR') 사례)
    ln_s = L("s := '{ 문자열 안 중괄호 }'")
    pos_s = s.pos_of(ln_s, s.lines[ln_s - 1].index("문자열"))
    lab_s, det_s = s.classify(ln_s, pos_s)
    check("문자열 안 매치 → 활성 + 설명", (lab_s, "문자열 리터럴 안" in det_s), ("활성", True))
    # 5) 조건부 — 심볼 값 모르면 활성+조건부 표기, 지정하면 비활성
    lab_d, det_d = s.classify(L("DebugOnly"))
    check("{$IFDEF DEBUG} 값 미상 → 활성·조건부", (lab_d, "조건부" in det_d), ("활성", True))
    s_rel = dlens.Src(pas, undefs=["DEBUG"])
    check("--undef DEBUG → DebugOnly 비활성", s_rel.classify(L("DebugOnly"))[0], "조건부 비활성")
    check("--undef DEBUG → ReleaseOnly 활성", s_rel.classify(L("ReleaseOnly"))[0], "활성")
    s_dbg = dlens.Src(pas, defines=["DEBUG"])
    check("--define DEBUG → ReleaseOnly 비활성", s_dbg.classify(L("ReleaseOnly"))[0], "조건부 비활성")
    # 6) 오보#5 유형: if sBic = '' 분기 안인지
    chain_in, _ = s.nesting(L("InsideBicEmpty"))
    check("InsideBicEmpty 는 if sBic='' 안", any("if" in d and "sBic = ''" in d for _b, d in chain_in), True)
    chain_out, _ = s.nesting(L("AfterBicBlock"))
    check("AfterBicBlock 은 if 밖(routine 직속)", [d.split(":")[0] for _b, d in chain_out], ["routine 본문"])
    # 7) begin 없는 단문 본문
    _c, single = s.nesting(L("SingleBody;"))
    check("SingleBody 는 if 단문 본문", bool(single and "if" in single), True)
    # 8) 조건부 Exit 뒤는 도달 가능, 직접 Exit 뒤는 도달불가
    check("if..then Exit 뒤 StillReachable 활성", lab("StillReachable"), "활성")
    check("Exit; 뒤 DeadAfterExit 도달불가", lab("DeadAfterExit"), "도달불가 추정")
    # 9) 정의 vs 참조
    lab_def, det_def = s.classify(L("procedure TFoo.btn_RegClick"))
    check("routine 머리 = 정의/선언", "정의/선언" in det_def, True)
    # 10) class(Exception); 전방 선언과 variant record 가 구조를 깨지 않는다
    check("블록 균형(underflow 0, 끝 깊이 0)", (s.underflow, s.final_depth), (0, 0))
    chain_inner, _ = s.nesting(L("InnerBody"))
    check("중첩 routine Inner 본문 인식", any("Inner" in d for _b, d in chain_inner), True)
    chain_outer, _ = s.nesting(L("OuterBody"))
    check("Outer 본문 인식", any("Outer" in d and "Inner" not in d for _b, d in chain_outer), True)
    # 11) 줄 일부 주석
    check("Foo; { 꼬리 } → 활성·줄 일부 주석", "줄 일부 주석" in s.classify(L("Foo; {"))[1], True)
    # 12) 인코딩
    check("cp949 판정", s.info["enc"], "cp949")

    # 13) 오보#7 유형: DFM inline / inherited 도 찾는다 (CLI 경유)
    py = sys.executable
    tool = os.path.join(HERE, "..", "scripts", "dlens.py")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    out = subprocess.run([py, tool, "dfm", dfm, "frame_CNTY_CD"], capture_output=True, env=env).stdout.decode("utf-8")
    check("DFM inline frame_CNTY_CD 발견", "inline frame_CNTY_CD: TFrameEdit" in out, True)
    out2 = subprocess.run([py, tool, "dfm", dfm, "Edt"], capture_output=True, env=env).stdout.decode("utf-8")
    check("DFM inherited Edt 부모 경로", "frame_CNTY_CD" in out2 and "inherited Edt" in out2, True)
    # 14) callers: 정의 / 활성 참조 / 주석 / DFM 배선 구분 + 범위 표기
    out3 = subprocess.run([py, tool, "callers", "btn_RegClick", tmp], capture_output=True, env=env).stdout.decode("utf-8")
    check("callers 범위 표기", "[범위] 파일 2개" in out3, True)
    check("callers DFM 이벤트 배선 구분", "DFM 이벤트 배선" in out3, True)
    out4 = subprocess.run([py, tool, "grep", "ShowMessage|validCheckData", tmp], capture_output=True, env=env).stdout.decode("utf-8")
    check("grep 결과에 주석 라벨이 붙는다", "블록주석 { }" in out4 and "블록주석 (* *)" in out4, True)
    out5 = subprocess.run([py, tool, "grep", "NoSuchThing", tmp], capture_output=True, env=env).stdout.decode("utf-8")
    check("0건이면 범위 한정 문구", "범위 안에 이 텍스트가 없다는 뜻일 뿐" in out5, True)

    fails = 0
    for name, ok, got, want in cases:
        print("%s  %s%s" % ("OK  " if ok else "FAIL", name, "" if ok else "   got=%r want=%r" % (got, want)))
        fails += 0 if ok else 1
    print("\n%d/%d 통과 → %s" % (len(cases) - fails, len(cases), "PASS" if fails == 0 else "FAIL %d" % fails))
    return fails


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
