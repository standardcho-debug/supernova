# supernova — 고객사 SNS 콘텐츠 생성 파이프라인 (프로토타입)

코파운더 고객사의 히스토리(사업계획·요구사항·불만사항·매출현황)를 근거로 네이버 블로그·인스타그램·유튜브
콘텐츠 초안을 만드는 파이프라인의 1~4단계 프로토타입입니다.

## 스코프

| 단계 | 내용 | 이 저장소에 포함? |
|---|---|---|
| 1. 히스토리 수집 | 고객사 문서를 `ClientProfile`로 정규화 | O |
| 2. 브리프 생성 | 히스토리 근거를 인용한 채널별 소재 제안 | O |
| 3. 초안 생성 | 채널별 카피/스크립트 생성 | O |
| 4. 승인 게이트 | 대표 승인/반려 상태 관리 | O |
| 5. 게시·성과수집 | 네이버 블로그/인스타/유튜브 실제 업로드, 반응 수집 | **제외** |

5단계를 제외한 이유: 각 채널의 공식 게시 API 연동, 계정 권한, 게시 정책은 별도로 검토해야 하는 영역이고,
현재 팀에 매체 계정을 직접 운영해본 경험이 없다는 점(사업계획서에 명시된 공백)과도 맞물립니다. 이 저장소는
"소재 발굴 → 초안 작성 → 대표 승인"까지를 자동화 대상으로 두고, 승인 이후 실제 업로드는 사람이 하거나
향후 별도 연동으로 붙이는 것을 전제로 설계했습니다. `ApprovalGate`에 `publish()`가 없는 것은 실수가
아니라 의도입니다.

## 설계 원칙

- **근거 없는 소재 금지**: `ContentBrief.source_evidence`는 고객사 히스토리에서 실제로 나온 문구를
  인용해야 합니다. 근거 없이 일반적인 마케팅 문구를 만들면 대행사와 다를 게 없다는 것이 사업계획서의
  핵심 차별점이라, 이 필드를 필수로 뒀습니다.
- **대표 승인은 축소가 아니라 유지**: 자동화가 없애는 것은 브리핑·왕복이지, 대외 콘텐츠 최종 확인이
  아닙니다. `ApprovalGate`는 이 경계를 코드로 강제합니다.
- **LLM/데이터소스는 인터페이스로 분리**: `HistorySource`, `LLMClient`는 프로토콜(protocol)입니다.
  실제 Cofounder 연동과 실제 모델 호출은 이 인터페이스 뒤에서 나중에 갈아끼울 수 있고, 지금은
  `StaticHistorySource`(JSON 픽스처)와 `TemplateLLMClient`(고정 출력)로 네트워크·API 키 없이
  전체 흐름을 실행·테스트할 수 있습니다.

## 아직 안 되어 있는 것 (다음 단계로 넘길 것)

- `CofounderHistorySource`는 `DocumentsFetcher` 인터페이스만 정의했고, 실제 Cofounder MCP
  문서 조회(`search_documents`/`list_documents`)와 연결하는 구현체는 없습니다.
- `AnthropicLLMClient`는 실제 SDK 호출 골격만 있고, 브리프/초안 생성 프롬프트가 실제로 안정적인
  JSON을 반환하는지는 검증되지 않았습니다(현재는 JSON 파싱 실패 시 그대로 에러를 던집니다 — 재시도나
  포맷 교정 로직 없음).
- 채널별 "불만사항→소재" 분류(`CofounderHistorySource`의 `bug` 키워드 매칭)는 임시 규칙이며,
  실제 Cofounder 문서 스키마에 맞는 태깅 체계로 교체가 필요합니다.
- 실제 고객사 데이터는 이 저장소에 넣지 않았습니다(`sns_marketing_agent/fixtures/`는 가상 예시).
  실제 연동 테스트는 Cofounder 접근 권한이 있는 별도 환경에서 진행해야 합니다.

## 실행

```bash
pip install -r requirements.txt
python -m sns_marketing_agent.pipeline --client-id demo-bakery --channels naver_blog instagram youtube
pytest
```
