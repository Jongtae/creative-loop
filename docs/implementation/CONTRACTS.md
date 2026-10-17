# 구현 계약 C01–C11

plan-v1.2 / 2026-10-17. 앞으로 구현할 정식 계약이며 현재 API에 모두 존재한다는 뜻이 아니다. 범위·합격은 MVP_ACCEPTANCE.md, 의존성은 plan.json을 따른다. 각 소유 이슈가 schema/서비스/테스트를 구현한다. 축약된 이슈 본문의 별칭보다 이 문서의 canonical 필드·값을 우선한다. 의미를 바꾸는 수정은 ADR와 영향 이슈·테스트 갱신이 필요하다.

## C01 — 공통 입력·API·오류·저장

신규 내부 ID는 UUID4의 32자 소문자 hex 문자열이며 외부 플랫폼 ID와 구분한다. legacy ID는 기존 검증 규칙을 유지하는 adapter에서만 허용한다. version/revision은 양의 정수, 시간은 timezone-aware UTC ISO8601, 실수는 finite, 크기/목록/문자열은 상한을 둔다. schema는 Pydantic strict validation 및 extra=forbid가 기본이며 bool을 count로 받지 않는다.

새 오류는 `{error:{code,message,request_id,retryable,details}}`; details는 허용된 필드명·범위·충돌 version 정도만. stack, token, provider body, 사용자 원문은 금지한다. 기존 detail 소비자는 compatibility wrapper로 유지한다. retryable=true도 유료 POST의 자동 재실행 승인이 아니다.

create201, enqueue202, 입력422, 초과413, 인증401/권한403, 없음404, revision/idempotency 충돌409, quota429, 공급자502/timeout504를 사용한다. 오래 걸린 job의 실패는 상태 조회에서 error_code로 반환한다. 각 새 API도 기존 Host/Origin/X-Creative-Loop:1/APP_TOKEN 경계를 통과해야 한다. sensitive GET/export도 인증 대상이다.

`Page={items:[],next_cursor:null|string,has_more:bool}`. cursor는 codec_version, 정렬 키+ID, 필터 hash를 포함한 제한 길이 opaque 값이다. 다른 필터/정렬/버전이면 거부한다. cursor 값을 SQL/파일경로로 실행하지 않는다. sort는 allowlist, SQL은 parameter binding. 권한 필터를 전체 수/결과 계산 전에 적용한다.

마이그레이션은 user_version을 읽고 알려진 순서만 transaction으로 적용한다. 성공 후만 version을 올리고 번호·SQL checksum·시각을 기록한다. 미래 version/변조 checksum/중간 실패는 기동 거부 또는 rollback. 기존 사용자 DB 삭제·자동 downgrade 금지. 사용자 DB와 테스트 DB를 분리한다.

## C02 — Asset·목적별 권한·provenance

`AssetRecord={id,created_at,content_hash,variants,provenance,rights_ref,is_demo,original_available,legacy_path?}`.

`AssetVariant={kind,sha256,width,height,mime,has_alpha,storage_key,transform_version}`. 공개 가능한 kind는 sanitized_original/preview/analysis/mask다. storage_key는 서버 생성이며 클라이언트가 지정할 수 없다. 반환 API에는 로컬 절대경로를 노출하지 않는다.

sanitized_original은 EXIF orientation을 적용하고 metadata를 제거한 full-resolution RGBA다. preview/analysis만 축소·배경 합성한다. exact raw 업로드 bytes는 기본 미보관, 별도 원본 보관 권한이 있는 private 저장소에만 선택 보관하며 일반 variant API에 포함하지 않는다. 신규 업로드는 PNG/JPEG/WEBP 정지 이미지, 10MB/20M pixels 상한을 유지한다. magic/decode/animation/폭탄을 검증하고 validate→staging→atomic rename→DB commit 실패 정리를 구현한다. 원본은 절대 덮어쓰지 않는다. 과거 흰 배경 축소본은 legacy/original_available=false로 남기며 잃은 투명도를 복원했다고 하지 않는다.

`Provenance={origin:user_upload|licensed_source|ai_generated|derived|synthetic,source_config_id?,external_id?,parent_asset_ids:[],operation?,model?,model_revision?,prompt_version?,provider_call_id?,mask_hash?,transform_version?}`. 상용 원본·prompt 원문은 기본 export/audit에 제외한다.

`RightsGrant={id,version,basis,allow_analysis,allow_generation,allow_model_input,allow_training,allow_original_storage,reviewed_at?,expires_at?,revoked_at?}`. 새 training/original 권한은 false 기본. 사용자 체크는 권한 주장 기록이지 법적 인증이 아니다. legacy 불명확 권한은 승격하지 않는다.

`check_rights(subject,purpose,at,expected_version)->PermissionDecision{allowed,reason_codes,grant_versions}`. purpose는 analysis/generation/model_input/training/original_storage 중 하나다. 외부 생성에는 generation과 model_input 모두 필요하다. 모델 학습은 추가 training 동의가 필요하다. 부모 provenance의 필요한 제한을 보존하고 순환/깊이 초과를 거부한다. enqueue와 실행 직전, 조회/검색/export/학습 시 재확인한다. grant version 변경은 승인·캐시 사용을 무효화한다. 권한 만료/철회는 현재 자료를 보유했다는 이유로 무시하지 않는다.

## C03 — BrandKit·BriefSnapshot

`BrandKit={id,version,name,palette:[{token,hex}],font_preferences:[],font_fallbacks:[],logos:[{asset_id,clear_space_ratio,min_width,aspect_locked}],tone,forbidden_terms:[],required_disclaimers:[],approved_claims:[],safe_margins:{top,right,bottom,left},locked_element_ids:[],created_at,updated_at}`.

palette1..12, logos0..4, font명1개≤120자·각목록≤10, 필수/금지/claim 목록 각각≤50·항목≤500자, name≤120자·tone≤2000자. safe_margins는 canvas 비율0..0.25, clear_space_ratio0..1. 폰트 이름·대체 전략만 저장하고 binary/임의URL은 받지 않는다. 로고의 자산 존재·alpha·사용권은 서버에서 검사한다.

POST/GET-list/GET-one/PUT `/api/brands`. PUT body=`{brand,expected_revision}`; JSON의 brand.version만 신뢰하지 않고 SQL `WHERE id=? AND version=?`로 CAS. 이전 snapshot과 새 version을 한 transaction에 저장한다.

`BriefSnapshot={...기존 Brief 필드,brand_id?,brand_version?,brief_hash,evidence_snapshot_id?}`. 신규 제작은 고정 BrandKit version을 사용한다. 가이드 업데이트가 과거 배치/scene을 재브랜딩하지 않는다. legacy brief-only 작업은 그대로 읽히고 내보내져야 한다.

## C04 — Jobs·승인·비용 원장

`JobRecord={id,parent_id?,kind,state,payload_hash,idempotency_key,payload,result_refs:[],attempt,lease_owner?,lease_token?,lease_until?,send_started,cancel_requested,provider_request_id?,error_code?,created_at,updated_at}`.

kind allowlist: plan_concepts/image_generate/image_edit/vision/correct_scene/source_sync/feature_extract/deletion. payload로 모듈·명령·workflow 코드를 실행하지 않는다. payload≤256KiB, idempotency key≤128자. state는 queued/running/succeeded/failed/needs_reconciliation/cancelled다. queued→running→terminal; queued→cancelled, running 취소는 cancel_requested다. 부모 배치는 각 상태 개수를 집계하고 partial을 별도 completeness 필드로 나타낸다.

`enqueue(kind,payload,key)`는 canonical JSON hash를 계산한다. 같은 key+hash는 같은 job, 다른 hash409. queue claim은 BEGIN IMMEDIATE의 짧은 transaction, 결과/heartbeat는 owner+lease token+state CAS. 기본 lease60s/heartbeat15s·worker동시성1. 네트워크 동안 DB lock을 유지하지 않는다.

전송 전 만료/실패만 안전 재큐. send_started 이후 timeout/프로세스 종료/응답 후 저장실패는 needs_reconciliation. 공급자 요청 ID로 안전한 상태 조회가 가능하면 대사하며 자동 유료 POST 재전송 금지. 새로운 retry는 사용자 재승인과 attempt lineage를 남긴다. 앱 멱등 key는 외부 공급자의 exactly-once 보장이 아니다.

`PricingCatalog={version,verified_at,official_source,models:...}`는 이미지/토큰/quality/size 단위의 검증된 상한을 제공한다. `BudgetQuote={id,request_hash,model,operation,pricing_version,max_units,upper_bound_micro_usd,expires_at}`. 모르는 요금/상한이면 blocked_budget_unknown. 금액은 정수 micro-USD, 최대 단위에 보수적 올림. 기본 live금액cap0, 실패도 호출수 제한에 반영한다.

`Approval={id,request_hash,quote_id,quote_hash,grant_versions,approved_by,approved_at,expires_at}`. 서버가 검증된 요청과 견적을 제시하고 사용자 명시 확인을 받는다. UI bool 하나가 다른 요청의 승인이 되지 못한다. 내용/모델/수량/근거/브랜드 변경은 새 quote와 승인이다.

API: POST `/api/quotes`는 순수 추정(외부 AI 호출0), POST `/api/approvals`는 승인할 quote/hash/동의만 검증·저장, POST `/api/jobs`는 approval_id+quote_id+payload와 Idempotency-Key를 대조한다. 기존 동기 AI API도 같은 권한/견적/승인 service를 통과하거나 명시적으로 차단한다. GET jobs Page/one, POST jobs/{id}/cancel. 승인 없이 기존 경로로 유료 호출할 수 있으면 실패다.

`BudgetReservation={job_id,quote_id,reserved_micro_usd,status,actual_micro_usd?,cost_basis:estimated|actual|unknown}`. enqueue+reserve는 원자 transaction, 일일 UTC·batch별 `settled+outstanding+new≤cap`. 중복 reserve/settle 멱등. 전송 전 취소만 해제, 전송 후 usage 없음은 예약 유지. 실제 과금이 예약보다 크면 숨기지 않고 기록/경보/후속 중단한다. 이 원장은 다른 앱의 계정 전체 지출을 통제하지 않는다.

## C05 — CreativeProvider

고정 Protocol 메서드는 `plan_concepts(request,context)`, `create_image(request,context)`, `edit_image(request,context)`, `extract_features(request,context)`다. 자연어 ScenePatch 교정은 별도 typed request를 받는 구조화 출력 handler가 사용한다. 모든 메서드는 transport·clock 주입 가능하며 DB저장/예산예약은 공통 service가 담당한다.

`CallContext={job_id,attempt,approval_id,request_hash,grant_versions,quote_id,timeout_seconds}`. `ProviderResult={model,model_revision?,provider_request_id?,usage?,structured_output?,image_bytes?,mime?,sent:true}`. 정해진 operation의 결과만 허용, finite/길이/bytes/mime/base64/schema를 검사한다. image bytes는 C02로 저장한다.

`Capabilities={provider,model_id,operations:[],sizes:[],qualities:[],mask_supported,configured,verification_state:unverified|verified,verified_at?,pricing_version?}`. 단순 설정됨이 live 성공/품질 검증됨을 뜻하지 않는다. health와 capabilities에서 hidden 유료 probe 금지.

`ProviderFailure={code,safe_message,sent:true|false|unknown,provider_request_id?}`. refusal·미완성 응답·잘못된 JSON은 정상 결과가 아니다. sent 불명확은 미확정으로 보존한다. 허용되지 않은 임의 URL을 다운로드하지 않는다. 자동 모델 전환·자동 paid 재시도·가짜 성공 fallback 금지.

OpenAI는 Images generations와 edits를 분리하고 child당 n=1. 카피/콘셉트/비전은 Responses 구조화 출력으로 검증한다. 공식 model/size/quality 계약은 구현시 재확인한다. 테스트는 MockTransport이며 FakeProvider 결과는 synthetic provenance로만 저장한다. 제품 이미지 모델은 코딩 모델 Terra와 별도 설정이다.

## C06 — ConceptPlan·BatchPlan·사람 fact review

`ConceptPlan={id,revision,brief_hash,brand_ref:{id,version},prompt_version,evidence_snapshot_id?,has_evidence,concepts:[],plan_hash,state:proposed|approved|superseded}`.

`Concept={id,message,visual_direction,composition_hint,asset_prompt,headline,subline,cta,locked_claims:[],evidence_mapping:[],uncertainties:[]}`. concept1..6, ID고유, message/각문구 길이는 Brief 상한, asset_prompt≤4000자, visual_direction≤2000자, 매핑은 실제 snapshot ID만. 단순 색상변경과 다른 메시지/구성/피사체의 아트디렉션을 구분한다.

첫 콘셉트 계획도 유료이면 호출 **이전** C04 견적/승인. 결과 저장이 이미지 생성을 자동 시작하지 않는다. 사용자 수정은 새 revision/hash. 잠금 사실·필수카피/로고 변경은 거부한다. 자연어의 모든 사실 오류를 자동 탐지할 수 있다고 가정하지 않는다.

`BatchPlan={id,revision,concept_plan_ref,brand_ref,evidence_snapshot_id?,items:[{concept_id,ordinal,model,prompt_hash,source_asset_id?,mask_id?,seed?,seed_supported}],layout_count,plan_hash,quote_id,approval_id}`. 이미지/콘셉트1..4, 총≤24, 레이아웃1..60, 기본 소량3장. 각 item은 고정 job_id/idempotency key와 연결하며 부모 작업의 이미지 비용을 이중 예약하지 않는다.

전체 enqueue 실패는 rollback. 부분 성공은 결과 유지·실패/미확정 수 표시. 성공이미지 duplicate hash도 표시하고 무단 재과금해 채우지 않는다. 실패를 fake/copied 이미지로 채워 완전성 수치를 올리지 않는다.

`FactReview={id,scene_or_copy_hash,brand_version,reviewer_id,reviewer_kind:human,reviewed_at,outcome:approved|rejected,notes?}`. 새 AI 카피는 unreviewed. content/brand 변경은 승인 무효. 모델이 reviewer_kind=human을 자동 생성할 수 없도록 명시적 사용자 입력 경로로만 저장한다. 검토는 광고·법률 인증을 뜻하지 않는다.

## C07 — SceneDocument·ScenePatch·mask

`SceneDocument={schema_version:2,design_id,revision,canvas:{width,height},brand_ref?,elements:[],asset_refs:[],provenance,scene_hash}`. canvas128..4096px, elements≤100, asset_refs≤24. 신규 preset1080×1080/1080×1350/1920×1080, 과거 preset은 legacy에서 보존한다.

공통 `Element={id,type:text|shape|image|logo,x,y,width,height,rotation,opacity,z,locked,...type_properties}`. geometry는 finite canvas좌표, 크기양수, opacity0..1, rotation-360..360. 요소ID고유, z는 안정 정렬. 잠금은 BrandKit에서 서버가 도출한다.

text 속성은 text/font_family/font_size/font_weight/fill/align/line_height/max_lines; shape은 허용 rect/ellipse·fill/stroke/radius; image/logo는 asset_id/variant/fit:contain|cover/crop:{x,y,width,height} 정규화0..1이다. 임의 SVG/HTML/CSS URL/JS/파일경로/외부href 금지. 로고 기본 contain/aspect 잠금. 래스터 이미지 안의 글자·피사체는 개별 native 요소가 아니다.

`ScenePatch={base_revision,operations:[{op,element_id,value}]}`. 허용op는 set_text/set_color/set_geometry/set_opacity/reorder/set_crop/add_element/remove_element. 각 value는 op별 typed schema, 임의 JSON pointer/setattr 금지. add_element는 검증된 전체요소, remove는 value 없음, reorder는 요소별z값. 로고·필수카피의 잠금을 해제하는 op는 없다.

전체 patch를 복제 scene에 적용→schema/권한/BrandKit 검사→새 hash→SQLCAS/이전 snapshot/새 revision transaction. 중간 invalid면 모두 rollback, stale409. undo/restore도 새로운 revision으로 만들며 철회된 자산은 되살리지 않는다. 선택/평가/내보내기 기록은 당시 revision을 계속 가리킨다.

예시(IDs는 테스트용):
```json
{"base_revision":3,"operations":[{"op":"set_text","element_id":"headline","value":{"text":"가볍게 시작하는 하루"}},{"op":"set_geometry","element_id":"headline","value":{"x":64,"y":96,"width":720,"height":180}}]}
```

`MaskRecord={id,source_asset_id,source_sha256,width,height,mask_sha256,edit_alpha_convention:one_is_edit}`. 원본과 같은 pixel dimensions, 내부 edit_alpha=1은 편집영역. provider mask의 반대 극성은 adapter에서 변환·테스트한다. 빈 mask는 거부. 좌표 변환은 zoom/DPR/letterbox/crop을 역변환하며 원본좌표를 기준으로 저장한다.

마스크 결과는 새asset. 원본 밖 보존을 약속하려면 preserve_outside 합성으로 원본좌표의 픽셀을 실제 보존하고 composited provenance 표시. provider에게 보낸 mask만으로 영역밖 동일하다고 주장하지 않는다. 적용은 사용자가 전후 결과 승인한 뒤 ScenePatch CAS다.

## C08 — Lint·렌더링·export

`LintIssue={code,severity:error|warning|review_required|unknown,element_id?,observed?,expected?,suggestion_patch?,auto_fix_allowed,rules_version}`. safe margins/overflow/로고비율·최소폭/필수·금지문구/브랜드색/권한을 분리한다. 단색 배경 대비4.5:1은 내부 본문 경고 기준이며 전체 WCAG 인증이 아니다. 이미지 배경은 측정 없으면 unknown/review_required.

브라우저 getBBox/getComputedTextLength는 fonts.ready 뒤 실제bounds를 검사한다. 근사 글자폭은 초기배치에만 사용. 긴한글을 조용히 잘라내거나 글꼴을 바꾸고 동일하다고 하지 않는다. 자동fix는 제안 patch, 승인전 적용0. final export는 필수error·필수검토 미완료를 차단한다. draft 저장은 가능하며 draft export는 final과 별도명시한다.

`ExportRequest={items:[{design_id,revision,scene_hash}],formats:[svg|png|json],mode:final|draft}`. 서버가 고정 snapshot에서 같은 결과를 렌더링한다. 통제된 headless renderer에 외부네트워크/파일URL/사용자스크립트 금지, timeout/메모리 제한. 클라이언트가 보낸 lint_pass=true를 신뢰하지 않는다.

`ExportManifest={schema_version,id,created_at,mode,items:[{design_id,revision,scene_hash,brand_ref,asset_hashes,files:[{name,sha256,mime,width?,height?}],lint_version,fact_review_refs,evidence_snapshot_id?,model_refs:[],font_metadata:[],warnings:[]}],engine_version}`.

파일명은 서버생성, 경로/ZIP traversal 금지. key·raw댓글·원문prompt·로컬절대경로·폰트binary를 기본 export에 포함하지 않는다. 누락폰트는 대체와 warning/확인; OS차이를 픽셀 동일 보장으로 표현하지 않는다. 전달 직전 권한재검사, 중간실패 temp정리. 이미 다운로드된 파일을 회수했다고 하지 않는다.

## C09 — SourceConfig·ObservationV2·수집

`SourceConfig={id,revision,provider,account_scope,login_family,api_version,capabilities,metric_definition_version,credential_ref,rights_ref,retention,contract_evidence_ref,enabled,state,last_success_at?}`. credential_ref는 allowlist 서버 환경변수명, 비밀값 자체가 아니다. arbitrary path/URL/command secret provider 금지. 상태는 configured/unverified/connected/expired/blocked/disabled.

connector canonical 메서드는 `verify_access()`, `list_creatives(cursor,since,limit)->SourcePage{items,next_cursor,coverage}`, `fetch_metrics(ids,window)`, `fetch_comments(id,cursor)`, `verify_deletion(id)`다. source API의 test-connection은 명시적으로 verify_access를 호출한다. 실제 로그인/endpoint/scope/보존 허용범위는 CL026 확인 계약이 선행한다. 페이지 누락/401/통신장애를 삭제로 판정하지 않는다.

`ObservationV2={id,source_config_id,external_id,asset_id?,parent_external_id?,media_type,metric_scope,published_at,observed_at,observation_window,metric_definition_version,category,traffic:paid|organic|unknown,metrics,comments_sample:[],comments_sample_coverage,rights_ref,is_demo}`.

`MetricValue={value:int|null,availability:observed|unavailable|not_authorized|not_supported|error,unit:event|impression|view|unique_account,scope,definition_id}`. count≥0이며 observed이면 value는 정수, 나머지 availability이면 null이다. likes/shares/reposts/saves/comments_count/views/impressions/reach를 각각 저장한다. 댓글 전체수와 실제 수집된 샘플목록은 다르다. 기간은 start/end·lifetime/interval 및 정의버전으로 식별한다.

정규화 예:
```json
{"likes":{"value":0,"availability":"observed","unit":"event","scope":"post","definition_id":"source-v1:likes:lifetime"},"shares":{"value":null,"availability":"not_supported","unit":"event","scope":"post","definition_id":"source-v1:shares:lifetime"}}
```

동일 `(source_config_id,external_id,observed_at,metric_definition_version)`는 unique. 같은key 다른내용409, 전체입력검증→원자import. 오래된 source_id/external_content_id 명칭은 legacy adapter에서 external_id로 변환하고 불명확한 정의는 unknown/legacy로 남긴다. `a or b`로 관측0을 다른분모로 대체하지 않는다. 캐러셀 부모실적을 여러 이미지의 독립실적으로 복제하지 않는다.

SourceRun은 source/config version/범위/checkpoint/status·coverage를 저장한다. 페이지자산/관측저장+checkpoint transaction 성공후 다음페이지. 신규수집과 metric refresh는 별도. source enabled/권한version은 실행중 재검사. 소유자가 실행한 CLI/worker가 중단되면 자동 수집이 계속된다고 표시하지 않는다.

미디어는 승인 connector가 제공한HTTPS allowlist만. DNS검사와 실제연결peer IP 일치 검증, private/reserved/linklocal/IPv6·redirect 우회 차단. streaming10MB/pixel20M상한·mime실decode, Authorization 다른host전달금지. source URL 저장 자체가 fetch승인은 아니다. 삭제tombstone을 재수집·복원에 적용한다.

## C10 — FeatureSet·반응·근거·검색

`FeatureSet={id,asset_id,asset_hash,schema_version,extractor,model_ref?,preprocess_version,observed,inferred,overrides:[],status,created_at}`. observed는 실제픽셀·scene·확인된원문, inferred는 `{attribute,value,grounding,uncertainty}`의구조화목록. 정확한폰트/문화맥락은 확정할수없으면 unknown. bbox는정규화0..1, text evidence span은실제입력에있어야한다. 민감특성·개인신원 추론금지.

`ReactionAspect={target:design|copy|product|price|service|brand|unknown,polarity:positive|negative|mixed|neutral|unknown,reason,evidence_span,uncertainty,source_comment_ref}`. 반어·문맥부족 unknown허용, 샘플수/coverage/전체수 분리. 댓글의명령문은untrusteddata이며 도구·코드로실행하지않음. 개인정보최소화/입력권한/삭제전파 필수.

`EmbeddingRecord={asset_id?,text_ref?,model_space_id,model_revision,processor_version,dimension,vector,created_at}`. float32 finite/L2 normalized, zero vector거부. model_space는모델+revision+processor+dimension이고서로다른공간을섞지않음. optional weights는승인후설치만, 앱/CI기동자동다운로드금지. 미설치면keyword-only 표시.

cache key=(asset_hash,extractor,model_space_id,schema_version,preprocess_version). 단계별pixel/semantic/embedding 부분성공 구분, 실패를가짜기본값으로채우지않는다. 권한은cache hit에도재확인, 철회시queued작업·cache·벡터·index무효화.

cohort는source/account/category/traffic/format/window/post-age bucket/metric definition/분모unit로 분리. 비율은 실제event count / 양의관측분모 ×1000, 분모0/null이면null. impressions/views/reach/followers자동대체 금지. 같은content는cutoff이전최신비교가능snapshot 한개. smoothing은versioned휴리스틱, 표본부족·예산/게시자/노출알고리즘교란을보정완료로표현하지않음.

`EvidenceQuery={query_text?,query_asset_id?,purpose,source_ids:[],category?,traffic?,window?,cutoff,top_k}`; k1..20. 권한·삭제·DEMO·시간·비교가능성 필터후 키워드/구조화특징+동일embedding cosine 후보를 RRF(k=60)로 융합, stable ID tie. 결과관련성은 고객선호확률이아님. vector미설치면명시적fallback.

`EvidenceSnapshot={id,query,filter_hash,cutoff,items:[{asset_id,observation_id,feature_version,model_space_id?,rights_versions,source_url,relevance_explanation,comparability,uncertainties}],snapshot_hash,created_at,state:valid|invalidated}`. 제작선택최대5개. generation/model_input목적을추가검사하고analysis-only특징을prompt로우회전송하지않는다. immutable은동일계약기록을뜻하며삭제대상의원문보존예외가아니다. 삭제후snapshot본문/cache비활성·tombstone만유지한다.

## C11 — 선택·학습·평가·게시 결과

`PreferenceEvent={id,client_event_id,actor_id,session_id,a:{design_id,revision,scene_hash},b:{...},display_order,outcome:A|B|tie|skip,reason?,source:human_designer|real_panel|synthetic|ai_judge,created_at,consent_for_learning,replaces_event_id?}`. actor는local pseudonymous식별자이며인구학프로필이아니다. real_panel과개인디자이너자료를임의합산하지않는다. 테스트/AI source를human으로변환금지.

동일client_event_id+hash멱등, 다른내용409. 같은시안비교거부, 당시revision이유효한지검증. 재평가는이벤트append, snapshot불변. tie/skip을승패로채우지않음. 최종선택도당시revision이며후속편집에자동승계하지않는다.

`DatasetManifest={id,task,actor_scope,source_refs,feature_versions,rights_versions,cutoff,exclusion_counts,group_rule,split_rule,seed,train_refs,validation_refs,test_refs,manifest_hash}`. 소스content/campaign/near-duplicate/비교쌍연결요소를같은group으로 묶고시간cutoff를적용. 한group뿐이거나시간제약과충돌하면insufficient_data. scaler/feature선택은train만fit. evaluation test manifest는튜닝전에동결한다.

개인랭커는실제동의한선택의feature차이+L2 logistic, deterministicseed/maxiterations, 안전한JSON계수/scaler/featureorder/version/hash만저장. pickle/joblib로드금지. model artifact저장≠active. source권한철회/feature mismatch이면비활성·재학습필요.

promotion 제안기준은유효holdout decisive pairs≥30·독립group≥5, baseline대비accuracy차이의group bootstrap95% CI하한>0과소유자승인. 이숫자는활성화안전장치이지통계충분성보장이아니다. 검정/튜닝기준은사전등록. 미달/불확실/자료없음은inactive+규칙fallback으로L2사용가능, 검증된성과주장금지.

`CandidateScore={scene_ref,hard_violations,technical_checks,brand_fit,diversity,evidence_relevance,personal_preference:null|value,scoring_version,config_hash,evidence_snapshot_id?}`. hard-error가다른점수로상쇄되지않음. MMR lambda0.7은제안초기값, embedding없으면spec/hash다양성. 선호/CTR확률은검증없으면null.

`PublicationLink={id,export_manifest_id,scene_ref,source_config_id,external_content_id,published_at,campaign?,traffic,verification_state:unverified|verified_by_user,transformation_notes?,observation_refs:[],prediction:null|validated_model_ref,revision}`. exactexport와게시내용은사용자가대조한다. 링크만으로동일한creative로단정하지않음. 실제게시/광고집행은자동화하지않는다. 소스삭제/철회는outcomecache에도전파한다. 관찰결과의상승을AI인과효과로표현하지않는다.

## 계약 변경·테스트 규칙

새schema는owner issue의검증 fixture·정상/실패/경계/동시성테스트와함께변경한다. 여기언급된파일·메서드·테스트는계획이며구현됐다고가정하지않는다. field명/단위/상태/권한/멱등·CAS/가격상한을임의수정하지않는다. 기존호환adapter와새contract를분리하고같은이름의module파일/패키지를동시에두지않는다.

권한·비용·mask극성·metric단위·scene revision·holdout경계는각각negative regression이필수다. 일반CI의live paid0, 사람평가는명시적사람증거, 모델·가중치·외부계정검증은별도승인이다. 전체합격선은MVP_ACCEPTANCE.md와CL059검사기/CL060최종인수에연결한다.
