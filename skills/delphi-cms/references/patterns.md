# 공통 패턴 (EXC 송금 화면 기준, 다른 업무도 같은 틀인 경우가 많다 — 화면마다 확인)

확인일 2026-09-29. `〔@X:줄 "문자열"〕` 는 그 줄에 그 문자열이 있어야 한다(`scripts/verify_refs.py`).

[@A]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.pas
[@B]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.pas
[@P]: D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.pas

## 1. 행 오류 표시 → 등록 버튼에서 차단 (두 단계)

- 검증 함수 안의 **중첩 프로시저 `SetError`** 가 현재 행에 `ERP_ERROR='Y'` 를 쓰고 메시지를 쌓는다.
  〔@A:2004 "FieldByName( 'ERP_ERROR' ).AsString := 'Y'"〕 〔@B:3076 "FieldByName( 'ERP_ERROR' ).AsString := 'Y'"〕
- 검증 함수는 **그 자리에서 막지 않는다.** 반환값이 항상 True 여도 설계상 정상이다(오보 #2).
- 차단은 **`btn_RegClick`** 이 선택 행 중 `ERP_ERROR='Y'` 를 보면 경고 후 `Exit`.
  〔@A:4462 "FieldByName('ERP_ERROR').AsString='Y'"〕 〔@A:4465 "Exit;"〕
  〔@B:4651 "FieldByName('ERP_ERROR').AsString='Y'"〕 〔@B:4654 "Exit;"〕
- 따라서 "송금 실행 단계에 재검증이 없다" 는 것만으로는 위험이 아니다 — 등록(차단) → 파일 생성 → 실행 체인이다(오보 #3).
- **단, 등록 시점 재검증은 없다**(등록 버튼 안 재검증 호출은 주석 〔@B:4506 "if Not validCheckData_TR_FXD0037 Then"〕).
  그래서 오류 표시가 지워지면 통과한다. 대량에서 확인된 클라이언트 경로(2026-09-29 시뮬레이션 발견·원문 확인):
  자동 버튼이 **체크와 무관하게 모든 행**의 오류 표시를 지우고 〔@B:885 "FieldByName('ERP_ERROR').AsString :=''"〕
  검증은 **체크된 행만** 다시 표시한다 〔@B:3140 "if DataSet.FieldByName('CHK').AsString = 'Y' then"〕
  → 오류 행 체크 해제 → 자동 → 다시 체크 → 등록 순서면 오류 표시 없이 등록 검사를 통과한다(체크 변경 시 재검증 이벤트 없음).
  서버(TR_FXD0037) 쪽 재검증은 미확인.
  당발(EXC0109010) 에도 같은 경로가 있다(2026-09-30 원문 확인): 자동 버튼이 CHK 조건 없는 루프에서 모든 행 표시를 지우고
  〔@A:737 "FieldByName('ERP_ERROR').AsString :=''"〕 검증은 체크 행만 〔@A:2986 "if DataSet.FieldByName('CHK').AsString = 'Y' then"〕,
  등록은 표시만 본다 〔@A:4462 "FieldByName('ERP_ERROR').AsString='Y'"〕.
  당발은 추가로 import 그리드의 NCS 칸이 잠겨 있지 않아(DFM 에 Options.Editing 없음) 검증 뒤 셀을 고쳐도 다시 검증하지 않는다
  〔D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.dfm:1609 "object cxGridDBColumnRMTE_TRSC_BNK_CD1"〕
  (대량은 잠김 〔D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.dfm:434 "Options.Editing = False"〕).
  → "등록까지 못 간다" 고 단정하지 말고 "일반 흐름에서는 등록이 막는다 · 위 순서는 예외 · 서버는 미확인" 으로 말한다.

## 2. 팝업의 차단 관용구

```pascal
sMessage := '...';
iiCom.iMsg.MsgWarning(self, iiCom.iLang.GetCodeMessage(sMessage, []), iiCom.iMsg.GetMsgTitle(self));
Exit;
```
팝업(EXC0102020_01)은 행 표시가 아니라 이 방식으로 저장을 막는다. 〔@P:1123 "frame_CNTY_CD.Edt.Text"〕

## 3. 검증 함수가 불리는 경로 (대량송금 MX 기준)

`callers ValidityCheck_FEXCEL_MX` 결과(2026-09-29): 활성 호출 3곳 — **자동 버튼·엑셀·ERP**.
- 자동 버튼 `btn_AutoClick`(DFM OnClick 배선됨) 〔@B:898 "ValidityCheck_FEXCEL_MX"〕
- 엑셀 가져오기 〔@B:1179 "ValidityCheck_FEXCEL_MX()"〕
- ERP 가져오기 〔@B:8384 "ValidityCheck_FEXCEL_MX"〕
- `(* *)` 안의 옛 호출은 죽은 코드 〔@B:4511 "ValidityCheck_FEXCEL_MX('3')"〕
→ 검증 로직을 **함수 안에** 넣으면 세 경로에 모두 적용된다.

## 4. 수정 팝업은 "등록된 목록" 을 받는다

두 화면 모두 `btnModifyClick` 에서 같은 팝업을 띄우고 **`tv_RegSongGeumList`(등록 목록 그리드)** 를 넘긴다.
〔@A:10069 "Params.Data['tv_RegSongGeumList'].AsObject := tv_RegSongGeumList"〕
〔@B:11485 "Params.Data['tv_RegSongGeumList'].AsObject := tv_RegSongGeumList"〕
→ 팝업은 **엑셀/ERP 에서 가져온 오류 행을 고치는 곳이 아니다**(오보 #8). 등록이 끝난 건의 수정 화면이다.
→ 다만 팝업에서 값을 바꿀 수 있으므로 등록 화면과 **같은 검증을 팝업에도** 넣어야 한다(제재국가·INFSC 등).

## 5. 엑셀 업로드 매핑

- 공통 팝업 `TfFileIO`(uFileIO.pas) 가 파일을 읽고, 화면의 **그리드 컬럼 순서**로 매핑한다.
  새 필드를 넣으면 그리드 컬럼 위치 = 엑셀 열 위치가 된다.
- FieldDefs 에 필드 추가 + `Tag := 9` 는 **비필수**(엑셀에 열이 없어도 오류 아님) 표시.
  〔@B:589 "FieldByName('RMTE_TEL_NO'           ).Tag := 9"〕

## 6. 전문 매핑 (MX)

화면 필드 → 전문 항목 (당발 MX 전송부 기준):
- 수취은행명 `RMTE_TRSC_BNK_NM1` → `MX_RCVG_BNK_NM` 〔@A:4839 "Data['MX_RCVG_BNK_NM'"〕,
  은행주소 `NM3/NM4/NM5` → `RCVG_BNK_ADR1/2/3` 〔@A:4840 "Data['RCVG_BNK_ADR1'"〕
- NCS `RMTE_TRSC_BNK_CD1` → `MX_BNK_SETL_RCGN_CD` = 앞 5자, `MX_BNK_SETL_RCGN_CTT` = 6번째부터 28자
  〔@A:4843 "COPY(DataSet.FieldByName('RMTE_TRSC_BNK_CD1'"〕 〔@A:4844 "Data['MX_BNK_SETL_RCGN_CTT'"〕
  (그래서 인도 IFSC 는 `INFSC` + 11자리로 넣는다.)
- BIC 가 있을 때 은행명(NM1~4)을 함께 보내면 전문 오류 — 기존 주석이 근거 〔@A:3315 "RMTE_TRSC_BNK_NM1,2,3,4 값 전문 전송 시 오류"〕.
  NCS 는 별도 항목이라 이 주석의 대상이 아니다 → BIC 와 NCS 는 동시 입력 가능(2026-09-29 사용자 결정으로 금지 해제).
- 전문 함수 본문은 `uTrTransList.pas` 〔D:/K/02. Library/TRLib/uTrTransList.pas:27674 "function TR_FXD0037"〕
  〔D:/K/02. Library/TRLib/uTrTransList.pas:28585 "function TR_FXD0132"〕
- 대량송금 전화번호 송신 〔@B:4897 "Data['RMTE_TEL_NO'"〕
