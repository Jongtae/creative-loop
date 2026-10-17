# Terra medium 구현 실행 계약

계획 plan-v1.2 / 2026-10-17 / 총괄 [#7](https://github.com/Jongtae/creative-loop/issues/7).
이 문서는 앞으로의 구현 지침이다. 60개 이슈가 등록됐다는 것은 기능 구현이나 MVP 합격을 뜻하지 않는다.

## 시작과 문서 우선순위

설계 PR을 검토·병합한 뒤 `AGENTS.md`, `MVP_ACCEPTANCE.md`, 이 문서, `plan.json`, 선택한 이슈와 직접 선행 PR의 계약만 읽는다. 60개 이슈와 연구 원문 전체를 매번 프롬프트에 넣지 않는다.

범위·합격선은 MVP_ACCEPTANCE, 정확한 필드·메서드는 CONTRACTS, 모듈 구조는 ARCHITECTURE_V1, 누적 선행관계는 plan.json을 따른다. 개별 이슈의 축약 명칭은 CONTRACTS의 canonical 이름으로 구현한다. 정합성 검사에서 추가한 CL-031/037/038의 CL-033 선행관계도 필수다. 의미 충돌은 임의 선택하지 말고 blocked_design으로 기록한다.

## 모델 고정

구현·계획·별도 리뷰는 `gpt-5.6-terra`, reasoning `medium`. `.codex/config.toml`에는 주 모델, 계획 모드, 리뷰 모델, 하위 에이전트 기본값을 지정한다. 설정 파일만으로 실제 적용을 확인했다고 하지 않는다. 설치된 클라이언트 버전, 프로젝트 신뢰, 조직 정책, 명령행·spawn override를 확인하고 실제 model/effort 관측값을 기록한다. 미지원 키/모델은 명확히 중단·안내하고 다른 모델이나 high로 조용히 바꾸지 않는다.

구현 모델과 제품의 이미지 생성 공급자는 별개다. Terra가 코드를 작성하며 이미지 모델은 승인된 어댑터로 호출한다. 같은 모델의 별도 문맥 리뷰는 유용한 자동 검토지만 사람의 판단이나 통계적 독립성을 보장하지 않는다.

## 한 작업의 실행

1. git status, 현재 main SHA, issue 본문·댓글·직접 의존 PR을 확인한다. 사용자의 변경을 보존하며 별도 worktree/branch를 사용한다.
2. issue closed만으로 선행 완료로 보지 않는다. 코드 작업은 merged PR·CI·필수 증거, gate는 실제 실행·소유자 승인 증거가 필요하다. gate에 코드가 없으면 의미 없는 코드 PR을 강제하지 않는다.
3. branch `impl/cl-NNN-<slug>`에서 한 계약만 구현한다. 목표는 보통 production 파일1~5개+테스트1~3개. 두 개 이상의 독립 변경이나 큰 API/DB 변경이 필요하면 하위 이슈로 더 분할한다. 파일 수를 맞추려고 변경을 숨기지 않는다.
4. 먼저 실패·경계·경쟁·권한 테스트를 만든다. 기존 assertion, fixture, 보안 검사, golden을 느슨하게 바꿔 통과시키지 않는다.
5. 구현 후 해당 테스트→전체 회귀→관련 브라우저 network E2E를 실행한다. 임시 DB·주입 시계/RNG·mock 공급자가 기본이며 실제 사용자 DB를 테스트하지 않는다.
6. 새 문맥의 같은 모델 리뷰어에게 이슈, diff, 테스트 결과를 제공한다. 계약 위반, 오류 경로, 데이터 누출, 동의/비용, 원복 가능성을 검토한다. 리뷰어가 가짜 테스트 결과나 사람 승인을 생성하지 못하게 한다.
7. PR에는 실제 issue 번호, 변경 계약, 실행 명령/결과, 미검증, 원복, 관측 model/effort를 쓴다. 모든 인수 조건이 완료된 코드 이슈만 `Closes #N`. 미완료 게이트가 남으면 `Refs #N`과 상태를 기록한다.
8. 기본은 PR까지 만들고 소유자의 병합 승인을 받는다. 승인된 정책 없이 auto-merge/force-push/관리자 우회/공개 전환/배포 금지. 병합 후 다음 ready 작업 하나를 선택한다. 같은 파일에 병렬 구현 금지; 기본 동시 구현 PR=1.

같은 실패를 3회 수정해도 해결되지 않으면 최소 재현과 원인을 기록하고 분할/설계 수정으로 해결한다. 모델 상향·무한 재시도는 하지 않는다. 관련 없는 ready 작업은 별도로 진행할 수 있다.

## 상태와 인수

작업: planned → ready → in_progress → review → merged. 차단은 blocked_design 또는 blocked_external. deferred/waived는 완료가 아니다. 구현 상태와 실검증 상태를 따로 기록한다. 새 테스트 파일명·명령은 구현 요구사항이며 생성·실행 전에는 통과했다고 쓰지 않는다.

```
Issue / PR:
Observed model / effort / client version:
Base SHA / branch / worktree:
Changed contracts and paths:
Tests actually run / results / artifact hashes:
Unverified or blocked:
Rollback:
Next ready issue:
```

## 기본 명령

```bash
python -m pytest -q
node --check creative_loop/static/app.js
python scripts/browser_smoke.py --transport network --artifacts artifacts
```

새 ES module의 syntax/test도 실행한다. inprocess는 보조이며 실제 HTTP 검증을 대신하지 못한다. 문서 전용 PR은 JSON/TOML·링크·계약·DAG 정합성을 검증한다. 이전 69개/10개 결과를 현재 결과로 복사하지 않는다.

## 외부 승인과 비밀

유료 요청, 모델 가중치 다운로드, 소셜 계정 연결, 외부 배포, 실제 사람 평가에는 별도 승인·자료가 필요하다. API 키의 존재가 비용 승인은 아니다. 전송 자료, 계정, 모델, 호출수, 상한 금액을 승인받고 해당 hash에 고정한다. 첫 콘셉트 계획 호출도 유료이므로 이미지 생성 이전에 별도 견적·승인을 받는다.

키·토큰·상용 원본·개인 댓글은 채팅/issue/PR/export에 넣지 않는다. 원본과 삭제·권한·비용 경계를 지킨다. 게이트 미충족을 mock으로 채우지 않는다. 사람 평가는 모델이 대신할 수 없고 승인 없이는 blocked_external로 남긴다.

## 붙여 넣을 작업 지시문

> Jongtae/creative-loop의 AGENTS.md와 docs/implementation/EXECUTION.md, MVP_ACCEPTANCE.md, plan.json을 읽어라. 구현 모델은 gpt-5.6-terra, reasoning medium으로 고정하고 실제 설정을 확인하라. 설계 PR 병합과 직접 의존 작업의 완료 증거가 확인된 가장 앞의 core 이슈 하나만 구현하라. 처음에는 CL-001(#8)이다. 지정된 계약·파일·실패 테스트를 지키고 한 이슈당 한 PR을 만들어라. 테스트를 완화하지 말고 실제 명령·결과·원복·미검증을 기록하라. 같은 모델의 별도 문맥 리뷰를 받고 승인 없는 유료 호출·모델 전환·권한 확대·강제 병합·배포를 하지 마라. 병합 승인 후 다음 ready 작업으로 진행하라. 외부 승인과 사람 평가가 필요한 단계는 증거가 없으면 blocked_external이다. L2 MVP 완료는 모든 필수 합격선·실제 검증·CL-060 소유자 승인이 충족된 경우에만 선언하라.
