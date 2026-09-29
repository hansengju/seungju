# D:\K 와 주변 드라이브 지도

확인일 2026-09-29. `〔경로 …〕` 는 `scripts/verify_refs.py` 가 존재 여부를 다시 확인한다.
경로에는 **공백이 있다**(`81. Framework`, `90. Program`). 공백을 빼면 없는 경로가 된다.

## D:\K — 영업점 CS 업무화면 (Delphi 10.4 VCL)

| 폴더 | 내용 |
|---|---|
| `D:\K\90. Program\03. PT\<업무>\<화면ID(이름)>\source\` | 화면 소스. 업무: APP BCA EXC FUN FUP HRW OPT PAY POS REC REP SET 〔경로 D:/K/90. Program/03. PT/EXC(외환수출입)〕 |
| `D:\K\90. Program\05. Popup\<팝업ID(이름)>\source\` | 팝업. 화면이 `gPopup.Popup.LoadForm(self, 'T<폼>', '', '<팝업ID>')` 로 띄운다 〔경로 D:/K/90. Program/05. Popup/EXC0102020_01(해외대량송금신청수정)/source〕 |
| `D:\K\90. Program\05. Popup\POPUPMODULE\source\uFileIO.pas` | 공통 엑셀 업로드 팝업(TfFileIO) 〔경로 D:/K/90. Program/05. Popup/POPUPMODULE/source/uFileIO.pas〕 |
| `D:\K\02. Library\TRLib\uTrTransList.pas` | 전문(TR_FXD…) 송수신 함수 모음, 약 3만 줄 〔경로 D:/K/02. Library/TRLib/uTrTransList.pas〕 |
| `D:\K\02. Library\dcp\` | 런타임 패키지 .bpl/.dcp. 예: `branchVCL\branchVCLDR27.bpl` 〔경로 D:/K/02. Library/dcp/branchVCL/branchVCLDR27.dcp〕 |
| `D:\K\90. Program\03. PT\pg_*.groupproj` | 업무별 프로젝트 그룹 〔경로 D:/K/90. Program/03. PT/pg_PAY(자금지급).groupproj〕 |

빌드 PC 에서는 같은 트리가 `K:\` 로 보일 수 있다(사용자 제공 dir 결과, 이 PC 에서는 D:\K).

## 주변 드라이브 (역할만 — 상세는 메모리 reference_cms_domain.md)

| 드라이브 | 역할 |
|---|---|
| `D:\X` | 프레임워크. SEED256 `81. Framework\18. Crypto\source\uFrame.Crypto.Seed256.pas` 〔경로 D:/X/81. Framework/18. Crypto/source/uFrame.Crypto.Seed256.pas〕, DB 계층 `81. Framework\01. Library\uApp.DBMS.pas` 〔경로 D:/X/81. Framework/01. Library/uApp.DBMS.pas〕 |
| `D:\Y` | 자기완결형 스케줄 정의·실행(CMS Agent) 〔경로 D:/Y/91. Program Utility/100. Agent〕 |
| `D:\U` | 은행별 exe 저장소 — 스케줄 엔진 아님 〔경로 D:/U〕 |
