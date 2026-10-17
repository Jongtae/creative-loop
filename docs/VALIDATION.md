# 검증 결과 / v0.1.0

## 실제 실행한 검사

| 검사 | 결과 | 사용 조건 |
|---|---|---|
| Python 자동 테스트 | **110 passed** | 2026-10-17, 프로젝트 `.venv`의 Python 3.12.12와 고정 requirements |
| JavaScript 문법 | 통과 | `node --check creative_loop/static/app.js` |
| GitHub 게시 셸 스크립트 문법 | 통과 | `bash -n scripts/publish_github.sh` |
| Chromium UI 흐름 | **10 passed** | 2026-10-17, 실제 HTML/CSS/JS + 실제 FastAPI/SQLite, `network` 전송 |
| 외부 AI 모델 호출 | **0회** | HTTPX MockTransport / 테스트 대체 응답 사용 |
| 실제 SNS 연결·수집 | **0개** | 합성 예제와 생성된 테스트 입력만 사용 |

## 110개 테스트가 검증한 범위

재현 가능한 60개 시안 스펙, 6레이아웃×3비율 SVG, 입력 제한·색상/텍스트 이스케이프, 이미지 파일·해상도·재사용 권한, 관측 입력 전체 검증 후 트랜잭션 저장, 중복·시간대·미수집 값 구분, 댓글 기본 개인정보 최소화, 같은 조건의 근거/생성 참고, 편집 충돌·버전, 선택·ZIP, 개인 선택 기록, 데이터 연결 해제·삭제를 검증했다.

외부 AI는 Responses와 Image API의 요청 스키마, 생성/수정 엔드포인트, 이미지 base64 처리, 거부·오류·비밀 정보 비노출, 요청 한도, 사용권·동의, 반환 자산의 SVG 연결을 **모의 응답**으로 검증했다. 모델 자체가 요청을 받아들였거나 이미지가 높은 품질로 생성됐다는 증거가 아니다.

폴더 워처는 성공 파일만 기록, 동일 내용 재전송 방지, 변경 파일 반영, 실패 재시도 대상 보존, 심볼릭 링크 건너뛰기를 검증했다. 실제 외부 데이터 공급 시스템과의 정기 내보내기는 연결하지 않았다.

병렬 계획 테스트 41개는 68개 작업 DAG의 ID·의존성·순환·리소스 충돌·필수 작업의 최종 인수 연결과 dry-run 후보 계산을 검증했다. 지속 실행기, 모델 호출, GitHub 쓰기, lease 또는 자동병합을 실행하거나 검증한 것은 아니다.

## 브라우저 검사 10개

1. 화면에서 12개 시안 생성.
2. 헤드라인 변경과 revision 저장.
3. 같은 배치의 A/B 선택 기록.
4. 브라우저 Canvas에서 1080×1080 PNG 생성.
5. 선택된 시안의 SVG·JSON ZIP 내보내기.
6. 이미지 업로드와 자동 픽셀 특징 저장.
7. JSON 관측 6개 가져오기와 DEMO 표시.
8. 저장된 작업 이력 다시 열기.
9. 390px 모바일 레이아웃의 가로 넘침 없음.
10. 브라우저 JavaScript 예외 없음.

정확한 실행 결과는 `browser-results.json`, 화면은 `screenshots/`에 보존했다. 이미지 업로드 테스트 파일은 단색 합성 테스트 픽셀이며, 소셜에서 수집한 실제 디자인이 아니다.

## 중요한 브라우저 경계

2026-10-17의 Chromium 검사는 `--transport network`로 로컬 서버의 실제 HTTP 전송을 사용했다. 이 결과는 공개 네트워크, 리버스 프록시, 배포 환경, 다른 OS의 폰트 렌더링 또는 CSP의 실제 배포 적용을 검증하지 않는다. 보안 헤더·Host·Origin·인증·업로드 제한은 API 테스트에서 별도 확인했다.

## 아직 실행하지 않은 검증

- 실제 OpenAI API 키/선택 모델을 통한 생성·편집·비전·교정, 한국어 품질, 지연·비용.
- 승인된 소셜 데이터 소스의 실제 인증·수집·갱신·삭제.
- 데이터 기반 개인 선택 모델의 홀드아웃 성능과 고객 성과 예측.
- 다양한 OS의 폰트/브라우저 PNG 차이, 공개 네트워크·리버스 프록시·배포 환경의 브라우저 E2E.
- Docker 빌드/실행, GitHub 원격 저장소 생성·push·Actions 실행.
- 다중 사용자, 접근 권한 분리, 지속 부하, 장애 복구, 정식 보안 심사.

## 재현 명령

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m playwright install chromium
python scripts/browser_smoke.py --transport network --artifacts artifacts
# 네트워크를 쓰지 않는 로컬 UI 검사
python scripts/browser_smoke.py --transport inprocess --artifacts artifacts
```

테스트는 임시 DB를 사용한다. pytest는 사용자의 외부 API 키·APP_TOKEN 환경을 테스트 중 분리하며, 외부 AI 테스트는 모의 전송만 이용한다. 로컬 `data/`가 모듈 로딩으로 생성될 수 있으나, 실제 테스트 데이터는 전달된 임시 디렉터리에 저장된다.

## 완료의 의미

v0.1의 로컬 제작 흐름과 외부 API **연동 코드**를 준비하고 검증했다. 원격 GitHub 프로젝트나 전체 소셜 기반 AI 크리에이티브 시스템을 배포·완료했다고 표현하지 않는다. 다음 마일스톤의 첫 인수 조건은 실제 계정에서 명시적으로 승인한 소량의 API 호출과 결과 검토다.
