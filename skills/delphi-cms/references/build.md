# 빌드 오류 절차 (Delphi 10.4, dcc32)

## 원칙

원인을 말하기 전에 **컴파일 로그 전문**을 받는다. 경고 목록 일부나 IDE 팝업 한 줄로 추측하지 않는다.
2026-09 세션에서 F2613 원인을 로그 없이 "파일 없음 → K: 미매핑 → designide → 설계시 전용 패키지"
순으로 네 번 틀렸다. 로그 전문을 받은 뒤에야 확정됐다(pitfalls #6).

## 순서

1. 로그 전문에서 **첫 Fatal/Error 줄**을 인용한다(파일·줄·코드).
2. 같은 로그의 **dcc32 명령줄**을 찾아 `-LU<패키지;...>` 목록과 `-U`/`-I`(검색 경로)를 뽑는다.
3. F2613 `Unit 'X' not found` 이면:
   - X 가 **런타임 패키지 안의 유닛**인가? → 그 패키지가 `-LU` 목록에 있는지 본다.
   - 없으면 원인은 검색 경로가 아니라 **패키지 목록 누락**이다.
4. 사용자 PC 에서 파일 존재를 확인할 때는 `dir` 결과 원문을 받는다(이 PC 의 D:\K 와 빌드 PC 의 K:\ 는 다를 수 있다).

## F2613 `ubcGridCrypt` 사례 (2026-09)

- `ubcGridCrypt` 는 `branchVCLDR27` 패키지 소속. 이 PC 에도 있다 〔경로 D:/K/02. Library/dcp/branchVCL/branchVCLDR27.dcp〕
- dcc32 `-LU` 목록(259개)에 `branchVCLDR27` 이 없었다 → 해결:
  Project > Options > **Packages**(좌측 트리의 별도 노드, Delphi Compiler 페이지 안이 아님) > **Runtime packages** >
  Target 을 **"All configurations - All platforms"** 로 두고 `branchVCLDR27` 추가.
- .dproj 의 `DCC_UsePackage` 는 PropertyGroup 체인(Base → Base_Win32 → Cfg_1_Win32)으로 `$(DCC_UsePackage)` 를 상속한다.
  한 구성에만 넣으면 다른 구성 빌드에서 빠진다.
