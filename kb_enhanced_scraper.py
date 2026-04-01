import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime

try:
    from playwright_stealth import stealth_async
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBInsuranceEnhancedScraper:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.data = []

    async def create_stealth_browser(self, playwright):
        """스텔스 모드로 브라우저 생성"""
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--disable-logging",
                "--disable-login-animations",
                "--disable-notifications",
                "--disable-gpu",
                "--disable-translations",
                "--disable-features=TranslateUI",
                "--disable-ipc-flooding-protection",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
                "--disable-client-side-phishing-detection",
                "--disable-sync",
                "--no-default-browser-check",
                "--no-first-run",
                "--window-size=1920,1080",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )

        # JavaScript로 추가 스텔스 설정
        await context.add_init_script("""
            // Webdriver 속성 제거
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Chrome 객체 추가
            window.chrome = {
                runtime: {},
            };

            // Permissions API 처리
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Plugin 정보 추가
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            // Language 설정
            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en'],
            });
        """)

        return browser, context

    async def wait_random(self, min_seconds=2, max_seconds=5):
        """랜덤 대기"""
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def slow_type(self, page, selector, text):
        """천천히 타이핑하기"""
        await page.focus(selector)
        await page.fill(selector, "")  # 먼저 비우기
        for char in text:
            await page.type(selector, char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

    async def human_like_click(self, page, selector):
        """사람처럼 클릭하기"""
        element = await page.wait_for_selector(selector, timeout=10000)
        box = await element.bounding_box()
        if box:
            # 요소 중앙이 아닌 랜덤한 위치 클릭
            x = box["x"] + random.uniform(box["width"] * 0.3, box["width"] * 0.7)
            y = box["y"] + random.uniform(box["height"] * 0.3, box["height"] * 0.7)

            # 마우스 이동 후 클릭
            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.click(x, y)

    async def try_different_approaches(self, page):
        """다양한 접근 방법으로 페이지 접근"""

        # 방법 1: 직접 접근
        logger.info("방법 1: 직접 URL 접근 시도")
        try:
            response = await page.goto(self.base_url,
                                     wait_until="networkidle",
                                     timeout=30000)
            logger.info(f"응답 상태: {response.status}")
            await self.wait_random(3, 5)

            # 방화벽 체크
            content = await page.content()
            if "firewall" in content.lower() or "blocked" in content.lower():
                logger.warning("방화벽에 차단됨, 다른 방법 시도")
                return False
            else:
                logger.info("직접 접근 성공")
                return True

        except Exception as e:
            logger.error(f"직접 접근 실패: {e}")

        # 방법 2: 메인 페이지를 거쳐서 접근
        logger.info("방법 2: 메인 페이지 경유 접근")
        try:
            await page.goto("https://www.kblife.co.kr", wait_until="networkidle")
            await self.wait_random(2, 4)

            # 보험상품 메뉴 클릭 시도
            insurance_links = [
                "a:has-text('보험상품')",
                "a:has-text('상품안내')",
                "[href*='product']",
                ".menu:has-text('보험')"
            ]

            for link_selector in insurance_links:
                try:
                    await page.wait_for_selector(link_selector, timeout=3000)
                    await self.human_like_click(page, link_selector)
                    await self.wait_random(2, 3)
                    break
                except:
                    continue

            # 타겟 상품 페이지로 이동
            await page.goto(self.base_url, wait_until="networkidle", timeout=30000)
            await self.wait_random(3, 5)

            content = await page.content()
            if "firewall" not in content.lower() and "blocked" not in content.lower():
                logger.info("메인 페이지 경유 접근 성공")
                return True

        except Exception as e:
            logger.error(f"메인 페이지 경유 접근 실패: {e}")

        # 방법 3: 리퍼러 설정
        logger.info("방법 3: 리퍼러 설정 접근")
        try:
            await page.set_extra_http_headers({
                "Referer": "https://www.kblife.co.kr/"
            })

            response = await page.goto(self.base_url,
                                     wait_until="networkidle",
                                     timeout=30000)
            await self.wait_random(3, 5)

            content = await page.content()
            if "firewall" not in content.lower() and "blocked" not in content.lower():
                logger.info("리퍼러 설정 접근 성공")
                return True

        except Exception as e:
            logger.error(f"리퍼러 설정 접근 실패: {e}")

        return False

    async def test_advanced_access(self):
        """고급 접근 방법 테스트"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()

                # 스텔스 모드 적용
                if STEALTH_AVAILABLE:
                    try:
                        await stealth_async(page)
                        logger.info("스텔스 모드 적용됨")
                    except:
                        logger.warning("스텔스 모드 적용 실패, 기본 모드 사용")
                else:
                    logger.warning("playwright-stealth를 사용할 수 없음. 기본 스텔스 설정만 사용")

                success = await self.try_different_approaches(page)

                if success:
                    # 페이지 스크린샷
                    await page.screenshot(path="kb_success_access.png", full_page=True)

                    # HTML 저장
                    html_content = await page.content()
                    with open("kb_success.html", "w", encoding="utf-8") as f:
                        f.write(html_content)

                    logger.info("성공적으로 페이지에 접근했습니다!")

                    # 페이지 내용 분석
                    await self.analyze_page_content(page)
                    return True
                else:
                    logger.error("모든 접근 방법이 실패했습니다.")
                    return False

            except Exception as e:
                logger.error(f"테스트 중 오류: {e}")
                return False
            finally:
                await browser.close()

    async def analyze_page_content(self, page):
        """페이지 내용 분석"""
        logger.info("페이지 내용 분석 중...")

        # 모든 입력 필드 찾기
        inputs = await page.query_selector_all("input")
        logger.info(f"입력 필드 발견: {len(inputs)}개")

        for i, inp in enumerate(inputs):
            try:
                inp_type = await inp.get_attribute("type")
                inp_name = await inp.get_attribute("name")
                inp_id = await inp.get_attribute("id")
                inp_placeholder = await inp.get_attribute("placeholder")
                inp_class = await inp.get_attribute("class")

                logger.info(f"Input {i+1}: type={inp_type}, name={inp_name}, id={inp_id}, placeholder={inp_placeholder}, class={inp_class}")
            except:
                pass

        # 모든 버튼 찾기
        buttons = await page.query_selector_all("button, input[type='button'], input[type='submit']")
        logger.info(f"버튼 발견: {len(buttons)}개")

        for i, btn in enumerate(buttons):
            try:
                btn_text = await btn.text_content()
                btn_value = await btn.get_attribute("value")
                btn_onclick = await btn.get_attribute("onclick")

                logger.info(f"Button {i+1}: text='{btn_text}', value='{btn_value}', onclick='{btn_onclick}'")
            except:
                pass

        # 특정 텍스트 검색
        keywords = ["생년월일", "성별", "보험료", "계산", "남자", "여자", "남성", "여성"]
        for keyword in keywords:
            try:
                elements = await page.query_selector_all(f"text={keyword}")
                if elements:
                    logger.info(f"키워드 '{keyword}' 발견: {len(elements)}개")
            except:
                pass

async def main():
    scraper = KBInsuranceEnhancedScraper()
    success = await scraper.test_advanced_access()

    if success:
        logger.info("고급 스크래핑 준비 완료!")
    else:
        logger.error("페이지 접근에 실패했습니다.")

if __name__ == "__main__":
    asyncio.run(main())