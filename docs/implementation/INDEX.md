# 구현 계획 인덱스 — 병렬 자동화 v2

총괄 #7 · 설계 PR #68 · plan-v2-parallel · 68개(필수65·선택3).

기존60개 ID/이슈번호는 유지하고 CL-061/062와 AUTO-001~006을 추가했다.
[실행 계약](EXECUTION.md) · [병렬 설계](PARALLEL_EXECUTION.md) · [작업 DAG](plan.json) · [제품 계약](CONTRACTS.md) · [MVP 합격선](MVP_ACCEPTANCE.md) · [제품 테스트 표](TEST_MATRIX.md)

현재: 설계 및 dry-run 도구 반영. 지속 Codex 실행기/자동병합은 미구현·미시작이며 AUTO-005 실인수 전 완료라고 하지 않는다.
시작: CL-001 다음 CL-002/007/059와 AUTO-001을 독립 예약하여 병렬 실행. 이후 slot이 비면 DAG의 다음 준비된 작업을 채운다.

| 작업 | 이슈 | 영역 | 병합 선행 |
|---|---|---|---|
| CL-001 — 실행 규칙·의존성 검사·회귀 기준 | [#8](https://github.com/Jongtae/creative-loop/issues/8) | foundation / core | 없음 |
| CL-002 — SQLite 순차 마이그레이션과 데이터 보존 | [#9](https://github.com/Jongtae/creative-loop/issues/9) | foundation / core | CL-001 |
| CL-003 — 불변 원본·투명도·파생 이미지 | [#10](https://github.com/Jongtae/creative-loop/issues/10) | foundation / core | CL-002 |
| CL-004 — 목적별 사용권·만료·철회·provenance | [#11](https://github.com/Jongtae/creative-loop/issues/11) | foundation / core | CL-002 |
| CL-005 — BrandKit 버전 저장·CRUD API | [#12](https://github.com/Jongtae/creative-loop/issues/12) | brand / core | CL-003, CL-004, CL-007 |
| CL-006 — BrandKit 편집 화면·브리프 연결 | [#13](https://github.com/Jongtae/creative-loop/issues/13) | brand / core | CL-003, CL-005 |
| CL-007 — 설정·오류·로그·공통 API 경계 | [#14](https://github.com/Jongtae/creative-loop/issues/14) | foundation / core | CL-001 |
| CL-008 — 내구성 Job 저장·멱등 enqueue·lease | [#15](https://github.com/Jongtae/creative-loop/issues/15) | jobs / core | CL-002, CL-007 |
| CL-009 — Worker dispatch·heartbeat·복구 | [#16](https://github.com/Jongtae/creative-loop/issues/16) | jobs / core | CL-004, CL-008 |
| CL-010 — 요금표·견적·원자 비용 예약 원장 | [#17](https://github.com/Jongtae/creative-loop/issues/17) | jobs / core | CL-008 |
| CL-011 — AI 공급자 capability·응답 계약 | [#18](https://github.com/Jongtae/creative-loop/issues/18) | generation / core | CL-007 |
| CL-012 — OpenAI 생성·편집·구조화 응답 어댑터 | [#19](https://github.com/Jongtae/creative-loop/issues/19) | generation / core | CL-003, CL-004, CL-011 |
| CL-013 — Job 승인 API·예산·권한·공급자 연결 | [#20](https://github.com/Jongtae/creative-loop/issues/20) | jobs / core | CL-009, CL-010, CL-012 |
| CL-014 — 브랜드 고정 콘셉트 계획기 | [#21](https://github.com/Jongtae/creative-loop/issues/21) | generation / core | CL-005, CL-013 |
| CL-015 — 다중 이미지 BatchPlan·자식 job | [#22](https://github.com/Jongtae/creative-loop/issues/22) | generation / core | CL-014 |
| CL-016 — 생성 계획 승인·진행·부분 실패 UI | [#23](https://github.com/Jongtae/creative-loop/issues/23) | generation / core | CL-006, CL-015 |
| CL-017 — SceneDocument v2·legacy 변환 | [#24](https://github.com/Jongtae/creative-loop/issues/24) | scene / core | CL-003, CL-005 |
| CL-018 — 순수 Scene SVG renderer·한국어 text bounds | [#25](https://github.com/Jongtae/creative-loop/issues/25) | scene / core | CL-017 |
| CL-019 — ScenePatch·CAS·revision·undo/redo | [#26](https://github.com/Jongtae/creative-loop/issues/26) | scene / core | CL-018 |
| CL-020 — 레이어 편집 UI·잠금·드래그 | [#27](https://github.com/Jongtae/creative-loop/issues/27) | scene / core | CL-019 |
| CL-021 — 마스크 편집 계약·좌표·원본 보존 | [#28](https://github.com/Jongtae/creative-loop/issues/28) | scene / core | CL-013, CL-019 |
| CL-022 — 마스크 브러시 UI·미리보기·적용 | [#29](https://github.com/Jongtae/creative-loop/issues/29) | scene / core | CL-020, CL-021 |
| CL-023 — 브랜드·가독성·필수 문구 lint | [#30](https://github.com/Jongtae/creative-loop/issues/30) | scene / core | CL-018 |
| CL-024 — 자연어 교정→검증된 ScenePatch 제안 | [#31](https://github.com/Jongtae/creative-loop/issues/31) | scene / core | CL-013, CL-019, CL-023 |
| CL-025 — 동일 revision SVG·PNG·JSON 내보내기 | [#32](https://github.com/Jongtae/creative-loop/issues/32) | scene / core | CL-019, CL-023 |
| CL-026 — 최초 소스 공식 계약·권한 확인 게이트 | [#33](https://github.com/Jongtae/creative-loop/issues/33) | sources / core | CL-004 |
| CL-027 — ObservationV2·metric 정의·원자 import | [#34](https://github.com/Jongtae/creative-loop/issues/34) | sources / core | CL-002, CL-004, CL-007 |
| CL-028 — SourceConfig·credential reference·오프라인 계약 | [#35](https://github.com/Jongtae/creative-loop/issues/35) | sources / core | CL-027 |
| CL-029 — 읽기 전용 소스 Protocol·페이지 변환·비활성 어댑터 | [#36](https://github.com/Jongtae/creative-loop/issues/36) | sources / core | CL-028 |
| CL-030 — 소스 미디어 안전한 다운로드 | [#37](https://github.com/Jongtae/creative-loop/issues/37) | sources / core | CL-003, CL-028 |
| CL-031 — 증분 수집·checkpoint·scheduler | [#38](https://github.com/Jongtae/creative-loop/issues/38) | sources / core | CL-009, CL-029, CL-030, CL-033 |
| CL-032 — 소스 연결·수집 상태·freshness UI | [#39](https://github.com/Jongtae/creative-loop/issues/39) | sources / core | CL-031 |
| CL-033 — 삭제·철회 전파·복원 tombstone | [#40](https://github.com/Jongtae/creative-loop/issues/40) | sources / core | CL-003, CL-004, CL-008, CL-027 |
| CL-034 — 허가된 실제 소스 파일럿 게이트 | [#41](https://github.com/Jongtae/creative-loop/issues/41) | sources / core | CL-026, CL-031, CL-032, CL-033 |
| CL-035 — 시각·카피 의미 특징 schema·추출 | [#42](https://github.com/Jongtae/creative-loop/issues/42) | evidence / core | CL-003, CL-004, CL-013 |
| CL-036 — SigLIP2 임베딩 어댑터·버전 격리 | [#43](https://github.com/Jongtae/creative-loop/issues/43) | evidence / core | CL-003, CL-004, CL-035 |
| CL-037 — 특징 추출 job·캐시·재추출 | [#44](https://github.com/Jongtae/creative-loop/issues/44) | evidence / core | CL-009, CL-035, CL-036, CL-033 |
| CL-038 — 댓글 대상·감성·이유 분리 추출 | [#45](https://github.com/Jongtae/creative-loop/issues/45) | evidence / core | CL-013, CL-027, CL-035, CL-033 |
| CL-039 — 비교 가능한 cohort·반응 빈도 | [#46](https://github.com/Jongtae/creative-loop/issues/46) | evidence / core | CL-027 |
| CL-040 — 혼합 검색·EvidenceSnapshot | [#47](https://github.com/Jongtae/creative-loop/issues/47) | evidence / core | CL-033, CL-037, CL-038, CL-039 |
| CL-041 — 레퍼런스 검색·근거·불확실성 UI | [#48](https://github.com/Jongtae/creative-loop/issues/48) | evidence / core | CL-032, CL-040 |
| CL-042 — 근거→콘셉트/생성 조건 연결 | [#49](https://github.com/Jongtae/creative-loop/issues/49) | generation / core | CL-014, CL-040 |
| CL-043 — 품질·브랜드·다양성 분리 랭킹 | [#50](https://github.com/Jongtae/creative-loop/issues/50) | evaluation / core | CL-023, CL-040 |
| CL-044 — 랭킹 독립 revision 고정 A/B·tie·skip | [#51](https://github.com/Jongtae/creative-loop/issues/51) | evaluation / core | CL-019 |
| CL-045 — 평가 dataset·시간/중복 누수 없는 split | [#52](https://github.com/Jongtae/creative-loop/issues/52) | evaluation / core | CL-044 |
| CL-046 — 개인 선택 ranker·baseline·모델 artifact | [#53](https://github.com/Jongtae/creative-loop/issues/53) | evaluation / core | CL-045 |
| CL-047 — 홀드아웃 평가·승격/거부·fallback | [#54](https://github.com/Jongtae/creative-loop/issues/54) | evaluation / core | CL-046 |
| CL-048 — 품질 benchmark·ablation·사람 평가 수집 | [#55](https://github.com/Jongtae/creative-loop/issues/55) | evaluation / core | CL-025, CL-041, CL-042, CL-043, CL-044, CL-061, CL-062 |
| CL-049 — 게시 결과와 정확한 디자인 revision 연결 | [#56](https://github.com/Jongtae/creative-loop/issues/56) | evaluation / core | CL-027, CL-033, CL-044 |
| CL-050 — Figma native layer 가져오기 파일럿 | [#57](https://github.com/Jongtae/creative-loop/issues/57) | extensions / extension | CL-025 |
| CL-051 — ComfyUI 선택형 로컬 공급자 | [#58](https://github.com/Jongtae/creative-loop/issues/58) | extensions / extension | CL-013, CL-021 |
| CL-052 — 위협 모델·보안/권한/비용 회귀 | [#59](https://github.com/Jongtae/creative-loop/issues/59) | quality / core | CL-013, CL-024, CL-025, CL-030, CL-033, CL-038, CL-040 |
| CL-053 — SQL pagination·성능/자원 benchmark | [#60](https://github.com/Jongtae/creative-loop/issues/60) | quality / core | CL-025, CL-031, CL-040, CL-043 |
| CL-054 — 설치·Docker·backup/restore·지원 OS | [#61](https://github.com/Jongtae/creative-loop/issues/61) | quality / core | CL-025, CL-031, CL-033 |
| CL-055 — 실제 HTTP 수직 E2E·CI·시각 회귀 | [#62](https://github.com/Jongtae/creative-loop/issues/62) | quality / core | CL-016, CL-020, CL-022, CL-024, CL-025, CL-041, CL-044, CL-049, CL-052, CL-053, CL-054, CL-061, CL-062 |
| CL-056 — 실제 AI 생성·수정·비전 파일럿 게이트 | [#63](https://github.com/Jongtae/creative-loop/issues/63) | quality / core | CL-055, AUTO-006 |
| CL-057 — 디자이너 실사용 품질·시간 파일럿 게이트 | [#64](https://github.com/Jongtae/creative-loop/issues/64) | quality / core | CL-034, CL-048, CL-056 |
| CL-058 — 실제 성과 실험·표본 설계·인과 검증 | [#65](https://github.com/Jongtae/creative-loop/issues/65) | quality / extension | CL-047, CL-049, CL-057 |
| CL-059 — MVP scorecard·증거 validator | [#66](https://github.com/Jongtae/creative-loop/issues/66) | quality / core | CL-001 |
| CL-060 — L2 MVP 최종 인수·출시 승인 | [#67](https://github.com/Jongtae/creative-loop/issues/67) | quality / core | CL-047, CL-049, CL-052, CL-053, CL-054, CL-055, CL-056, CL-057, CL-059, CL-061, CL-062, AUTO-005 |
| CL-061 — 생성 결과→Scene 레이아웃 조합 통합 | [#69](https://github.com/Jongtae/creative-loop/issues/69) | generation / core | CL-015, CL-018 |
| CL-062 — 랭킹→A/B 후보 선택 통합 | [#70](https://github.com/Jongtae/creative-loop/issues/70) | evaluation / core | CL-043, CL-044 |
| AUTO-001 — 병렬 bootstrap·계약 fixture·사전검사 | [#71](https://github.com/Jongtae/creative-loop/issues/71) | automation / core | CL-001 |
| AUTO-002 — 내구성 DAG 배정기·경로 lease·backpressure | [#72](https://github.com/Jongtae/creative-loop/issues/72) | automation / core | AUTO-001 |
| AUTO-003 — Codex worker·worktree·독립 리뷰·checkpoint | [#73](https://github.com/Jongtae/creative-loop/issues/73) | automation / core | AUTO-001 |
| AUTO-004 — 정책 제한 단일 merger·최신 통합 SHA 검증 | [#74](https://github.com/Jongtae/creative-loop/issues/74) | automation / core | AUTO-002, AUTO-003 |
| AUTO-005 — 병렬 자동실행 통합·장애주입·무인진행 인수 | [#75](https://github.com/Jongtae/creative-loop/issues/75) | automation / core | AUTO-002, AUTO-003, AUTO-004 |
| AUTO-006 — 조기 유료 공급자 호환성 probe | [#76](https://github.com/Jongtae/creative-loop/issues/76) | automation / core | CL-013 |
