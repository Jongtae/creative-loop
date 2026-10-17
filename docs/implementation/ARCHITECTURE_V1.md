# Creative Loop v1 전체 구현 설계

plan-v1.2 / 2026-10-17. 기준 main `596c8a7b18db602cae7e4972732ac83ed2f4981a`. 신규 기능의 구현 완료 기록이 아니라 앞으로 구현할 설계다. 총괄 #7, 상세 CL-001…060. 범위·합격은 MVP_ACCEPTANCE, 정확한 schema는 CONTRACTS, 의존관계는 plan.json이 우선한다.

## 1. 제품 구조

브랜드 가이드 → 허가된 creative/반응 → 관찰·추론 특징 → 관련 근거 → 여러 콘셉트/이미지 → native text/logo/shape와 래스터 조합 → 교정/비교/선택 → SVG/PNG/JSON → 실제 게시 결과 → 평가/다음 제작.

연구 대시보드·페르소나 대화는 제품 목표가 아니다. 모든SNS 전량 수집을 보장하지 않는다. 단일 디자이너, 정지 이미지, 한국어/영어, 로컬/접근 제한 MVP를 우선한다. Figma/ComfyUI/실제 트래픽 성과실험은 선택 확장. 다중 테넌트·Postgres/분산큐·동영상·광고집행은 기존 #6 후속 범위로 남긴다.

## 2. 고정 스택과 점진 확장

Python3.13과 기존 FastAPI/Pydantic/httpx/NumPy/Pillow를 유지한다. SQLite WAL+로컬 디스크, API 프로세스와 명시 실행 worker를 분리하며 동시 외부작업 기본1. 다중호스트 SQLite 공유 금지. 긴 네트워크 호출 동안 DB write lock을 잡지 않는다.

프런트는 HTML/CSS/JS를 유지하고 영역별 ES module로 나눈다. React/Next.js·Kafka/Kubernetes·에이전트 프레임워크로 전면 재작성하지 않는다. SceneDocument JSON을 편집 원본으로, SVG를 렌더링으로 사용한다. PNG final export는 통제된 headless renderer에서 실제 폰트·bounds를 확인한다. Chromium의 설치·메모리·네트워크제한은 CL-025/054의 운영 의존성이다.

코딩 모델 Terra medium과 제품의 이미지 생성 엔진은 별개다. AI는 OpenAI Protocol 어댑터부터, ComfyUI는 확장. 로컬 임베딩은 google/siglip2-base-patch16-224가 후보이나 정확한 weights revision·라이선스·설치·한국어 품질은 CL-036에서 검증한다. 기본 앱/CI가 자동 가중치를 받지 않는다.

첫 소스는 승인된 자사 Instagram professional 계정 읽기 전용을 후보로 한다. 로그인 계열/API version/endpoint/scope/지표/저장·학습 사용권은 CL-026에서 실제 확인한 계약으로 고정한다. 접근 불가시 blocked_external, 무단 스크래핑 대체 금지. 다른 허가 소스를 고르면 소유자 ADR로 먼저 계약과 후속 이슈를 변경한다. 기존 JSON/CSV import는 계속 유지한다.

## 3. 기준 코드에서 확인된 선행 문제

- Store 초기화가 매번 user_version=1을 실행하므로 순차 migration과 checksum/실패 rollback이 먼저다.
- 기존 이미지 추출은 흰 배경 합성·축소를 한다. 새 업로드부터 RGBA 원본과 preview/analysis를 분리한다. 과거에 잃은 alpha를 복원했다고 하지 않는다.
- reserve_call은 프로세스 Lock+요청수 제한이다. 별도 worker/대량생성 이전에 DB의 원자 예약·금액·시도 기록으로 보강한다.
- DesignSpec는 제한된 레이아웃 파라미터다. SceneDocument v2를 추가하되 기존 payload/읽기/내보내기를 깨지 않는다.
- 관측10k/일부시안500의 고정조회상한은 전량처럼 표시하지 말고 cursor로 확장한다.

## 4. 모듈 소유권

| 경로 | 책임 |
|---|---|
| creative_loop/contracts/ | 순수 Pydantic schema, DB/네트워크 금지 |
| migrations/ | 순차 SQL/버전/checksum, 파괴적 자동 downgrade 금지 |
| repositories/ | parameter SQL, CAS, paging, 짧은 transaction |
| services/ | rights/assets/brands/scene/dispatch/export 등 도메인 규칙 |
| jobs/ | claim/lease/heartbeat/취소/불확정 복구/수집·추출 handler |
| integrations/ | AI/source adapter, credentials, bounded egress |
| analysis/ | pixel/semantic/embedding/reaction/cohort/retrieval/ranking |
| evaluation/ | 고정 dataset/splits/baselines/holdout/rubric/promotion |
| api/ | router, 공통 auth/Origin/동의/오류 경계 |
| static/modules/ | 브랜드/작업/레이어/마스크/비교/근거 UI |
| integrations/figma-plugin/ | 선택 확장 native Figma import |

기존 app.py factory/미들웨어, models.py v0.1, providers.py/features.py는 호환 진입점으로 남긴다. 같은 이름의 파일과 패키지를 동시에 만들지 않는다. 이슈의 새 상대 Python 경로는 특별한 언급이 없으면 creative_loop/ 아래다.

## 5. 저장과 원본 보존

기존7개 테이블을 삭제하지 않는다. 새 owner 이슈에서 schema_migrations, asset_variants, rights_grants/provenance, brands/brand_revisions, jobs/attempts, budget_reservations, design_documents/revisions/fact_reviews, sources/runs/checkpoints, observation_snapshots/tombstones, feature_sets/embeddings, evidence_snapshots, generation_plans, preference_events, evaluation/model_artifacts, publications를 순차 추가한다.

ID뿐 아니라 version/revision/hash를 모든 선택·내보내기·학습에 연결한다. 원본은 metadata 제거·EXIF 방향 적용한 full-resolution RGBA sanitized_original이다. preview/analysis만 축소·합성한다. exact raw bytes는 기본 미보관, 별도 권한·보존 승인시만 private 영역에 저장하고 공개 variant API에 넣지 않는다. 폰트 binary는 저장/배포 범위 밖이다.

## 6. 생성·수정 흐름

BrandKit/Brief/권한을 고정한다. 근거 없는 baseline은 그대로 유지한다. 실제 근거 선택시 최대5개 snapshot에 권한·시간·모델버전을 고정한다. 유료 콘셉트 호출 전에 별도 견적·승인을 받는다. 결과의 방향·카피를 확인/수정한 뒤 이미지 생성 plan의 count/model/cost/hash를 다시 승인한다.

이미지 최대24 child jobs, layout 최대60. 완료/실패/취소/불확정과 비용을 나눠 보여준다. 실패분을 복제/fake로 채우지 않는다. 같은이미지를다른layout으로 만든것과 독립생성은 구분한다.

SceneDocument의 text/shape/image/logo만 허용한다. 래스터 안의 글자/피사체까지 native layer가 됐다고 하지 않는다. edit는 typed patch의 전체검증→CAS→새revision이다. undo도 새revision. 로고/필수카피 잠금을 클라이언트가 해제할 수 없다. 일반 자연어의 사실 오류를 완벽 탐지하지 못하므로 AI 새 카피에는 hash에 고정된 사람 fact review가 필요하다.

마스크는 원본 픽셀좌표에 고정한다. 내부 edit_alpha=1이며 공급자 극성은 adapter가 변환. 비마스크영역 완벽보존은 provider 약속이 아니라 명시적 원본합성 옵션에서만 보장한다. 적용 전후를 사용자가 비교한 뒤 새asset/scene revision으로 채택한다.

## 7. Job·비용·실패

queued→running→succeeded/failed/needs_reconciliation/cancelled. lease60s·heartbeat15s 제안, owner token CAS. enqueue idempotency는 앱 중복제출만 막으며 공급자 exactly-once 보장이 아니다. 전송전실패만 안전재큐; 전송후timeout/crash/저장실패는 자동 paid POST 재실행 금지. 사용자의 재승인·대사로 처리한다.

가격은 공식 확인일·version·단위상한을 고정하고 정수 micro-USD로 보수 예약. 원자식 settled+outstanding+new≤일일cap/plan cap, 기본 live금액cap0. 모르는가격/상한이면 승인차단. 전송후usage 없음은 예약유지·미확정 표시; 임의0원처리 금지. 공급자 actual이 견적을 넘으면 그대로기록·경보·후속중단. 다른앱의계정전체지출까지 통제한다고 하지 않는다.

401/403/refusal/schema오류는 무한반복 금지. 관측 GET만 bounded backoff/Retry-After, 유료POST 자동retry 금지. 모델응답/댓글을 코드·도구명령으로 실행하지 않는다.

## 8. 소스·특징·근거

저장/모델입력/생성재사용/학습 권한은 각각 다르다. media는 승인된connector 응답만 fetch하고 host/DNS/실제peer IP/redirect까지 검증한다. URL·Content-Length만 믿지 않고 streaming byte/pixel 상한을 적용한다.

페이지의 관측저장+checkpoint를 원자commit한다. 실패/401/빈페이지는 삭제의 증거가 아니다. 신규자료와 기존metric refresh를 분리하고 실제 관측시각/기간/availability를 기록한다. 0/null, share/repost, count/unique people, sample comments/total count, 캐러셀 부모반응을 구분한다.

특징은 관찰/모델추론/unknown으로 나누며 모델·preprocess·schema·asset hash에 따른 캐시를 사용한다. 개인 신원/민감특성 추론 없음. 댓글은 반응대상과이유/근거span을 추출하지만 전체고객선호로 일반화하지 않는다.

검색은 권한/삭제/DEMO/시간 필터 후 키워드+같은 embedding 공간 cosine/RRF. 비교가능한 event rate와 relevance는 분리한다. 생성 context도 추가권한을 검증한다. 상관·유사도는 인과나CTR가 아니다.

## 9. 선택·학습·삭제

개인 A/B/tie/skip는 당시 revision/hash/표시순서/actor를 저장한다. 쌍대모델은 동의한 개인의 실제선택만 사용한다. source-content/campaign/near-duplicate/pair-connected group+시간cutoff로 분할하고 scaler는 train만 fit. 부족하면 평가불가/fallback. 안전한 JSON 모델만 저장하고 테스트셋으로튜닝하거나 자동활성화하지 않는다.

삭제/철회는 먼저새조회·작업·export 사용을 차단하고 durable job으로 원본/관측/댓글/캐시/embedding/evidence/모델 의존을정리한다. snapshot 불변이라는 이유로 삭제대상을 보존하지 않는다. tombstone을 재수집/백업복원에 적용한다. 기존모델은 stale/비활성·재학습필요이지 완벽 unlearning이라고 하지 않는다. 이미다운로드/외부전송한자료 자동회수 주장은 금지한다.

## 10. 검증과 통합 순서

CL001–013 기반·안전실행 → CL014–025 실제제작 → CL026–042 허가데이터·근거 → CL043–049 선택·검증루프 → CL052–060 보안/성능/설치/실행/사람인수. 번호순이 아니라 plan.json의 DAG로 진행한다. CL059 합격검사기는 초기에 구현 가능하다. source gate가 막히면 다른독립core작업을 진행한다.

일반 CI에는 live paid0, 실제 HTTP E2E, migration/두connection경쟁/crash/권한삭제/원본불변·exporthash와보안fixture를 포함한다. live계정·사람평가·OS실행은 별도증거. 최종 L2 조건은 MVP_ACCEPTANCE의15항목이며 모델self-score·테스트수로대체하지 않는다.

## 공식 참고와 미확인 경계

- 모델: https://developers.openai.com/api/docs/models/gpt-5.6-terra
- 구성: https://developers.openai.com/codex/config-reference/
- 이미지: https://developers.openai.com/api/docs/guides/image-generation
- SigLIP2: https://huggingface.co/google/siglip2-base-patch16-224
- Figma: https://developers.figma.com/docs/plugins/
- 소스 계약 확인 대상: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/

구성키는2026-10-17 공식문서를 확인했지만 사용자 클라이언트의 실제설정·모델접근을 실행검증한 것은 아니다. Meta 문서는 이 조사환경에서본문접근이실패했으므로CL026에서 정확한계약을 확정해야 한다. 이전 연구원문은 보존자료이지 최신정책/라이선스/성능이 검증된구현명세가 아니다.
