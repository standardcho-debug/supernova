# Canva 편집본 이관 (TIPS v1)

`tips.html` 시안을 **문구·구성·색 그대로** Canva의 편집 가능한 디자인으로 옮기는 파이프라인.
Canva 자유생성(Magic Design 등)은 쓰지 않는다 — Canva는 편집·배포 도구로만 쓴다.

## 흐름
1. `extract.py` — Playwright로 `tips.html`을 렌더하고 도형·텍스트·이미지 좌표를 `layers.json`으로 추출
   - 측정 폰트를 **Noto Sans KR(400/700)** 으로 바꿔서 잰다. Canva에 Pretendard가 없어 이 폰트로 대체되므로,
     같은 폰트로 재야 배지·형광펜·체크칩 위치가 Canva 렌더와 맞는다.
   - 반투명(rgba·opacity)은 배경과 미리 합성한 단색으로 넣는다(Canva에서 색 편집이 쉬움).
2. `build_pptx.py` — `layers.json` → PPTX 2종 (1080×1350px, 텍스트는 전부 텍스트박스)
   - `TIPS_캐러셀_5p.pptx`, `TIPS_광고_피드_4x5.pptx`
   - 광고 하단 지도(둥근 클리핑 + 크림색 페이드)만 `ad_map_composite.png` 한 장으로 미리 합성
3. Canva `import-design-from-url` 에 이 저장소의 raw URL(커밋 SHA 고정)을 넘겨 가져온다.
   컨테이너 네트워크 정책상 canva.com 직접 업로드가 막혀 있어 공개 raw URL을 경유했다.

```bash
npm pack @fontsource/noto-sans-kr && mkdir -p .fontsource && tar xzf fontsource-noto-sans-kr-*.tgz -C .fontsource
python3 extract.py && python3 build_pptx.py
```

## 원본 대비 알려진 차이
| 항목 | 원본(HTML) | Canva 편집본 |
|---|---|---|
| 폰트 | Pretendard 500/600/700/800 | Noto Sans KR 400/700 (500→400, 600·800→700) |
| 가운데 정렬 텍스트 | flex 중앙 | 작은 도형 안 텍스트만 도형 크기 박스+가운데 정렬, 나머지는 좌측 정렬 고정 위치 |
| 5장 스크린샷 카드 그림자 | box-shadow | 없음 |
| 5장 스크린샷 모서리 | 이미지 10px 라운드 | 직각 |
| 3장 형광펜 | 텍스트 하단 40% 그라데이션 | 텍스트 뒤 민트 사각형(별도 레이어) — 문구 길이 바꾸면 수동 조정 |
| 광고 지도 | 이미지+CSS 페이드 | 합성 이미지 1장(페이드 포함) |
