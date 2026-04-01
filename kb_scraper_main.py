import asyncio
import json
from playwright.async_api import async_playwright
from datetime import datetime
import random
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBInsuranceScraper:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.data = []

    async def create_browser_context(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        return browser, context

    def generate_birthdate(self, age):
        current_year = datetime.now().year
        birth_year = current_year - age
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return f"{birth_year}{month:02d}{day:02d}"

    async def wait_random(self, min_seconds=1, max_seconds=3):
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def test_single_case(self, age=30, gender="남성"):
        """단일 테스트 케이스"""
        async with async_playwright() as playwright:
            browser, context = await self.create_browser_context(playwright)

            try:
                page = await context.new_page()
                logger.info(f"테스트 시작: {age}세 {gender}")

                # 페이지 로드
                await page.goto(self.base_url)
                await page.wait_for_load_state("networkidle")
                await self.wait_random(2, 3)

                # 페이지 스크린샷 (디버깅용)
                await page.screenshot(path="kb_page_1.png")
                logger.info("초기 페이지 스크린샷 저장됨")

                # 모든 input 요소 찾기
                inputs = await page.query_selector_all("input")
                logger.info(f"페이지에서 발견된 input 요소: {len(inputs)}개")

                for i, inp in enumerate(inputs):
                    inp_type = await inp.get_attribute("type")
                    inp_name = await inp.get_attribute("name")
                    inp_id = await inp.get_attribute("id")
                    inp_placeholder = await inp.get_attribute("placeholder")
                    logger.info(f"Input {i}: type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}")

                # 모든 버튼 찾기
                buttons = await page.query_selector_all("button, input[type='button'], input[type='submit']")
                logger.info(f"페이지에서 발견된 버튼: {len(buttons)}개")

                for i, btn in enumerate(buttons):
                    btn_text = await btn.text_content()
                    btn_value = await btn.get_attribute("value")
                    logger.info(f"Button {i}: text='{btn_text}', value='{btn_value}'")

                # 페이지 전체 텍스트 일부 확인
                page_text = await page.text_content("body")
                if "생년월일" in page_text:
                    logger.info("생년월일 텍스트 발견됨")
                if "성별" in page_text:
                    logger.info("성별 텍스트 발견됨")
                if "보험료" in page_text:
                    logger.info("보험료 텍스트 발견됨")

                return True

            except Exception as e:
                logger.error(f"테스트 중 오류: {str(e)}")
                return False
            finally:
                await browser.close()

    async def run_test(self):
        logger.info("KB 보험 스크래핑 테스트 시작")
        result = await self.test_single_case()
        if result:
            logger.info("테스트 성공!")
        else:
            logger.error("테스트 실패!")

async def main():
    scraper = KBInsuranceScraper()
    await scraper.run_test()

if __name__ == "__main__":
    asyncio.run(main())