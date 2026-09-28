"""tips.html 렌더 결과에서 레이어(도형·텍스트·이미지) 좌표를 뽑아 layers.json 으로 저장.
Canva 이관용 PPTX(build_pptx.py)의 입력. 문구·색·위치는 HTML이 정본이다."""
import asyncio, json, os
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

JS = r"""
(id) => {
  const f = document.getElementById(id);
  const F = f.getBoundingClientRect();
  const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if(!m) return null;
    const p = m[1].split(',').map(s=>parseFloat(s)); return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}; };
  const over = (top, bot) => ({r:top.r*top.a+bot.r*(1-top.a), g:top.g*top.a+bot.g*(1-top.a), b:top.b*top.a+bot.b*(1-top.a), a:1});
  const hex = c => '#'+[c.r,c.g,c.b].map(v=>Math.round(v).toString(16).padStart(2,'0')).join('').toUpperCase();
  // 요소 뒤의 실효 배경색 (조상 배경을 합성)
  const bgUnder = el => { const chain=[]; for(let e=el; e && e!==document.body; e=e.parentElement){
      const c=parse(getComputedStyle(e).backgroundColor); if(c&&c.a>0) chain.push(c); if(e===f) break; }
    let acc={r:255,g:255,b:255,a:1}; for(let i=chain.length-1;i>=0;i--) acc=over(chain[i],acc); return acc; };
  const rel = r => ({x:r.left-F.left, y:r.top-F.top, w:r.width, h:r.height});
  const out = {bg: hex(parse(getComputedStyle(f).backgroundColor)), layers: []};
  const boxed = e => { const s=getComputedStyle(e); const c=parse(s.backgroundColor);
    return (c&&c.a>0) || parseFloat(s.borderTopWidth)>0 || s.backgroundImage!=='none'; };
  const absorbable = e => { const s=getComputedStyle(e); return s.display==='inline' && !boxed(e) && e.tagName!=='IMG'; };
  const all = [...f.querySelectorAll('*')];
  for (const e of all) {
    const s = getComputedStyle(e);
    if (s.display==='none' || s.visibility==='hidden') continue;
    const r = e.getBoundingClientRect(); if (!r.width || !r.height) continue;
    // 1) 도형
    if (boxed(e) && e.tagName!=='IMG' && !e.dataset.skipShape) {
      const c = parse(s.backgroundColor); const radius = parseFloat(s.borderTopLeftRadius)||0;
      const parentBg = bgUnder(e.parentElement);
      const L = {kind:'shape', ...rel(r), radius: Math.min(radius, Math.min(r.width,r.height)/2),
                 ellipse: s.borderTopLeftRadius==='50%' || radius>=Math.min(r.width,r.height)/2 && r.width===r.height};
      if (c && c.a>0) L.fill = hex(over(c, parentBg));
      if (parseFloat(s.borderTopWidth)>0) { L.line = hex(over(parse(s.borderTopColor), parentBg)); L.lineW = parseFloat(s.borderTopWidth); L.dash = s.borderTopStyle==='dashed'; }
      if (s.backgroundImage.includes('gradient') && e.tagName==='B') { L.fill='#9BEBDF'; L.y+=r.height*0.6; L.h=r.height*0.4; }
      L.name = (e.className||e.tagName).toString();
      out.layers.push(L);
    }
    // 2) 이미지
    if (e.tagName==='IMG') { out.layers.push({kind:'image', src:e.getAttribute('src'), ...rel(r), name:'img'}); continue; }
    // 3) 텍스트 루트: 직접 텍스트 노드를 가진, 흡수되지 않는 요소
    const hasText = [...e.childNodes].some(n=>n.nodeType===3 && n.textContent.trim());
    if (!hasText) continue;
    if (e.tagName==='B' && e.parentElement.childNodes.length>1) continue;  // 하이라이트 b 는 부모 텍스트에 흡수
    if (absorbable(e) && e.parentElement && e.parentElement!==f) {
      // 부모가 텍스트 루트면 거기에 흡수된다
      let p=e.parentElement; while(p && absorbable(p)) p=p.parentElement;
      if (p && [...p.childNodes].some(n=>n.nodeType===3 && n.textContent.trim()) || p && [...p.children].some(c=>c===e||c.contains(e))) {
        const pHasText = [...p.childNodes].some(n=>(n.nodeType===3 && n.textContent.trim()));
        if (pHasText) continue;
      }
    }
    const lines=[[]]; const rects=[];
    const walk = (node) => {
      for (const n of node.childNodes) {
        if (n.nodeType===3) { let t=n.textContent.replace(/\s+/g,' '); if(!t.trim()) continue;
          const ps = getComputedStyle(n.parentElement); const col=parse(ps.color);
          const rg=document.createRange(); rg.selectNodeContents(n); for(const q of rg.getClientRects()) rects.push(q);
          lines[lines.length-1].push({t, size:parseFloat(ps.fontSize), weight:parseInt(ps.fontWeight),
            color: hex(over(col, bgUnder(n.parentElement))), strike: ps.textDecorationLine.includes('line-through'),
            ls: parseFloat(ps.letterSpacing)||0});
        } else if (n.nodeName==='BR') lines.push([]);
        else if (n.nodeType===1 && absorbable(n)) walk(n);
        else if (n.nodeType===1 && n.tagName==='B') walk(n);  // 하이라이트 b 는 도형+텍스트 흡수
      }
    };
    walk(e);
    if (!rects.length) continue;
    const x0=Math.min(...rects.map(q=>q.left)), y0=Math.min(...rects.map(q=>q.top)),
          x1=Math.max(...rects.map(q=>q.right)), y1=Math.max(...rects.map(q=>q.bottom));
    for (const ln of lines) { if(ln.length){ ln[0].t=ln[0].t.replace(/^ /,''); ln[ln.length-1].t=ln[ln.length-1].t.replace(/ $/,''); } }
    out.layers.push({kind:'text', x:x0-F.left, y:y0-F.top, w:x1-x0, h:y1-y0, h1: rects[0].height, lines: lines.filter(l=>l.length),
      lh: s.lineHeight==='normal'? null : parseFloat(s.lineHeight), size: parseFloat(s.fontSize),
      align: s.textAlign, name:(e.className||e.tagName).toString()});
  }
  return out;
}
"""

NOTO = os.path.join(HERE, '.fontsource', 'package')  # npm pack @fontsource/noto-sans-kr 후 압축 해제

# Canva에는 Pretendard가 없어 Noto Sans KR(400/700만 지정 가능)로 대체된다.
# 측정도 같은 폰트로 해야 배지·형광펜·칩 위치가 Canva 렌더와 맞는다.
NOTO_PREP = r"""
(base) => {
  for (const w of [400, 700]) { const l=document.createElement('link'); l.rel='stylesheet'; l.href=base+'/'+w+'.css'; document.head.appendChild(l); }
  const st=document.createElement('style'); st.textContent="body{line-height:1.2} *{font-family:'Noto Sans KR' !important}"; document.head.appendChild(st);
  for (const e of document.querySelectorAll('#s1 *,#s2 *,#s3 *,#s4 *,#s5 *,#ad *')) {
    const w=parseInt(getComputedStyle(e).fontWeight); e.style.fontWeight = w>=600 ? '700' : '400'; }
}
"""

PREP = r"""
() => {
  // ::before 체크 표시를 실제 텍스트로
  document.querySelectorAll('.checks span').forEach(s=>{ const t=document.createElement('i'); t.textContent='✓ '; t.style.color='#2DD4BF'; t.style.fontStyle='normal'; s.prepend(t); s.classList.add('noBefore'); });
  const st=document.createElement('style'); st.textContent='.checks span.noBefore:before{content:none}'; document.head.appendChild(st);
  // 광고 지도 영역은 미리 합성한 이미지 1장으로 대체(클리핑+그라데이션)
  const ad=document.querySelector('.adshot img'); ad.dataset.composite='1';
}
"""

async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        pg = await b.new_page(viewport={'width':1080,'height':1350})
        await pg.goto('file://' + os.path.join(ROOT, 'tips.html'))
        await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(400)
        await pg.evaluate(PREP)
        await pg.evaluate(NOTO_PREP, 'file://' + NOTO)
        await pg.wait_for_timeout(300); await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(300)
        res = {}
        for sid in ['s1','s2','s3','s4','s5','ad']:
            res[sid] = await pg.evaluate(JS, sid)
        # 광고 지도: 컨테이너 좌표(클리핑 박스)
        res['ad']['adshot'] = await pg.evaluate("""()=>{const f=document.getElementById('ad').getBoundingClientRect();
            const a=document.querySelector('.adshot').getBoundingClientRect(); const i=document.querySelector('.adshot img').getBoundingClientRect();
            return {x:a.left-f.left,y:a.top-f.top,w:a.width,h:a.height, ix:i.left-a.left, iy:i.top-a.top, iw:i.width, ih:i.height}}""")
        await b.close()
    json.dump(res, open(os.path.join(HERE, 'layers.json'), 'w'), ensure_ascii=False, indent=1)
    for k, v in res.items():
        print(k, v['bg'], sum(l['kind']=='text' for l in v['layers']), 'text /', sum(l['kind']=='shape' for l in v['layers']), 'shape /', sum(l['kind']=='image' for l in v['layers']), 'img')

asyncio.run(main())
