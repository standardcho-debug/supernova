# co·founder — AX 컴퍼니빌더 홈페이지 리뉴얼

`index.html` 단일 파일(HTML/CSS/JS, 외부 의존성은 Google Fonts뿐)로 된 리뉴얼 시안입니다.
브라우저로 바로 열어 확인할 수 있고, 섹션 단위로 나뉘어 있어 `supernova-platform` Next.js 마케팅 홈으로 옮기기 쉽습니다.

## 섹션 구성
1. Hero: 결정 노드가 사람 레인에서 AI 레인으로 옮겨가는 미니 지도
2. 대상: 초기창업기업(업력 3년 이하) · AX 전환이 필요한 기존 사업자
3. 현실: MIT NANDA 2025 (95% / 5% / 90%)
4. AX 정의: AI 도입 vs AX, 권한 3단계(사용·변경·결정)
5. **AX 사업화 진단**: 이익식(결정 노드) + 결정지도 = AX 시스템 지도 (00푸드 예시, 인터랙티브)
6. **팁스 사업화**: AX 지도 → AI 기술개발 과제 → TIPS 전략 → 구축
7. 서비스: 진단 → 전환(4주 파일럿) → 운영, 일하는 방식(MCP 대화 루프)
8. 사례: 00푸드 월 200만 → 1억, 스태프 동일
9. 비교표 · 가격 구조 · 팀 · 사업계획서(무료, 서브) · FAQ · 진단 신청 폼

## 채워야 할 것
- 신청 폼 전송: 현재는 화면 안에서만 처리합니다. `/launch#consult` 등 실제 접수 API에 연결이 필요합니다.

## 비교 시안: Taste Skill 적용본
- `index.html`은 Taste Skill 적용본을 기준으로 합친 현재 버전입니다(권한 3단계 막대 복원).
- `index_tasteskill.html`: 기존 `index.html`을 [Taste Skill](https://github.com/Leonxlnx/taste-skill)(MIT)의 `redesign-existing-projects` 점검 기준으로 손본 비교용 버전입니다. 브랜드 규칙(워드마크·로고·색·Google Fonts)은 그대로 유지했습니다.
- 스킬 원본은 `.claude/skills/`에 있어, 이 레포를 여는 Claude Code 세션이 자동으로 인식합니다.

## 비교 시안: DeepSales UX 패턴 적용본
- `index_deepsales.html`: 현재 `index.html`에 deepsales.com의 UX 패턴 3가지를 적용한 비교용 버전입니다.
  1. 히어로 바로 아래 실적 띠(7년+ · 7개사 · 38건 · 50×)
  2. 서비스 섹션을 아코디언 + 그림 패널로 (진단=깊이 1 지도, 전환=레인 이동 애니메이션, 운영=깊이 2 지도)
  3. "통제권은 항상 대표님께" 순환 다이어그램 섹션
