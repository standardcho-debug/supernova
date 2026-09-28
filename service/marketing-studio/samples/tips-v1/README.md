# TIPS 캐러셀 시안 v1 (코파운더 자사 파일럿)

브리프 `TIPS 준비, 어디서부터 해야 할까요` → 인스타그램 캐러셀 5장 + 피드 광고 1장 (1080×1350, 4:5).
Claude가 카피·레이아웃을 직접 설계한 수작업 시안. Canva 편집본 제작의 원본으로 쓴다.

## 파일
| 경로 | 내용 |
|---|---|
| `tips.html` | 6장 전체 소스 (HTML/CSS, Pretendard) |
| `render.py` | Playwright로 `out/*.png` 재생성 (`python3 render.py`) |
| `out/` | 렌더 결과 PNG 6장 |
| `src/logo_symbol.png`, `src/logo_word.png` | 워드마크 락업(다크)에서 잘라낸 심볼·워드마크 |
| `src/map_crop.png` | spnv-platform 결정지도(이익식) 화면 크롭 — 자사 데이터, 공개 승인됨(2026-09-28) |
| `fonts/` | Pretendard (SIL OFL 1.1) |
| `canva/` | Canva 편집본 이관 파이프라인(HTML→레이어 추출→PPTX→Canva 가져오기). `canva/README.md` 참고 |

## 브랜드 토큰 (실제 로고에서 추출)
- 네이비 `#16243D` · 터쿼이즈 `#2DD4BF` · 진한 터쿼이즈 `#0F9E8C` · 민트 `#E3F8F4` · 크림 `#FAF8F3`
- 브랜드킷에 적힌 `#1E40AF`는 실제 로고와 다름 → 위 값을 우선

## 카피 원칙 (브리프 must_avoid)
- TIPS 선정 보장·확률 표현 금지, 최상급 금지, 지어낸 숫자 금지
- 내용은 대표 TIPS 덱(슬라이드 8·9·10) 로직을 SNS 문장으로 재작성한 것 — 새 주장 추가 금지
- 타 고객사 이름·인물이 보이는 `Video Screen*` 자산은 사용 금지 (C4 마스킹)

## Canva 이관 원칙
- Canva 자유생성(Magic Design 등)으로 내용 재구성 금지 — 정보 왜곡 리스크 (2026.08 테스트)
- 이 시안의 문구·구성·색을 그대로 편집 가능한 Canva 디자인으로 옮기는 것이 목표
