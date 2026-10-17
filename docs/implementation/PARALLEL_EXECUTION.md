# 병렬 자동 구현: 설계와 활성화 경계

plan-v2-parallel / 총괄 #7. 제품 작업 CL-001~062와 실행기 AUTO-001~006, 총68개(필수65·선택3).
**반영된 것:** 실행 정책, 작업별 dependency/resource metadata, Codex 설정, CI 분할, 오프라인 배정 후보 계산과 테스트.
**아직 아닌 것:** daemon/실제 Codex pool/GitHub 자동병합 실행. AUTO-001~005 구현과 실제 파일럿 전에는 not_implemented_not_started다.

## 1. 목표는 가장 많은 worker가 아니라 가장 짧은 통합 완료 시간

중앙 배정기(결정적 코드) → 구현4 → 리뷰2 → 단일 merger → 완료 이벤트 → 다음 ready.
독립 작업이 없으면 슬롯을 억지로 채우지 않는다. 시안 생성 공급자의 동시성은 이 코딩 풀과 무관하다.
우선순위는 merge 준비 가능 작업, longest downstream path, 해제되는 후속 수, 오래 대기한 작업 순이다.
동일 길이 task 가정으로 계산한 단계 수는 기간·배속 보장이 아니다. 실제 소요/리뷰/재작업/한도를 관측하여 재가중한다.

## 2. task metadata

`plan.json` schema_version=2. task_defaults의 값이 각 task에 적용된다.
- `depends_on`: backward-compatible **병합** 선행. `merge_requires` 생략시 이 값.
- `start_requires`: 생략시 depends_on. 다르면 contract_lock_required=true가 필수.
- `live_requires`: 실제 외부 실행 전 별도 충족할 gate. 비어 있어도 비용/전송 동의가 생기지 않는다.
- `resources`: coarse exclusive hints. 실제 dispatch 전 issue의 범위와 read/쓰기 계획을 분석해 exact write manifest를 원자 예약해야 한다.
- `lane`: 동적 후보 분류. lane 전체를 독점시켜 병렬성을 불필요하게 없애지 않는다.
- `merge_policy`: policy_checked / owner_review / owner_gate. 뒤 두 가지를 자동 승인하지 않는다.
- `status`/`evidence`: 정적 계획의 시작값. 실제 상태는 git-ignored coordinator DB에 저장하고 사람이 읽을 요약만 기록한다. 모든 worker가 plan.json을 수정하지 않는다.

`start_requires`를 완화한 UI·adapter 작업은 동결된 fixture로만 준비하고 최대1개 speculative slot을 사용한다.
후속의 missing dependency를 mock으로 채워 프로덕션에 연결하는 것은 금지다. 병합은 실제 선행+최신 통합검사를 필요로 한다.
계약 fixture hash 변경은 관련 worker 결과·리뷰·CI의 신선도를 재검사하며 grandfathering하지 않는다.

## 3. 병목 분리와 인수 보존

| 기존 | v2 처리 | 보존된 최종 검증 |
|---|---|---|
| CL-018이 CL-015 생성 완료를 기다림 | CL-018은 CL-017 뒤 순수 renderer; 조합은 CL-061(#69) | 60개 scene/lineage/이미지수 구분을 CL-061 및 CL-055에 연결 |
| CL-044가 CL-043 ranking을 기다림 | CL-044는 revision 비교 독립; ranking 연결 CL-062(#70) | ranked candidate·tie/skip·표시순서·fallback을 CL-062 및 CL-055에서 통합 |
| CL-028에 소스 승인 의존 | 오프라인 SourceConfig/Protocol은 먼저 구현; live CL-026 fail-closed | CL-034는 CL-026을 명시적 선행으로 유지; 실데이터30개/3회 변함없음 |
| 마지막에 CI/브라우저 기반 구축 | 기존 CI를 지금 unit/browser/plan 병렬로 분리; CL-055는 fixture 기반 test scaffold 조기 준비 가능 | 최종 CL-055 통합 완료 전 합격 금지, missing tests를 skip 처리 금지 |
| 마지막에 실제 provider 문제 발견 | AUTO-006(#76) 소량 승인 probe를 CL-013 뒤 독립 실행 | CL-056의 최종SHA·3콘셉트×2이미지·수정/비전/품질 검증 유지 |

## 4. 충돌 제어: clone만 분리해서는 부족

작업별 worktree, branch, DB, tmp, server port, browser artifacts를 분리한다.
특정 path 또는 그 상위 directory에 대한 write 예약이 겹치면 동시 배정하지 않는다. read-only reviewer는 immutable head를 읽고 수정권한이 없다.
공용 자원은 `app.py`, legacy `models.py`/store 진입점, `static/app.js`/index/styles, package init·router registry, migrations 번호/manifest, requirements/lock, workflows, AGENTS/실행정책이다.
이런 자원은 기본 builder 소유가 아니다. 새 영역 module은 독립 작성하고 최소 wiring만 coordinator가 별도 integration lease와 최신 base에서 적용한다.
새 migration 파일 내용은 각 이슈 소유지만 최종 연속 번호/체크섬 등록은 merger가 순서 고정 후 전체 upgrade/rollback 실패 테스트를 다시 수행한다.
예약은 정렬된 all-or-nothing transaction, lease/fencing token으로 수행한다. 예상하지 않은 diff가 나타나면 publish를 막고 예약을 재심사한다.

## 5. 내구성·복구·속도제어

제안 상태: planned→ready→claimed→implementing→reviewing→merge_ready→merging→merged.
보조 상태: blocked_design, blocked_external, blocked_approval, needs_reconciliation, idle_budget.
재시작은 main/branch/PR/CI 실제 상태와 DB checkpoint를 비교하여 재개한다. 이벤트 중복키와 head SHA로 dedupe한다.
lease가 만료되어도 이전 process 종료/대사 없이 복제 worker를 띄우지 않는다. paid POST 응답분실은 자동 재시도하지 않는다.
회귀/리뷰 수정은 같은 원인 최대3회; 해결 못 하면 해당 task를 격리하고 무관한 작업 진행.
리뷰 backlog≥4 또는 merge backlog≥2이면 신규 speculative stop, 구현 슬롯 축소. 429/메모리 압박/예산압박도 축소 신호다.
4→6은 owner ceiling 내에서 측정 후만 가능하고 총 root/subagent 수를 합산한다. 모델/effort는 변하지 않는다.

## 6. 사전 승인된 자동병합

현재 `auto_merge_runtime_enabled=false`이며 PR #68은 이 정책의 검토 대상이다. 반영 요청은 runtime을 실행하거나 무제한 비용을 허용한 기록이 아니다.
소유자의 로컬 run policy를 활성화한 뒤 policy_checked 작업만 매 PR 사람 클릭 없이 병합 가능하다.
필수 조건: plan/issue scope 일치, 실제 merge prerequisites 완료, 현재 head의 별도 문맥 리뷰, 미해결 high severity0, 최신 base+head 통합 tests 전부 success, branch protection 준수, secret/rights/cost policy 변경0.
모델 리뷰는 본인 GitHub approval 또는 사람 승인을 대체하지 않는다. 필요한 권한이 없으면 해당 PR만 대기한다.
merge 직전 expected head와 최신 base를 재조회한다. 다른 writer가 main을 바꿀 수 있는 설정이면 check/merge race를 완전히 막았다고 주장하지 않는다. protected branch 또는 실제 단일 writer 보장 없는 상태에서 자동병합을 켜지 않는다.
새 dependencies, 파괴적 contract/migration 순서, CI/보안/자동화 정책 변경, 유료실행, 외부전송·배포, 최종출시는 별도 승인 대상이다.

## 7. 권한과 예산 분리

interactive coordinator: workspace-write/on-request 유지. unattended worker: workspace-write/approval never(거부), reviewer: read-only. sandbox/network 우회는 하지 않는다.
GitHub write token은 trusted coordinator만. 실제 coding 인증은 필요한 프로세스에만 주입하고 제품 AI/SNS secret은 전달하지 않는다.
run 정책은 로컬 보호 파일로 repo, plan/contract/policy hash, 기간, 허용 branch/paths/tasks, coding call/token/비용 또는 구독 실행 한도, runtime cap, stop을 고정한다. 미확정 사용량이면 안전여유를 유지하고 cap을 입증할 수 없으면 신규 배정을 중단한다.
제품 live 호출 budget은 별도이며 기본0이다. coding pool을 켰다고 이미지6장·SNS수집·가중치 다운로드가 승인되지 않는다.
모든 외부 게이트가 막혀 ready가 없으면 idle_external과 필요한 증거 목록을 남긴다. 스스로 승인·리뷰·고객반응을 만들지 않는다.

## 8. 검증 책임

이번 `parallel_plan.py` tests는 DAG/우선 후보/자원 충돌/시작 대 병합/게이트 경계를 확인하는 계획 도구 단위검사다. process crash나 remote merger 자체를 실행한 결과가 아니다.
AUTO-002~005가 별도로 수행할 최소 검증:
- 두 scheduler 경쟁, 중복/역순 이벤트, prefix 경로 충돌, stale fencing token, 깨진 checkpoint.
- worktree/DB/port 격리, worker 종료/재개, 잘못된 model/effort, 무단 path·명령 주입·secret 노출 거부.
- stale head/base/contract·취소/skipped CI·위조 리뷰·기존PR 중복 및 lost merge response 대사.
- 4개의 실제 worker overlap과 독립 review, 단일merge, 한 task block에도 다른task 진행을 timestamp/event로 확인.
- dry-run은 외부0, 유료·권한 초과0, missing evidence는 pass가 아님.
CI plan/unit/browser는 독립 병렬 job이며 최종 verify가 모두 success일 때만 통과한다. 브라우저 network 검사는 항상 수행한다.
새 browser/security suites는 작성한 뒤 동일 gate에 편입해야 하며 기존 smoke10개가 모든 미래기능을 검증한다고 하지 않는다.
실제사람2명/5과제·활성작업시간·실제소스·export·복구 등 기존 L2 기준은 그대로다.

## 9. 공식 참고 / 구현시 재확인

- https://developers.openai.com/codex/config-reference/ : agents.max_concurrent_threads_per_session, model/effort, sandbox/approval. 실제 클라이언트 적용 별도 검증.
- https://developers.openai.com/codex/noninteractive/ : exec의 비대화형 출력·권한·실행 방식. 정확한 flags는 설치된 help로 고정.
- https://developers.openai.com/codex/multi-agent/ : 독립 작업과 별도 문맥 review, 공유 수정 충돌 고려.
- https://developers.openai.com/api/docs/models/gpt-5.6-terra : medium 지원. 계정 접근·RPM/TPM·가격은 실제 run에서 확인.
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency : PR 중복실행 취소. merge serialization과 CI cancel은 다른 개념.
