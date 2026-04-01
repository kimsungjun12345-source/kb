import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def analyze_page():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        page = await context.new_page()

        try:
            url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
            logger.info(f"페이지 로딩: {url}")

            await page.goto(url)
            await page.wait_for_load_state("networkidle", timeout=30000)

            # 페이지 타이틀 확인
            title = await page.title()
            logger.info(f"페이지 타이틀: {title}")

            # 페이지 URL 확인 (리다이렉트되었는지)
            current_url = page.url
            logger.info(f"현재 URL: {current_url}")

            # 페이지 스크린샷
            await page.screenshot(path="kb_page_full.png", full_page=True)
            logger.info("전체 페이지 스크린샷 저장됨")

            # HTML 일부 저장
            html_content = await page.content()
            with open("kb_page.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info("페이지 HTML 저장됨")

            # 특정 키워드 검색
            keywords = ["생년월일", "성별", "보험료", "계산", "남성", "여성", "input", "button"]
            for keyword in keywords:
                try:
                    elements = await page.query_selector_all(f"text={keyword}")
                    logger.info(f"키워드 '{keyword}' 발견: {len(elements)}개")

                    # 텍스트 포함 요소도 검색
                    text_elements = await page.query_selector_all(f":text('{keyword}')")
                    logger.info(f"텍스트 포함 '{keyword}' 발견: {len(text_elements)}개")
                except:
                    pass

            # iframe 확인
            frames = page.frames
            logger.info(f"페이지의 프레임 수: {len(frames)}")
            for i, frame in enumerate(frames):
                frame_name = frame.name
                frame_url = frame.url
                logger.info(f"프레임 {i}: name={frame_name}, url={frame_url}")

            # 모든 form 요소 확인
            forms = await page.query_selector_all("form")
            logger.info(f"페이지의 form 요소: {len(forms)}개")

            # 대기 시간을 두고 다시 확인 (동적 로딩 가능성)
            await asyncio.sleep(5)

            # 다시 input/button 검색
            inputs = await page.query_selector_all("input")
            buttons = await page.query_selector_all("button, input[type='button'], input[type='submit']")
            logger.info(f"5초 후 - Input: {len(inputs)}개, Button: {len(buttons)}개")

        except Exception as e:
            logger.error(f"분석 중 오류: {str(e)}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_page())