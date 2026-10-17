# 목표에서 증거까지: 테스트 추적표

plan-v1.2 / 상태: **계획, 신규 기능 미구현·신규 테스트 미실행**. 이 표의 테스트 경로는 후속 구현 요구다. 기존 main의 과거 CI를 이 계획의 기능 합격으로 재사용하지 않는다. 명령을 실행하지 못하면 not_run/blocked로 남긴다.

| 인수 ID | 대표 테스트 경로(예정) | 필수 부정/경계 케이스 | 실제 인수 증거 |
|---|---|---|---|
| MVP-01 | test_plan_status.py, test_api_boundary.py, 실제HTTP E2E | API key 없음·AI OFF·설정만으로유료호출0 | fresh clone 설치·명령·SHA |
| MVP-02 | test_migrations.py, test_asset_variants.py, test_rights.py, test_brands.py, test_scene_schema.py | 미래DB버전·rollback·alpha·staleCAS·잠금우회 | DB/원본hash·3비율fixture |
| MVP-03 | test_observations_v2.py, test_instagram_connector.py, test_source_sync.py | 0/null·부모중복·페이지실패·401·cursor악성 | CL034 실제30개/3run/재개 |
| MVP-04 | test_semantic_features.py, test_embeddings.py, test_reactions.py, test_retrieval.py | unknown·민감추론·권한후필터금지·벡터공간혼합 | 실제특징20라벨·20query P@5 |
| MVP-05 | test_jobs_store.py, test_worker.py, test_budget.py, test_batch_plans.py, browser generation | 중복제출·미확정재시도·24/25·부분실패 | CL056 live6장·CL057 방향평가 |
| MVP-06 | test_scene_edits.py, test_masks.py, browser layers/masks | revision경쟁·원본불변·zoom/DPR좌표·영역밖합성 | 저장재기동·원본hash·실제편집 |
| MVP-07 | test_design_lint.py, test_ai_corrections.py | 필수카피삭제·사실추가·무승인patch·이미지배경unknown | 규칙fixture·사람fact review |
| MVP-08 | test_exports_v2.py, test_scene_renderer.py, browser text bounds | 잘못된revision·폰트누락·ZIP경로·실패partial | exactPNG/SVG/JSON·manifest hashes |
| MVP-09 | test_engagement_v2.py, test_preferences_v2.py, test_dataset_splits.py, test_model_promotion.py, test_publications.py | 단위혼합·미래누출·tie승패변환·학습미검증활성화 | 선택당시snapshot·평가또는fallback |
| MVP-10 | test_deletion_cascade.py, test_backup_restore.py, worker crash | 삭제cache/복원재등장·미확정과금autoretry | fault injection·복원checksum |
| MVP-11 | tests/security/, test_budget.py, test_api_boundary.py | secrets/XSS/SSRF/DNS/Origin·oldAPI우회 | 위협→테스트결과·비밀0·상한검산 |
| MVP-12 | benchmark human-evaluation 입력검증 | 모델이사람답채우기·실패안제외·전체재제작 | CL057 실제5과제2명raw ratings |
| MVP-13 | benchmark 시간계산fixture | 활성/대기혼합·baseline0·사후제외 | 5쌍실측·중앙단축률·비용/대기 |
| MVP-14 | test_pagination.py, benchmark_local.py | 필터cursor변경·query상한·N+1·권한우회최적화 | 환경고정20회·개별latency/p95 |
| MVP-15 | test_mvp_acceptance.py, Docker/OS/network suite | missing/skip/blocked·가짜live·staleSHA·미승인owner | CL060 L2 scorecard+최종승인 |

## 필수 CI 및 별도 게이트

일반 PR CI는 unit/contract/integration/security와 실제 HTTP browser(공급자만fake)로 구성하고 live paid 요청0을 검증한다. golden screenshot 검토는 DOM/scene/bounds assertions와 함께 사용한다. 변경된 지원환경·dependency·DB migration에 대해 회귀해야 한다.

CL026 계정·정책, CL034 소셜 실제수집, CL056 유료AI, CL057 실제사람, CL060 소유자 승인은 CI의mock success로대체하지않는다. CL050/051은선택확장, CL058은L3실험이다.

## 증거 JSON의 최소 요구

```json
{
  "requirement_id": "MVP-05",
  "requirement_version": "plan-v1.2",
  "status": "not_run",
  "issue_ids": ["CL-015", "CL-056", "CL-057"],
  "release_sha": null,
  "environment": null,
  "evidence_kind": null,
  "commands_executed": [],
  "results": [],
  "artifact_hashes": [],
  "reviewer": null,
  "executed_at": null,
  "limitations": ["계획만 작성됨. 실행·사람평가 없음."]
}
```

이 예시는 아직 구현되지 않은 CL059 검사기의 입력 요구이며 통과 fixture가 아니다. 실제schema는계약대로추가하고not_run을pass로변환하려면필수증거를검증한다. 결과파일안의명령을자동실행하지않는다. 실제상용원본/개인댓글/토큰·폰트파일은Git/CI artifact에올리지않는다.

## 실패와 재검증

필수항목의skip/flaky retry/blocked/waived는정상pass가아니다. 원인·최소재현·수정PR·다시실행한명령을기록한다. 이전SHA결과는영향범위와불변조건을확인한경우만근거로첨부하며새기능검증을대체하지못한다. 목표미달을표본삭제/기준완화/모델자기평가로해결하지않는다.
