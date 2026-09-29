# EXC 송금 3종: 대량당발송금(EXC0109010) · 해외대량송금(EXC0102020) · 수정 팝업(EXC0102020_01)

확인일 2026-09-29 (dlens · 원문). 줄 번호는 이날 기준 — 쓰기 전에 `scripts/verify_refs.py`.
세 파일은 **공통 모듈이 아니다.** 요건이 같아도 파일마다 따로 넣고, 파일마다 따로 확인한다.

[@A]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.pas
[@B]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.pas
[@P]: D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.pas

## 주요 함수

| | 당발 @A | 대량 @B |
|---|---|---|
| MT 행 검증 | 〔@A:1977 "function TfrmEXC0109010.ValidityCheck_FEXCEL_MT"〕 | 〔@B:1981 "function TfrmEXC0102020.ValidityCheck_FEXCEL_MT"〕 |
| MX 행 검증 | 〔@A:2893 "function TfrmEXC0109010.ValidityCheck_FEXCEL_MX"〕 | 〔@B:3044 "function TfrmEXC0102020.ValidityCheck_FEXCEL_MX"〕 |
| 등록(차단 지점) | 〔@A:4345 "procedure TfrmEXC0109010.btn_RegClick"〕 | 〔@B:4494 "procedure TfrmEXC0102020.btn_RegClick"〕 |
| 수정 팝업 호출 | 〔@A:10065 "LoadForm(self, 'TfrmEXC0102020_01'"〕 | 〔@B:11487 "LoadForm(self, 'TfrmEXC0102020_01'"〕 |

팝업은 저장 전에 MT/MX 각각 검사하고 `MsgWarning` + `Exit` 로 막는다.

## 2026-09 MX 제약 요건 반영 현황

| 요건 | 당발 @A | 대량 @B | 팝업 @P |
|---|---|---|---|
| 수취은행 국가 CU/IR/KP 차단 (MT·MX) | 〔@A:2325 "미국 금융제재국가 및 SDN"〕 〔@A:3302 "미국 금융제재국가 및 SDN"〕 | 〔@B:2579 "미국 금융제재국가 및 SDN"〕 〔@B:3809 "미국 금융제재국가 및 SDN"〕 | 〔@P:1129 "미국 금융제재국가 및 SDN"〕 〔@P:1709 "미국 금융제재국가 및 SDN"〕 |
| 인도면 수취인 전화번호 필수 | 〔@A:3246 "수취인 전화번호는 필수 입력 항목입니다"〕 | 〔@B:3320 "수취인 전화번호는 필수 입력 항목입니다"〕 | 해당 없음 — 전화번호 입력칸이 없다 |
| 인도면 목적코드 P+숫자4 | 〔@A:3836 "송금 목적 코드는 반드시 대문자"〕 | 〔@B:3358 "송금 목적 코드는 반드시 대문자"〕 | **검사는 있으나 예전 문구** 〔@P:1322 "수취인거주국가가 인도(IN)인 경우 수취인앞지시사항은"〕 〔@P:1923 "수취인거주국가가 인도(IN)인 경우 수취인앞지시사항은"〕 |
| NCS 에 INFSC(11) 인정 | 〔@A:6487 "'INFSC') and (iLength = 11)"〕 | 〔@B:7559 "'INFSC') and (iLength = 11)"〕 | 〔@P:2076 "'INFSC') and (iLength = 11)"〕 |
| 인도 NCS 11자리(바이트) | 〔@A:3438 "인도의 은행 코드는 무조건 11자리"〕 〔@A:3615 "인도의 은행 코드는 무조건 11자리"〕 | 〔@B:3861 "인도의 은행 코드는 무조건 11자리"〕 | **미반영** (2026-09-29 발견) |
| SBIN(State Bank of India)이면 BIC 11자리 | 〔@A:3539 "= 'SBIN'"〕 | 〔@B:3676 "= 'SBIN'"〕 | **미반영** — BIC 는 최대 35자 검사만 〔@P:1106 "Length(WideString(frame_BIC_CD.Edt.Text)) > 35"〕 |
| BIC 있을 때 NCS 금지 | 해제(2026-09-29 사용자 결정) — 길이·형식 검사만 남김 〔@A:3411 "NCS 코드 데이터의 길이제한범위[33]"〕 | 원래 금지 없음 | 원래 금지 없음 |

## 화면별 메모

- 당발 `showmessage` 3곳은 전부 죽은 코드 — 5277 은 `{ }` 블록주석 안, 6765/6766 은 `//`.
  〔@A:5277 "showmessage(tv_RegSongGeumList"〕 (dlens live → 블록주석 { } 5265~5278행)
- 대량 `validCheckData_TR_FXD0037` 호출은 `(* *)` 안(죽은 코드). 살아 있는 검증 경로는 `ValidityCheck_FEXCEL_*`.
  〔@B:4512 "if Not validCheckData_TR_FXD0037 Then"〕
- 대량 수취인 전화번호: 그리드 컬럼 〔@B:325 "cxGridDBColumnRMTE_TEL_NO"〕, FieldDefs 〔@B:520 "Add('RMTE_TEL_NO'"〕,
  ERP SELECT 〔@B:11228 "AA.RMTE_TEL_NO"〕, 전문 송신 〔@B:4903 "Data['RMTE_TEL_NO'"〕.
  엑셀 양식에 열 추가는 사용자가 직접 한다(2026-09-29 합의).
- 팝업 국가코드 `frame_CNTY_CD` 는 DFM 에 `inline` 으로 선언돼 있다(object 로만 찾으면 "없다" 가 나온다).
  〔D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.dfm:696 "inline frame_CNTY_CD: TFrameEdit"〕
- 당발 등록 목록 그리드의 국가코드 컬럼 편집 잠금(`Options.Editing = False`)은 사용자 승인 대기 중(2026-09-29 기준).
