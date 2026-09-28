import asyncio,os,sys
from playwright.async_api import async_playwright
MODE=sys.argv[1]
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path='/opt/pw-browsers/chromium-1194/chrome-linux/chrome')
        pg=await b.new_page(viewport={'width':1080,'height':1920})
        await pg.goto('file://'+os.path.join(os.path.dirname(os.path.abspath(__file__)),'reel.html')); await pg.evaluate('document.fonts.ready'); await pg.wait_for_timeout(400)
        if MODE=='stills':
            os.makedirs('reel_stills',exist_ok=True)
            for t in [2.9,7.5,11.9,17.0,20.5]:
                await pg.evaluate(f'render({t})'); await pg.screenshot(path=f'reel_stills/t{t}.png')
        else:
            os.makedirs('reel_frames',exist_ok=True); fps=24; n=int(21*fps)
            for i in range(n):
                await pg.evaluate(f'render({i/fps})'); await pg.screenshot(path=f'reel_frames/f{i:04d}.jpg',type='jpeg',quality=90)
        await b.close()
asyncio.run(main())
