# EXC 송금 3종: 대량당발송금(EXC0109010) · 해외대량송금(EXC0102020) · 수정 팝업(EXC0102020_01)

확인일 2026-09-30 (dlens · 원문). 줄 번호는 이날 기준 — 쓰기 전에 `scripts/verify_refs.py`.
세 파일은 **공통 모듈이 아니다.** 요건이 같아도 파일마다 따로 넣고, 파일마다 따로 확인한다.

[@A]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.pas
[@B]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.pas
[@P]: D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.pas

## 주요 함수

| | 당발 @A | 대량 @B |
|---|---|---|
| MT 행 검증 | 〔@A:1977 "function TfrmEXC0109010.ValidityCheck_FEXCEL_MT"〕 | 〔@B:1982 "function TfrmEXC0102020.ValidityCheck_FEXCEL_MT"〕 |
| MX 행 검증 | 〔@A:2893 "function TfrmEXC0109010.ValidityCheck_FEXCEL_MX"〕 | 〔@B:3045 "function TfrmEXC0102020.ValidityCheck_FEXCEL_MX"〕 |
| 등록(차단 지점) | 〔@A:4256 "procedure TfrmEXC0109010.btn_RegClick"〕 | 〔@B:4420 "procedure TfrmEXC0102020.btn_RegClick"〕 |
| 수정 팝업 호출 | 〔@A:10048 "LoadForm(self, 'TfrmEXC0102020_01'"〕 | 〔@B:11486 "LoadForm(self, 'TfrmEXC0102020_01'"〕 |

팝업은 저장 전에 MT/MX 각각 검사하고 `MsgWarning` + `Exit` 로 막는다.

## 인도 요건 반영 현황 (2026-10-07 최종 : 대량·당발은 등록 버튼 경고, 팝업은 항목별 개별 안내)

요건(사용자 지시) : ① 수취인 전화번호 ② 수취인앞지시사항1 = P + 숫자 4자리 ③ NCS = INFSC + IFSC 11자리 — 송금통화 INR **또는 수취인 국가 IN 또는 수취은행 국가 IN** 일 때(2026-10-07 사용자 결정, 세 화면 공통 — 수취은행 국가 = 대량 CNTY_CD · 당발 THR_CNTY_CD · 팝업 frame_CNTY_CD),
④ 수취은행이 STATE BANK OF INDIA 면 BIC 11자리 — 통화 무관. MX 만.
**대량·당발** : 행 검증(ValidityCheck_FEXCEL_MX)의 인도 검사는 2026-10-07 에 모두 뺐다(사용자 결정 "기존 밸리드 체크 버리고").
`btn_RegClick` 의 '소재국가가 다른 송금 건' 확인 루프(2026.05.22 무역사기 예방) 안에서 체크된 행마다 중첩 함수 `IsIndiaRuleNg` 로 보고,
한 건이라도 어긋나면 고정 안내문(머리 문구 + 4줄, 행 번호 없음)을 `MsgWarning` 후 `Exit` — 등록 중단(사용자 결정). 소재국가 확인창보다 먼저 뜬다.
SBI 판단 = BIC 앞 4자리 SBIN **또는** 은행명에 STATE BANK OF INDIA(공백 무시) — 당발은 BIC 가 있으면 은행명 입력이 금지라 은행명만으로는 8자리 SBIN BIC 를 못 잡는다.
**팝업** : 하나씩 따로 안내(MsgWarning + Exit). 1차 수정본(.bak.20261007_2 : 최종 문구 + SBI 은행명 조건)에 '수취인 국가 IN' 조건을 더했다.
팝업 통화 콤보는 INR 을 제외하므로(setCombo 제외 목록 + Items.Assign) INR 건은 '송금통화를 선택하세요' 에서 먼저 막힌다 → 팝업에서 인도 검사가 실제로 도는 것은 수취인 국가 IN 건.
(2026-10-07 사고 : '기존 백업버전으로' 를 오늘 수정 전 백업으로 해석해 SBI 은행명 조건까지 되돌렸다가 사용자 지적으로 1차 수정본으로 복구.)

| 항목 | 당발 @A (btn_RegClick) | 대량 @B (btn_RegClick) | 팝업 @P (저장 전 개별 경고) |
|---|---|---|---|
| 확인 함수 | 〔@A:4274 "function IsIndiaRuleNg : Boolean;"〕 | 〔@B:4437 "function IsIndiaRuleNg : Boolean;"〕 | — |
| 통화·수취인 국가를 읽는 곳 | 전역 gCur_Cd 〔@A:4289 "gCur_Cd.Trim ) = 'INR'"〕 | 행 CUR_CD 〔@B:4452 "FieldByName( 'CUR_CD' ).AsString.Trim ) = 'INR'"〕 | 콤보 〔@P:1761 "VarToStrDef( frame_CUR_CD.cmb.EditValue, '' ) ) ) = 'INR'"〕 |
| ④ SBI (통화 무관) | 은행명 RMTE_TRSC_BNK_NM1 〔@A:4283 "= 'SBIN' ) or"〕 | 은행명 RCVG_BNK_NM1 〔@B:4446 "= 'SBIN' ) or"〕 | 은행명 frame_RCVG_BNK_NM1 〔@P:1670 "= 'SBIN' ) or"〕 |
| 대상 판정(MX + 필드 존재) | 〔@A:4358 "bIndiaChk := ( Frame_RdoGroup.rdoGrp.ItemIndex <> 0 )"〕 | 〔@B:4576 "bIndiaChk := ( Frame_RdoGroup.rdoGrp.ItemIndex <> 0 )"〕 | — |
| 루프 안 확인(체크 행) | 〔@A:4383 "if bIndiaChk and ( not bIndiaNg ) and IsIndiaRuleNg then"〕 | 〔@B:4602 "if bIndiaChk and ( not bIndiaNg ) and IsIndiaRuleNg then"〕 | — |
| 경고 후 중단 | 〔@A:4396 "if bIndiaNg then"〕 〔@A:4402 "BIC 11 자리 필수';"〕 | 〔@B:4615 "if bIndiaNg then"〕 〔@B:4621 "BIC 11 자리 필수';"〕 | NCS 〔@P:1767 "( sNcsBody = '' ) or ( Copy( sNcsBody, 1, 5 ) <> 'INFSC' )"〕 · 목적 〔@P:1921 "( UpperCase( Trim( frame_CNTY_CD.Edt.Text ) ) = 'IN' ) Then"〕 |
| 수취은행 국가 CU/IR/KP 차단 (MT·MX, 통화 무관, 행 검증 유지) | 〔@A:2325 "미국 금융제재국가 및 SDN"〕 〔@A:3289 "미국 금융제재국가 및 SDN"〕 | 〔@B:2580 "미국 금융제재국가 및 SDN"〕 〔@B:3756 "미국 금융제재국가 및 SDN"〕 | 〔@P:1127 "미국 금융제재국가 및 SDN"〕 〔@P:1695 "미국 금융제재국가 및 SDN"〕 |
| NCS 형식표에 INFSC(11) 인정 (행 검증 유지) | 〔@A:6470 "'INFSC') and (iLength = 11)"〕 | 〔@B:7558 "'INFSC') and (iLength = 11)"〕 | 〔@P:2089 "'INFSC') and (iLength = 11)"〕 |
| BIC 없으면 은행명·주소 필수 (통화 무관, 기존) | 은행명 〔@A:3311 "수취인거래은행BIC 또는 수취인거래은행명은 필수"〕 | 은행명 〔@B:3504 "수취은행BIC 또는 수취은행명은 필수"〕 | 은행명 〔@P:1992 "수취은행BIC 또는 수취은행명은 필수"〕 |
| BIC 있을 때 은행명·주소 | 입력 금지(기존) 〔@A:3557 "BIC 정보가 있는경우 수취인거래은행명은 입력할 수 없습니다"〕 | 허용(안내만) | 허용(안내만) |

경고 문구(대량·당발 동일, 사용자 양식 그대로) : '수취인 국가가 인도인 경우 아래의 투입사항을 확인 후 거래하시기 바랍니다.' 아래
'- 수취인 전화번호 필수' / '- 수취인앞 지시사항에 송금목적 (P+4자리숫자) 필수' / '- NCS 정보 : INFSC + 11자리' / '- 수취은행이 STATE BANK OF INDIA 일 경우 BIC 11 자리 필수'.
**2026-10-07 사고** : 빌드 PC(K:) IDE 쪽에서 당발 .pas 가 9/30 편집 전 내용으로 바뀌어 INR 조건이 사라져 있었다 → 다시 적용한 뒤 같은 날 등록 버튼 방식으로 옮김. pitfalls #12.

**INR 은 팝업에서만 막히고, 대량·당발은 통과한다** (2026-10-06 정정 — 9/30 에 "세 화면 모두 막힌다" 고 적은 것은 틀렸다).
세 파일 모두 `setCombo` 에 같은 제외 목록이 있지만 〔@A:10487 "EGP|INR|ILS"〕 〔@B:11760 "EGP|INR|ILS"〕 〔@P:733 "EGP|INR|ILS"〕,
걸러 낸 목록을 원래 콤보에 되돌려 쓰는 것은 팝업뿐이다 〔@P:784 "cmb1.Properties.Items.Assign(cmb2.Properties.Items)"〕.
대량·당발의 setCombo 에는 되돌려 쓰기가 없다(파일 안 `Items.Assign` 0건) → 검증이 대조하는 cmb_CurCd 에 INR 이 남아 통과한다
〔@B:3404 "if sTmp = cmb_CurCd.Properties.Items[j].Value then"〕. 실제 10/06 개발계 로그에서 INR 건이 등록 전문으로 나갔다.
팝업은 INR 이 콤보에 없어 '송금통화를 선택하세요' 에서 막힌다 〔@P:1441 "송금통화를 선택하세요"〕 → **INR 건은 수정 팝업으로 수정·저장할 수 없다.**
→ "막힌다/통과한다" 는 제외 목록만 보지 말고 걸러 낸 결과가 어느 콤보에 들어가는지까지 확인한다(pitfalls 유형: 증거 범위보다 강한 말).

## 화면별 메모

- 당발 `showmessage` 3곳은 전부 죽은 코드 — 5278 은 `{ }` 블록주석 안, 6766/6767 은 `//` (2026-09-30 줄 기준).
  〔@A:5260 "showmessage(tv_RegSongGeumList"〕 (dlens live → 블록주석 { })
- 대량 `validCheckData_TR_FXD0037` 호출은 `(* *)` 안(죽은 코드). 살아 있는 검증 경로는 `ValidityCheck_FEXCEL_*`.
  〔@B:4486 "if Not validCheckData_TR_FXD0037 Then"〕
- 대량 수취인 전화번호: 그리드 컬럼 〔@B:326 "cxGridDBColumnRMTE_TEL_NO"〕, FieldDefs 〔@B:521 "Add('RMTE_TEL_NO'"〕,
  ERP SELECT 〔@B:11227 "AA.RMTE_TEL_NO"〕, 전문 송신 〔@B:4902 "Data['RMTE_TEL_NO'"〕.
  엑셀 양식에 열 추가는 사용자가 직접 한다(2026-09-29 합의).
- 팝업 국가코드 `frame_CNTY_CD` 는 DFM 에 `inline` 으로 선언돼 있다(object 로만 찾으면 "없다" 가 나온다).
  〔D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.dfm:696 "inline frame_CNTY_CD: TFrameEdit"〕
- 등록 목록 그리드(`tv_RegSongGeumList`)는 두 화면 모두 대부분 컬럼이 편집 가능한 설계다(뷰 OptionsData.Editing 기본값).
  국가코드(CNTY_CD) 컬럼만 대량이 잠겨 있었고 〔D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.dfm:2958 "Options.Editing = False"〕,
  당발도 같게 잠갔다(2026-09-29) 〔D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.dfm:3479 "Options.Editing = False"〕.
