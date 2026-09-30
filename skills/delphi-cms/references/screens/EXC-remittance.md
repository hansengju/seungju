# EXC 송금 3종: 대량당발송금(EXC0109010) · 해외대량송금(EXC0102020) · 수정 팝업(EXC0102020_01)

확인일 2026-09-30 (dlens · 원문). 줄 번호는 이날 기준 — 쓰기 전에 `scripts/verify_refs.py`.
세 파일은 **공통 모듈이 아니다.** 요건이 같아도 파일마다 따로 넣고, 파일마다 따로 확인한다.

[@A]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.pas
[@B]: D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.pas
[@P]: D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.pas

## 주요 함수

| | 당발 @A | 대량 @B |
|---|---|---|
| MT 행 검증 | 〔@A:1977 "function TfrmEXC0109010.ValidityCheck_FEXCEL_MT"〕 | 〔@B:1981 "function TfrmEXC0102020.ValidityCheck_FEXCEL_MT"〕 |
| MX 행 검증 | 〔@A:2893 "function TfrmEXC0109010.ValidityCheck_FEXCEL_MX"〕 | 〔@B:3044 "function TfrmEXC0102020.ValidityCheck_FEXCEL_MX"〕 |
| 등록(차단 지점) | 〔@A:4346 "procedure TfrmEXC0109010.btn_RegClick"〕 | 〔@B:4487 "procedure TfrmEXC0102020.btn_RegClick"〕 |
| 수정 팝업 호출 | 〔@A:10066 "LoadForm(self, 'TfrmEXC0102020_01'"〕 | 〔@B:11480 "LoadForm(self, 'TfrmEXC0102020_01'"〕 |

팝업은 저장 전에 MT/MX 각각 검사하고 `MsgWarning` + `Exit` 로 막는다.

## 인도 요건 반영 현황 (2026-09-30 : 트리거를 '수취인거주국가 IN' → '송금통화 INR' 로 전환, MX 만)

요건(사용자 지시): 통화 INR 이면 ① 수취인 전화번호 필수 ② NCS 필수 = INFSC + IFSC 11자리, BIC 와 동시 입력 가능,
수취은행 식별은 "NCS + BIC" 또는 "NCS + 은행명 + 은행주소(도시명 필수)" ③ 수취인앞지시사항1 = P + 숫자 4자리.
SBIN 검사는 통화와 무관하게 세 파일 MX 에 유지. 팝업 MT 에는 인도 전용 검사가 없다(2026-09-30 제거, 사용자 결정).
검증 : 원문 시뮬레이션 37건에서 오늘 편집 때문에 요건과 어긋나거나 세 파일이 갈리는 칸 0건(검토 워크플로, 에이전트 결과 — 핵심 줄은 원문 재확인).

| 요건 | 당발 @A | 대량 @B | 팝업 @P |
|---|---|---|---|
| 통화를 읽는 곳 | 전역 gCur_Cd (ERP 경로는 검증 시점 행 CUR_CD 가 빈 값) 〔@A:3018 "sTmp := gCur_Cd.Trim;"〕 | 행 CUR_CD 〔@B:3317 "FieldByName( 'CUR_CD' ).AsString.Trim ) = 'INR'"〕 | 콤보 EditValue 〔@P:1759 "VarToStrDef( frame_CUR_CD.cmb.EditValue, '' ) ) ) = 'INR'"〕 |
| 수취은행 국가 CU/IR/KP 차단 (MT·MX, 통화 무관) | 〔@A:2325 "미국 금융제재국가 및 SDN"〕 〔@A:3302 "미국 금융제재국가 및 SDN"〕 | 〔@B:2579 "미국 금융제재국가 및 SDN"〕 〔@B:3802 "미국 금융제재국가 및 SDN"〕 | 〔@P:1127 "미국 금융제재국가 및 SDN"〕 〔@P:1693 "미국 금융제재국가 및 SDN"〕 |
| ① INR 이면 전화 필수 | 〔@A:3243 "gCur_Cd.Trim ) = 'INR'"〕 〔@A:3246 "수취인 전화번호는 필수 입력 항목입니다"〕 | 〔@B:3320 "수취인 전화번호는 필수 입력 항목입니다"〕 | 해당 없음 — 전화 입력칸이 없고 수정 전문에도 RMTE_TEL_NO 를 넣지 않는다 |
| ② INR 이면 NCS 필수 + INFSC + 11자리 | BIC 없음 분기 〔@A:3427 "gCur_Cd.Trim ) = 'INR' ) and"〕(빈 값은 기존 〔@A:3370 "NCS 코드 중 하나는 필수"〕) · BIC 있음 분기 〔@A:3609 "( sNcsBody = '' ) or ( Copy( sNcsBody, 1, 5 ) <> 'INFSC' )"〕 | 분기 밖 한 곳 〔@B:3847 "( sNcsBody = '' ) or ( Copy( sNcsBody, 1, 5 ) <> 'INFSC' )"〕 | 〔@P:1763 "( sNcsBody = '' ) or ( Copy( sNcsBody, 1, 5 ) <> 'INFSC' )"〕 |
| ② 11자리(바이트) 문구 | 〔@A:3439 "인도의 은행 코드는 무조건 11자리"〕 〔@A:3616 "인도의 은행 코드는 무조건 11자리"〕 | 〔@B:3854 "인도의 은행 코드는 무조건 11자리"〕 | 〔@P:1772 "인도의 은행 코드는 무조건 11자리"〕 |
| ② BIC 없으면 은행명·주소 필수 (통화 무관, 기존) | 은행명 〔@A:3324 "수취인거래은행BIC 또는 수취인거래은행명은 필수"〕 + NCS 있으면 상세주소·거리명·도시명(NM3~5) 필수 〔@A:3380 "수취인거래은행상세주소는 필수"〕 | 은행명 〔@B:3539 "수취은행BIC 또는 수취은행명은 필수"〕 · 국가 〔@B:3561 "수취은행 국가코드 필수"〕 · 도시명 〔@B:3629 "수취은행BIC 또는 수취은행도시명은 필수"〕 | 도시명·국가 〔@P:1516 "수취은행 도시명은 필수 입력 항목입니다"〕 · 은행명 〔@P:1986 "수취은행BIC 또는 수취은행명은 필수"〕 |
| ② BIC 있을 때 은행명·주소 | 입력 금지(기존) 〔@A:3624 "BIC 정보가 있는경우 수취인거래은행명은 입력할 수 없습니다"〕 | 허용(4칸 모두면 등록 때 안내만) | 허용(안내만) |
| ③ INR 이면 목적코드 P+숫자4 | 〔@A:3823 "gCur_Cd.Trim ) = 'INR' ) then"〕 〔@A:3837 "송금 목적 코드는 반드시 대문자"〕 | 〔@B:3344 "FieldByName( 'CUR_CD' ).AsString.Trim ) = 'INR' ) then"〕 〔@B:3358 "송금 목적 코드는 반드시 대문자"〕 | 〔@P:1915 "frame_CUR_CD.cmb.EditValue, '' ) ) ) = 'INR' ) Then"〕 〔@P:1931 "송금 목적 코드는 반드시 대문자"〕 |
| NCS 형식표에 INFSC(11) 인정 | 〔@A:6488 "'INFSC') and (iLength = 11)"〕 | 〔@B:7552 "'INFSC') and (iLength = 11)"〕 | 〔@P:2083 "'INFSC') and (iLength = 11)"〕 |
| SBIN 이면 BIC 11자리 (MX, 통화 무관) | 〔@A:3540 "= 'SBIN'"〕 | 〔@B:3669 "= 'SBIN'"〕 (2026-09-30 복원) | 〔@P:1669 "= 'SBIN'"〕 |

**INR 은 지금 세 화면 모두 통화 콤보에서 빠져 있다.** `setCombo` 가 제외 목록의 통화를 빼고 USD·JPY·EUR 만 다시 넣는다
〔@A:10505 "EGP|INR|ILS"〕 〔@B:11754 "EGP|INR|ILS"〕 〔@P:733 "EGP|INR|ILS"〕.
그래서 INR 행은 새 검사보다 먼저 '송금통화 값이 잘못되었습니다'(당발 〔@A:3060 "송금통화 값이 잘못되었습니다"〕 · 대량 〔@B:3448 "송금통화 값이 잘못되었습니다"〕)
또는 팝업 '송금통화를 선택하세요' 〔@P:1441 "송금통화를 선택하세요"〕 에서 걸린다. INR 허용 여부는 사용자 결정 사항이다(2026-09-30 질의).
당발 상단 콤보(FrameCUR_CD)는 setCombo 를 거치지 않아 INR 을 고를 수 있고, 막히는 곳은 검증의 cmb_CurCd 대조다.

## 화면별 메모

- 당발 `showmessage` 3곳은 전부 죽은 코드 — 5278 은 `{ }` 블록주석 안, 6766/6767 은 `//` (2026-09-30 줄 기준).
  〔@A:5278 "showmessage(tv_RegSongGeumList"〕 (dlens live → 블록주석 { })
- 대량 `validCheckData_TR_FXD0037` 호출은 `(* *)` 안(죽은 코드). 살아 있는 검증 경로는 `ValidityCheck_FEXCEL_*`.
  〔@B:4505 "if Not validCheckData_TR_FXD0037 Then"〕
- 대량 수취인 전화번호: 그리드 컬럼 〔@B:325 "cxGridDBColumnRMTE_TEL_NO"〕, FieldDefs 〔@B:520 "Add('RMTE_TEL_NO'"〕,
  ERP SELECT 〔@B:11221 "AA.RMTE_TEL_NO"〕, 전문 송신 〔@B:4896 "Data['RMTE_TEL_NO'"〕.
  엑셀 양식에 열 추가는 사용자가 직접 한다(2026-09-29 합의).
- 팝업 국가코드 `frame_CNTY_CD` 는 DFM 에 `inline` 으로 선언돼 있다(object 로만 찾으면 "없다" 가 나온다).
  〔D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source/uEXC0102020_01.dfm:696 "inline frame_CNTY_CD: TFrameEdit"〕
- 등록 목록 그리드(`tv_RegSongGeumList`)는 두 화면 모두 대부분 컬럼이 편집 가능한 설계다(뷰 OptionsData.Editing 기본값).
  국가코드(CNTY_CD) 컬럼만 대량이 잠겨 있었고 〔D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0102020(해외대량송금신청)/source/uEXC0102020.dfm:2948 "Options.Editing = False"〕,
  당발도 같게 잠갔다(2026-09-29) 〔D:/K/90. Program/03. PT/EXC(외환수출입)/EXC0109010(대량당발송금신청)/source/uEXC0109010.dfm:3479 "Options.Editing = False"〕.
