# Terra medium 병렬 구현 실행 계약

plan-v2-parallel / 2026-10-17 / 총괄 #7 / 설계 PR #68.
이 버전은 v1.2의 **동시 구현 PR=1·매 PR 소유자 클릭** 기본값을 대체한다.
제품은 아직 구현 계획 단계다. `parallel_plan.py`만 실행 가능한 오프라인 계획 도구이며, 지속 실행기 AUTO-001~005는 별도 구현·인수가 필요하다.

## 문서 우선순위와 범위

MVP 합격선은 `MVP_ACCEPTANCE.md`, 제품 필드/메서드는 `CONTRACTS.md` 그대로다.
실행 순서·시작/병합/실데이터 게이트는 v2 `plan.json`과 `PARALLEL_EXECUTION.md`가 우선한다.
`ARCHITECTURE_V1.md`의 번호순 설명은 개념적 기능 순서이지 실행 barrier가 아니다.
기존 issue의 짧은 선행 header와 충돌하면 v2 plan과 해당 issue의 v2 변경 기록을 읽고, 제품 계약의 의미 충돌은 blocked_design으로 남긴다.
원래 테스트·품질·사용권·사람평가·MVP-01~15 합격선을 완화하지 않는다.

## 모델과 풀

구현·계획·리뷰는 `gpt-5.6-terra`, reasoning `medium` 고정이다.
공식 config에 있는 주 모델/계획/리뷰/하위 모델 설정을 사용하되 CLI 버전·프로젝트 신뢰·조직정책·명령 override 이후의 effective model/effort를 검사한다.
미지원 설정이나 모델이면 해당 작업을 막고 다른 모델/high로 바꾸지 않는다.
기본 구현자4 + 독립 리뷰어2 + 단일 병합 coordinator1. 기본6개의 subagent 상한은 별도 CLI root process의 전역 한도를 대신하지 않는다.
여러 CLI worker를 쓰면 각 worker의 추가 spawn은 금지하고 coordinator가 전체 동시성을 계산한다. 제품의 AI 이미지 worker 동시성1과 개발자4는 다른 설정이다.
최대 구현6은 승인된 ceiling·자원/요금 측정 후에만. 처음부터6~8개를 강제하거나 무한 spawn하지 않는다.

## 시작

1. 설계 PR 병합을 확인하고 CL-001을 bootstrap한다. 그 뒤 CL-002/007/059와 AUTO-001은 서로의 실제 write set이 독립이면 병렬로 진행할 수 있다.
2. AUTO-001의 계약 fixture/사전검사를 먼저 동결한다. AUTO-002·003은 별개 모듈로 병렬 개발, AUTO-004로 통합, AUTO-005로 무인실행을 인수한다. bootstrap 동안도 독립 제품 작업은 진행 가능하다.
3. AUTO-005를 통과한 실행기와 소유자의 로컬 run policy가 있어야 지속 실행을 켠다. 이 계획 반영/PR 병합만으로 장기 프로세스나 자동병합이 켜지지 않는다.
4. 실행기 초기 정책에 repository/plan SHA, 허용 작업·경로·브랜치, coding 사용/시간/작업 한도, 기간, 취소방법을 고정한다. 제품 API 지출·SNS·모델 가중치 다운로드·외부 배포는 별도다.

## 작업 한 개

- 하나의 계약·이슈·PR. 이슈와 직접 선행 계약/diff만 task packet에 제공한다.
- coordinator가 exact write paths와 자원 lease를 원자 예약하고 별도 worktree/branch/DB/temp/port를 제공한다. 공용 진입점 수정은 integration lease를 별도 획득한다.
- `start_requires` 완료+고정 contract fixture로 구현을 시작한다. 누락된 선행 구현을 임시 production stub으로 몰래 채우지 않는다. 독립 준비(speculative)는 최대1개.
- 실패·경계·경쟁·권한 테스트부터 작성하고 변경 범위 검사를 수행한다. test/assertion/golden을 느슨하게 만들지 않는다.
- 빠른 영향 테스트→병렬 전체 회귀·실제 HTTP 브라우저→독립 문맥 리뷰→최신 통합 SHA 검사 순서로 진행한다.
- PR은 실제 명령·결과·head/base SHA·artifact hash·model/effort·원복·미검증을 포함한다. 새 head/contract/base 변경시 필요한 증거를 무효화한다.
- `merge_requires` 완료와 승인된 자동병합 정책을 만족하는 일반 코드 PR은 **개별 사람 클릭 없이** 단일 merger가 병합한다. 필수 사람 리뷰 규칙은 우회하지 않는다.
- 병합 완료 이벤트마다 빈 슬롯에 다음 독립 ready 작업을 즉시 배정한다. 다른 작업의 종료를 기다리는 wave barrier를 사용하지 않는다.

## 자동 진행 / 예외

일반 구현·테스트·범위 내 오류수정·독립 AI 리뷰·정책 허용 PR 병합·다음 작업 배정은 자동화 대상이다.
공통계약 파괴, 새로운 dependency, 마이그레이션 순서 변경, CI/보안/자동화정책 변경, 권한 확대는 별도 소유자 승인 대상이다.
한 task의 승인 대기·실패는 해당 task만 block하고 무관한 ready 작업은 계속한다. 모든 ready가 소진되면 idle_external/idle_budget/idle_review이지 MVP 완료가 아니다.
동일 실패 수정3회 후 최소재현·분할 제안과 blocked_design을 남긴다. 인증 오류/예산초과/정책 철회는 무한 재시도하지 않는다.
이미 실행 중인 worker 생존·branch·PR을 대사하지 않고 lease 만료만으로 복제 실행하지 않는다. checkpoint는 실제 run 상태이며 모델이 성공을 주장한 텍스트가 아니다.

## 승인·안전·최종 인수

코딩 worker는 제한된 workspace-write와 비대화형 approval=never를 사용한다. 이는 허용된 sandbox 안에서만 실행하고 필요한 승인은 자동 거부한다는 뜻이다. interactive coordinator 기본 on-request는 유지한다.
GitHub publish/merge credential은 trusted coordinator에만 보관한다. worker/reviewer는 정책을 바꾸거나 자신에게 권한을 부여하지 못한다.
모든 일반 CI에서 제품 유료호출0. 실제 source 계약 CL-026, source 파일럿 CL-034, 조기 probe AUTO-006, 최종 live CL-056, 사람 CL-057, 소유자 CL-060은 실제 증거가 필요하다.
CL-028~032의 오프라인 구현·mock 병합은 허용하지만 live 실행은 CL-026 승인과 실제 권한 없이는 fail-closed다. AUTO-006은 독립적으로 앞당기되 최종 live 품질 검사를 대체하지 않는다.
L2는 기존 모든 MVP-01~15와 추가 통합 CL-061/062, 무인실행 AUTO-005 및 CL-060 소유자 승인까지 충족한 경우만 선언한다.

## 현재 실행 가능한 검사

```bash
python scripts/parallel_plan.py
python scripts/parallel_plan.py --completed CL-001
python -m pytest -q tests/test_parallel_plan.py
```

`--completed`는 계획 시뮬레이션 가정이다. 실제 완료/lease/GitHub 상태를 검증하거나 저장하지 않는다.
`python scripts/automation/run.py ...`는 AUTO-005가 앞으로 만들 명령이다. 아직 존재하지 않는 실행기를 실행하라고 안내하지 않는다.

## 구현 모델에 전달할 지시

> AGENTS.md와 EXECUTION.md, PARALLEL_EXECUTION.md, plan.json, MVP_ACCEPTANCE.md를 읽어라. Terra/medium effective 설정을 확인하라. 먼저 CL-001/AUTO-001~005의 bootstrap·인수와 독립 ready 작업을 병렬로 진행하라. 한 이슈당 한 worktree/PR, 구현4·리뷰2·단일merger를 지키고 가능한 작업이 끝날 때마다 다음 독립 작업을 채워라. 고정 계약으로 시작할 수 있어도 병합 선행·통합 CI는 생략하지 마라. run policy 승인 전에는 PR까지, 승인 후 범위 내 일반 PR만 자동 병합하라. 권한/비용/모델/합격선은 바꾸지 마라. 외부 게이트는 해당 작업만 막고 다른 작업을 계속하라. 실제 실행·사람 증거 없이 L2 완료를 선언하지 마라.
