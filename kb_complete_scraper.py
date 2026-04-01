import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBCompleteScraper:
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
                "--window-size=1920,1080"
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
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            window.chrome = {
                runtime: {},
            };

            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });

            Object.defineProperty(navigator, 'languages', {
                get: () => ['ko-KR', 'ko', 'en-US', 'en'],
            });
        """)

        return browser, context

    def generate_birthdate(self, age):
        """나이를 기준으로 생년월일 생성 (YYYYMMDD 형식)"""
        current_year = datetime.now().year
        birth_year = current_year - age
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return f"{birth_year}{month:02d}{day:02d}"

    async def wait_random(self, min_seconds=2, max_seconds=5):
        """랜덤 대기"""
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def slow_type(self, page, selector, text):
        """천천히 타이핑하기"""
        await page.focus(selector)
        await page.fill(selector, "")
        for char in text:
            await page.type(selector, char)
            await asyncio.sleep(random.uniform(0.05, 0.15))

    async def human_like_click(self, page, selector):
        """사람처럼 클릭하기"""
        element = await page.wait_for_selector(selector, timeout=10000)
        box = await element.bounding_box()
        if box:
            x = box["x"] + random.uniform(box["width"] * 0.3, box["width"] * 0.7)
            y = box["y"] + random.uniform(box["height"] * 0.3, box["height"] * 0.7)

            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
            await page.mouse.click(x, y)

    async def scrape_single_case(self, age, gender):
        """단일 케이스 데이터 수집"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info(f"데이터 수집 시작: {age}세 {gender}")

                # 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle", timeout=60000)
                await self.wait_random(3, 5)

                # 생년월일 입력
                birthdate = self.generate_birthdate(age)
                logger.info(f"생년월일 입력: {birthdate}")

                birthday_input = await page.wait_for_selector("#birthday", timeout=10000)
                await page.focus("#birthday")
                await page.fill("#birthday", "")
                await self.slow_type(page, "#birthday", birthdate)

                await self.wait_random(1, 2)

                # 성별 선택
                gender_value = "M" if gender == "남성" else "F"
                gender_selector = f"input[name='genderCode'][value='{gender_value}']"

                try:
                    await page.check(gender_selector)
                    logger.info(f"성별 선택 완료: {gender}")
                except:
                    # 라디오 버튼을 직접 클릭
                    gender_radios = await page.query_selector_all("input[name='genderCode']")
                    if len(gender_radios) >= 2:
                        if gender == "남성":
                            await gender_radios[0].click()
                        else:
                            await gender_radios[1].click()
                        logger.info(f"성별 선택 완료 (직접 클릭): {gender}")

                await self.wait_random(2, 3)

                # 설계견적하기 버튼 클릭
                calculate_buttons = [
                    "button:has-text('설계견적하기')",
                    "button:has-text('견적')",
                    "button:has-text('계산')",
                    "[onclick*='설계']",
                    "[onclick*='견적']"
                ]

                clicked = False
                for btn_selector in calculate_buttons:
                    try:
                        await page.wait_for_selector(btn_selector, timeout=5000)
                        await self.human_like_click(page, btn_selector)
                        logger.info(f"버튼 클릭 성공: {btn_selector}")
                        clicked = True
                        break
                    except:
                        continue

                if not clicked:
                    # 모든 버튼 중에서 설계견적 관련 찾기
                    buttons = await page.query_selector_all("button")
                    for button in buttons:
                        try:
                            button_text = await button.text_content()
                            if button_text and ("설계" in button_text or "견적" in button_text):
                                await button.click()
                                logger.info(f"설계견적 버튼 클릭: {button_text}")
                                clicked = True
                                break
                        except:
                            continue

                if not clicked:
                    logger.error("설계견적하기 버튼을 찾을 수 없습니다")
                    return None

                # 페이지 로딩 대기
                await self.wait_random(5, 8)

                # 새 페이지나 팝업 처리
                pages = context.pages
                target_page = page

                if len(pages) > 1:
                    # 새 페이지가 열렸다면 해당 페이지로 전환
                    target_page = pages[-1]
                    logger.info("새 페이지로 전환")

                # 팝업 체크
                try:
                    popup_selectors = [".popup", ".modal", "[id*='popup']", "[class*='popup']"]
                    for selector in popup_selectors:
                        popup = await target_page.query_selector(selector)
                        if popup:
                            is_visible = await popup.is_visible()
                            if is_visible:
                                logger.info("팝업 발견, 닫기 시도")
                                close_selectors = ["[class*='close']", "button:has-text('닫기')", "button:has-text('확인')"]
                                for close_selector in close_selectors:
                                    try:
                                        await target_page.click(close_selector, timeout=2000)
                                        await self.wait_random(1, 2)
                                        break
                                    except:
                                        continue
                except:
                    pass

                # 결과 페이지에서 데이터 수집
                result_data = await self.collect_insurance_data(target_page, age, gender, birthdate)

                # 스크린샷 저장 (디버깅용)
                await target_page.screenshot(path=f"kb_result_{age}_{gender}.png")

                return result_data

            except Exception as e:
                logger.error(f"스크래핑 중 오류: {age}세 {gender} - {str(e)}")
                return None
            finally:
                await browser.close()

    async def collect_insurance_data(self, page, age, gender, birthdate):
        """보험 데이터 수집"""
        try:
            result_data = {
                "age": age,
                "gender": gender,
                "birthdate": birthdate,
                "plans": [],
                "special_clauses": [],
                "scraped_at": datetime.now().isoformat(),
                "page_url": page.url
            }

            logger.info("보험 데이터 수집 시작")

            # 페이지 내용 확인
            page_content = await page.content()
            with open(f"kb_result_page_{age}_{gender}.html", "w", encoding="utf-8") as f:
                f.write(page_content)

            # 플랜 데이터 수집
            await self.collect_plan_data(page, result_data)

            # 특약 데이터 수집
            await self.collect_special_clause_data(page, result_data)

            logger.info(f"데이터 수집 완료: {age}세 {gender} - 플랜 {len(result_data['plans'])}개, 특약 {len(result_data['special_clauses'])}개")

            return result_data

        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {str(e)}")
            return None

    async def collect_plan_data(self, page, result_data):
        """플랜 데이터 수집"""
        try:
            # 플랜 관련 요소 찾기
            plan_selectors = [
                "[class*='plan']",
                "[class*='product']",
                "[id*='plan']",
                ".tab-content",
                "[class*='premium']"
            ]

            plans_found = []
            for selector in plan_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        logger.info(f"플랜 관련 요소 발견: {selector} ({len(elements)}개)")
                        for i, element in enumerate(elements[:4]):  # 최대 4개
                            try:
                                text_content = await element.text_content()
                                if text_content and len(text_content.strip()) > 10:
                                    plan_info = {
                                        "plan_number": i + 1,
                                        "selector": selector,
                                        "content": text_content.strip()[:200],  # 처음 200자만
                                        "premium": await self.extract_premium_from_element(element),
                                        "coverage": await self.extract_coverage_from_element(element)
                                    }
                                    plans_found.append(plan_info)
                            except:
                                continue
                except:
                    continue

            result_data["plans"] = plans_found[:4]  # 최대 4개 플랜만

        except Exception as e:
            logger.error(f"플랜 데이터 수집 중 오류: {str(e)}")

    async def extract_premium_from_element(self, element):
        """요소에서 보험료 추출"""
        try:
            text = await element.text_content()
            # 보험료 패턴 찾기 (원, 만원, 천원 등)
            import re
            premium_patterns = [
                r'(\d{1,3}(?:,\d{3})*)\s*원',
                r'(\d{1,3}(?:,\d{3})*)\s*만원',
                r'월\s*(\d{1,3}(?:,\d{3})*)',
                r'보험료.*?(\d{1,3}(?:,\d{3})*)'
            ]

            for pattern in premium_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    return matches[0]

            return None
        except:
            return None

    async def extract_coverage_from_element(self, element):
        """요소에서 보장내용 추출"""
        try:
            # 보장 관련 키워드가 포함된 텍스트 찾기
            text = await element.text_content()
            coverage_keywords = ["보장", "급여", "지급", "혜택", "담보"]

            for keyword in coverage_keywords:
                if keyword in text:
                    # 키워드 주변 텍스트 추출
                    lines = text.split('\n')
                    for line in lines:
                        if keyword in line:
                            return line.strip()[:100]  # 처음 100자만

            return None
        except:
            return None

    async def collect_special_clause_data(self, page, result_data):
        """특약 데이터 수집"""
        try:
            # 특약 관련 체크박스 찾기
            checkboxes = await page.query_selector_all("input[type='checkbox']")
            logger.info(f"체크박스 발견: {len(checkboxes)}개")

            for i, checkbox in enumerate(checkboxes):
                try:
                    # 체크박스와 연관된 레이블이나 텍스트 찾기
                    parent = await checkbox.evaluate("el => el.closest('tr, div, li, .clause-item, [class*=\"clause\"], [class*=\"special\"]')")

                    if parent:
                        text_content = await parent.text_content()
                        if text_content and len(text_content.strip()) > 5:
                            # 특약명 추출 (간단한 방법)
                            clause_name = text_content.strip().split('\n')[0][:50]

                            # 체크박스 상태 확인
                            is_checked = await checkbox.is_checked()

                            # 물음표나 도움말 아이콘 찾기
                            tooltip_info = await self.find_tooltip_info(parent)

                            clause_data = {
                                "index": i,
                                "name": clause_name,
                                "is_active": is_checked,
                                "tooltip": tooltip_info,
                                "full_text": text_content.strip()[:200]  # 처음 200자만
                            }

                            result_data["special_clauses"].append(clause_data)

                except Exception as e:
                    logger.debug(f"체크박스 {i} 처리 중 오류: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"특약 데이터 수집 중 오류: {str(e)}")

    async def find_tooltip_info(self, parent_element):
        """물음표 툴팁 정보 찾기"""
        try:
            # 물음표, 도움말 아이콘 등을 찾기
            tooltip_selectors = [
                "[class*='tooltip']",
                "[class*='help']",
                "[class*='question']",
                "[title]",
                "img[src*='help']",
                "img[src*='question']",
                ".ico-help",
                ".ico-question"
            ]

            for selector in tooltip_selectors:
                tooltip_element = await parent_element.query_selector(selector)
                if tooltip_element:
                    # 툴팁 텍스트 추출 시도
                    title_attr = await tooltip_element.get_attribute("title")
                    if title_attr:
                        return title_attr

                    # 호버해서 툴팁 내용 확인 시도
                    try:
                        await tooltip_element.hover()
                        await asyncio.sleep(0.5)

                        # 툴팁 내용 찾기
                        tooltip_content_selectors = [
                            "[role='tooltip']",
                            "[class*='tooltip-content']",
                            "[class*='tooltip-text']",
                            ".tooltip"
                        ]

                        for content_selector in tooltip_content_selectors:
                            content_element = await parent_element.page.query_selector(content_selector)
                            if content_element:
                                is_visible = await content_element.is_visible()
                                if is_visible:
                                    content_text = await content_element.text_content()
                                    if content_text:
                                        return content_text.strip()
                    except:
                        pass

            return None

        except:
            return None

    async def test_single_scrape(self, age=30, gender="남성"):
        """단일 스크래핑 테스트"""
        logger.info(f"단일 스크래핑 테스트 시작: {age}세 {gender}")

        result = await self.scrape_single_case(age, gender)

        if result:
            # 결과를 JSON 파일로 저장
            filename = f"kb_test_result_{age}_{gender}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logger.info(f"테스트 결과 저장: {filename}")
            logger.info(f"수집된 데이터: 플랜 {len(result['plans'])}개, 특약 {len(result['special_clauses'])}개")

            # 간단한 결과 출력
            print("\n=== 수집된 데이터 요약 ===")
            print(f"나이: {result['age']}세")
            print(f"성별: {result['gender']}")
            print(f"생년월일: {result['birthdate']}")
            print(f"플랜 수: {len(result['plans'])}")
            print(f"특약 수: {len(result['special_clauses'])}")

            if result['plans']:
                print("\n=== 플랜 정보 ===")
                for i, plan in enumerate(result['plans'][:3]):  # 처음 3개만 출력
                    print(f"플랜 {i+1}: {plan.get('content', 'N/A')[:100]}...")

            if result['special_clauses']:
                print("\n=== 특약 정보 ===")
                for i, clause in enumerate(result['special_clauses'][:5]):  # 처음 5개만 출력
                    print(f"특약 {i+1}: {clause.get('name', 'N/A')}")

        else:
            logger.error("스크래핑 실패")

        return result

async def main():
    scraper = KBCompleteScraper()

    # 단일 테스트 실행
    await scraper.test_single_scrape(30, "남성")

if __name__ == "__main__":
    asyncio.run(main())