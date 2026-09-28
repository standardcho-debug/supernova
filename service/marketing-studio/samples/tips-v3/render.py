"""tips.html → out/*.png 미리보기 렌더"""
import asyncio, os
from playwright.async_api import async_playwright
H = os.path.dirname(os.path.abspath(__file__))
NAMES = {'s1':'01_표지','s2':'02_질문2개','s3':'03_과제명_전후','s4':'04_확장지도','s5':'05_과제명공식','s6':'06_AX시스템지도','s7':'07_무료AX진단','ad':'광고_피드'}
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        pg = await b.new_page(viewport={'width':1080,'height':1350})
        await pg.goto('file://' + os.path.join(H, 'tips.html')); await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(500)
        os.makedirs(os.path.join(H, 'out'), exist_ok=True)
        for i, n in NAMES.items():
            await pg.locator('#' + i).screenshot(path=os.path.join(H, 'out', f'TIPS_v3_{n}.png'))
        await b.close()
asyncio.run(main())
