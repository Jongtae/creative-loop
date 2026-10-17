# Creative Loop 구현 계획 인덱스

plan-v1.2 / 2026-10-17 / 총괄 [#7](https://github.com/Jongtae/creative-loop/issues/7).
**57개 MVP 필수 + 3개 선택 확장 = 60개 세부 이슈**. 모두 계획 등록 상태이며 코드·실제 테스트·MVP 품질의 완료를 뜻하지 않는다. 기존 #1–#6과 main 코드는 보존한다.

## 읽는 순서

[MVP 목표/합격선](MVP_ACCEPTANCE.md) → [Terra medium 실행 규칙](EXECUTION.md) → [전체 구조](ARCHITECTURE_V1.md) → [입출력 계약 C01–C11](CONTRACTS.md) → [목표별 테스트/증거](TEST_MATRIX.md) → [기계 판독 계획/DAG](plan.json) → **선택한 이슈 하나**.

`.codex/config.toml`은 구현/계획/리뷰의 모델·effort 기본값을 지정한다. 실제 클라이언트/조직/override 적용값은 실행시 확인해야 한다. 제품 이미지 생성엔진과 구현 모델은 별개다.

## 실행 순서의 원칙

설계 PR 병합 후 **CL-001(#8)**부터 시작한다. 이후 번호순이 아니라 plan.json의 직접 선행 조건이 완료된 core 이슈를 선택한다. 예를 들어 CL-005는 CL-007을 기다려야 한다. CL-059 합격검사기는 초기에 수행할 수 있다. CL-031/037/038은 삭제hook을 위해 CL-033도 선행한다.

원격 이슈번호는 아래 실제 링크를 사용하며 번호가 CL+7이라는 산식을 앞으로 추가되는 이슈에 가정하지 않는다. merged 코드 증거와 외부 gate 증거를 구분한다. 미충족 gate는 blocked_external로 남기고 독립 core만 진행한다. extension은 L2 검증 뒤 선택 실행하며 native GitHub Projects/자동 sub-issue 그래프를 만들었다고 가정하지 않는다. 이 문서와 plan.json이 실행 관계의 기준이다.

## 기반·브랜드·안전 실행

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-001 / #8](https://github.com/Jongtae/creative-loop/issues/8) | 실행 규칙·의존성 검사·회귀 기준 |
| [CL-002 / #9](https://github.com/Jongtae/creative-loop/issues/9) | SQLite 순차 migration·기존 데이터 보존 |
| [CL-003 / #10](https://github.com/Jongtae/creative-loop/issues/10) | RGBA 원본·투명도·파생 이미지 |
| [CL-004 / #11](https://github.com/Jongtae/creative-loop/issues/11) | 목적별 사용권·만료·철회·provenance |
| [CL-005 / #12](https://github.com/Jongtae/creative-loop/issues/12) | BrandKit 버전/CRUD |
| [CL-006 / #13](https://github.com/Jongtae/creative-loop/issues/13) | 브랜드 편집·브리프 연결 UI |
| [CL-007 / #14](https://github.com/Jongtae/creative-loop/issues/14) | 설정·오류·로그·공통 API 경계 |
| [CL-008 / #15](https://github.com/Jongtae/creative-loop/issues/15) | Job 저장·멱등성·lease |
| [CL-009 / #16](https://github.com/Jongtae/creative-loop/issues/16) | Worker·heartbeat·취소/복구 |
| [CL-010 / #17](https://github.com/Jongtae/creative-loop/issues/17) | 요금표·견적·원자 비용 예약 |
| [CL-011 / #18](https://github.com/Jongtae/creative-loop/issues/18) | 공급자 Protocol/capability |
| [CL-012 / #19](https://github.com/Jongtae/creative-loop/issues/19) | OpenAI 생성·편집·구조화 응답 |
| [CL-013 / #20](https://github.com/Jongtae/creative-loop/issues/20) | 승인 API·예산·권한·실행 연결 |

## 실제 디자인 제작·편집·내보내기

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-014 / #21](https://github.com/Jongtae/creative-loop/issues/21) | 브랜드 잠금 콘셉트 계획 |
| [CL-015 / #22](https://github.com/Jongtae/creative-loop/issues/22) | BatchPlan·자식 이미지 jobs·부분완료 |
| [CL-016 / #23](https://github.com/Jongtae/creative-loop/issues/23) | 콘셉트/이미지 별도 승인·진행 UI |
| [CL-017 / #24](https://github.com/Jongtae/creative-loop/issues/24) | SceneDocument v2·legacy 변환 |
| [CL-018 / #25](https://github.com/Jongtae/creative-loop/issues/25) | SVG 렌더링·한글 bounds·레이아웃 조합 |
| [CL-019 / #26](https://github.com/Jongtae/creative-loop/issues/26) | 원자 ScenePatch·CAS·revision·undo |
| [CL-020 / #27](https://github.com/Jongtae/creative-loop/issues/27) | 레이어·드래그·속성 편집 UI |
| [CL-021 / #28](https://github.com/Jongtae/creative-loop/issues/28) | 마스크 API·원본 좌표·합성 |
| [CL-022 / #29](https://github.com/Jongtae/creative-loop/issues/29) | 브러시·확대·전후 비교 UI |
| [CL-023 / #30](https://github.com/Jongtae/creative-loop/issues/30) | 브랜드/문구/가독성 lint·fact review |
| [CL-024 / #31](https://github.com/Jongtae/creative-loop/issues/31) | 자연어 교정→검증된 patch 제안 |
| [CL-025 / #32](https://github.com/Jongtae/creative-loop/issues/32) | 동일 revision SVG/PNG/JSON/ZIP |

## 허가된 데이터 수집·삭제

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-026 / #33](https://github.com/Jongtae/creative-loop/issues/33) | **게이트:** 첫 소스 공식 API/권한/지표 계약 |
| [CL-027 / #34](https://github.com/Jongtae/creative-loop/issues/34) | ObservationV2·0/null·원자 import |
| [CL-028 / #35](https://github.com/Jongtae/creative-loop/issues/35) | SourceConfig·서버 credential reference |
| [CL-029 / #36](https://github.com/Jongtae/creative-loop/issues/36) | 읽기 전용 첫 소스 어댑터 |
| [CL-030 / #37](https://github.com/Jongtae/creative-loop/issues/37) | 미디어 fetch·SSRF/DNS/redirect 차단 |
| [CL-031 / #38](https://github.com/Jongtae/creative-loop/issues/38) | 증분 수집·checkpoint·재개 |
| [CL-032 / #39](https://github.com/Jongtae/creative-loop/issues/39) | 소스·지표 제공범위·최신성 UI |
| [CL-033 / #40](https://github.com/Jongtae/creative-loop/issues/40) | 삭제 전파·tombstone·복원 차단 |
| [CL-034 / #41](https://github.com/Jongtae/creative-loop/issues/41) | **게이트:** 실제30개 수집·3회 갱신 파일럿 |

## 특징·검색·근거 기반 생성

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-035 / #42](https://github.com/Jongtae/creative-loop/issues/42) | 관찰/추론/unknown 특징 schema |
| [CL-036 / #43](https://github.com/Jongtae/creative-loop/issues/43) | SigLIP2 어댑터·승인 설치·공간 분리 |
| [CL-037 / #44](https://github.com/Jongtae/creative-loop/issues/44) | 추출 job·버전 캐시·재추출 |
| [CL-038 / #45](https://github.com/Jongtae/creative-loop/issues/45) | 댓글 반응 대상·이유·불확실성 |
| [CL-039 / #46](https://github.com/Jongtae/creative-loop/issues/46) | 비교 가능 그룹·이벤트 빈도 |
| [CL-040 / #47](https://github.com/Jongtae/creative-loop/issues/47) | 권한 우선 하이브리드 검색·snapshot |
| [CL-041 / #48](https://github.com/Jongtae/creative-loop/issues/48) | 레퍼런스/근거 선택 UI |
| [CL-042 / #49](https://github.com/Jongtae/creative-loop/issues/49) | 근거를 콘셉트/이미지 조건에 연결 |

## 선택·학습·실험 준비

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-043 / #50](https://github.com/Jongtae/creative-loop/issues/50) | 브랜드/기술/다양성 분리 정렬 |
| [CL-044 / #51](https://github.com/Jongtae/creative-loop/issues/51) | revision 고정 A/B·동률·보류·이유 |
| [CL-045 / #52](https://github.com/Jongtae/creative-loop/issues/52) | dataset·group/time 분할·누출 방지 |
| [CL-046 / #53](https://github.com/Jongtae/creative-loop/issues/53) | 개인 쌍대 랭커·JSON artifact |
| [CL-047 / #54](https://github.com/Jongtae/creative-loop/issues/54) | 홀드아웃·승격/거부·규칙 fallback |
| [CL-048 / #55](https://github.com/Jongtae/creative-loop/issues/55) | 특징/검색/생성 benchmark·사람평가 수집기 |
| [CL-049 / #56](https://github.com/Jongtae/creative-loop/issues/56) | 최종 export와 실제 게시 결과 연결 |

## 보안·운영·최종 인수

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-052 / #59](https://github.com/Jongtae/creative-loop/issues/59) | 위협 모델·악성 입력·권한/비용 우회 회귀 |
| [CL-053 / #60](https://github.com/Jongtae/creative-loop/issues/60) | SQL 페이지네이션·환경 고정 성능 측정 |
| [CL-054 / #61](https://github.com/Jongtae/creative-loop/issues/61) | 설치/Docker·백업복원·실제 지원OS |
| [CL-055 / #62](https://github.com/Jongtae/creative-loop/issues/62) | 실제 HTTP 전체 제작 E2E·CI/시각 회귀 |
| [CL-056 / #63](https://github.com/Jongtae/creative-loop/issues/63) | **게이트:** 승인된 실제 AI·비용 파일럿 |
| [CL-057 / #64](https://github.com/Jongtae/creative-loop/issues/64) | **게이트:** 실제5과제·2명 품질/시간 평가 |
| [CL-059 / #66](https://github.com/Jongtae/creative-loop/issues/66) | 인수 증거 검사기; CL001 뒤 조기 구현 가능 |
| [CL-060 / #67](https://github.com/Jongtae/creative-loop/issues/67) | **게이트:** L2 MVP 최종 소유자 승인 |

## 선택 확장 — L2 필수 아님

| ID / 실제 이슈 | 작업 |
|---|---|
| [CL-050 / #57](https://github.com/Jongtae/creative-loop/issues/57) | Figma native layer import 파일럿 |
| [CL-051 / #58](https://github.com/Jongtae/creative-loop/issues/58) | 승인된 로컬 ComfyUI 공급자 |
| [CL-058 / #65](https://github.com/Jongtae/creative-loop/issues/65) | **게이트:** 실제 성과 실험·표본/인과 검증 |

## 기존 이슈와의 관계

기존 #1의 게시/HTTP 검증은 CL001/054/055, #2의 AI 파일럿은 CL011–025/056, #3 소스는 CL026–034, #4 특징은 CL035–041/048, #5 평가루프는 CL043–049/057–058, #6 도구/운영은 CL017–025/050–054와 연결된다. 이전 이슈를 자동 종료하거나 완료 상태를 재작성하지 않는다. 다중 사용자·Postgres·공개 SaaS는 이번 L2와 별도다.

## 계획 정합성

60개 ID/이슈번호 고유성, 없는 선행관계/순환 없음, core가extension을 필수 의존하지 않음, MVP15개 ID 범위와연결을검사한다. 이 검사는 계획 구조 검증이지60개 기능의 테스트 통과가 아니다. plan.json의 mvp_ids는주요연결이며 전체추적은MVP_ACCEPTANCE와TEST_MATRIX를함께본다. scripts/plan_status.py와check_mvp.py는각각CL001/059에서앞으로구현한다.
