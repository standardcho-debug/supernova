import asyncio,os
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        pg=await b.new_page(viewport={'width':1080,'height':1350},device_scale_factor=1)
        await pg.goto('file://'+os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),'tips.html')))
        await pg.evaluate('document.fonts.ready')
        await pg.wait_for_timeout(500)
        names={'s1':'TIPS_캐러셀_01_표지','s2':'TIPS_캐러셀_02_큰그림','s3':'TIPS_캐러셀_03_기술축','s4':'TIPS_캐러셀_04_사업축','s5':'TIPS_캐러셀_05_진단CTA','ad':'TIPS_광고_피드_4x5'}
        for i,n in names.items():
            await pg.locator('#'+i).screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)),'out',f'{n}.png'))
        await b.close()
asyncio.run(main())
