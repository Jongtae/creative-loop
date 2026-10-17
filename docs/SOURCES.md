# 실제 구현에 참고한 공식 자료

아래는 원문 보고서의 전체 참고문헌이 아니라 이번 구현의 API 계약·라이브러리 사용·수식·GitHub 게시 방식에 확인한 1차 자료다. 외부 API는 계정 권한, 선택 모델, 서비스 변경에 따라 달라질 수 있으므로 실호출 전에 재확인한다.

| 영역 | 공식 자료 | 코드에 반영한 부분 |
|---|---|---|
| OpenAI 이미지 생성·편집 | https://developers.openai.com/api/docs/guides/image-generation | Image API 생성/편집, PNG base64 응답 |
| OpenAI 이미지 프롬프팅 | https://developers.openai.com/api/docs/guides/image-prompting | 텍스트 생성과 기존 이미지 편집 경로 구분 |
| OpenAI 비전 | https://developers.openai.com/api/docs/guides/images-vision | Responses의 input_image |
| OpenAI Responses | https://developers.openai.com/api/reference/resources/responses/methods/create | 입력 구조, 저장 비활성화, 완료 상태·출력 읽기 |
| OpenAI 구조화 출력 | https://developers.openai.com/api/docs/guides/structured-outputs | JSON schema strict 출력과 로컬 재검증 |
| FastAPI 테스트 | https://fastapi.tiangolo.com/tutorial/testing/ | TestClient 기반 API 테스트 |
| Pillow Image | https://pillow.readthedocs.io/en/stable/reference/Image.html | 이미지 열기·픽셀 처리·변환 |
| W3C 대비 이해 | https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html | 상대 휘도/대비율 참고. 전체 접근성 적합성 인증 아님 |
| GitHub CLI | https://cli.github.com/manual/gh_repo_create | 비공개 새 저장소, local source/remote/push |

소셜 플랫폼의 약관/정책을 이 프로젝트의 기술 문서만으로 충족한다고 판단하지 않는다. 실제 수집 어댑터를 추가하는 시점에 해당 플랫폼의 공식 정책·허가 목적·데이터 보존/삭제 요구를 다시 검토해야 한다.
