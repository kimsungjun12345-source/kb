"""
KB 라이프 인터랙티브 데이터 수집기
사용자가 웹사이트에서 클릭/선택할 때마다 달라지는 동적 정보들을 자동으로 수집
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import random

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('interactive_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KBInteractiveScraper:
    """KB라이프 인터랙티브 데이터 수집기"""

    def __init__(self):
        self.captured_data = []
        self.interaction_results = {}

        # 테스트할 상호작용 시나리오들
        self.interaction_scenarios = {
            "age_gender_combinations": [
                {"age": 25, "gender": "남성"}, {"age": 35, "gender": "여성"},
                {"age": 45, "gender": "남성"}, {"age": 55, "gender": "여성"}
            ],
            "coverage_options": [
                "기본형", "고급형", "최고급형"
            ],
            "payment_methods": [
                "월납", "연납", "일시납"
            ],
            "coverage_periods": [
                "10년", "20년", "30년", "종신"
            ]
        }

        # 상품 정보
        self.product_info = {
            "KB 착한암보험": {
                "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5",
                "product_code": "316100104"
            }
        }

    async def setup_browser(self) -> tuple[Browser, BrowserContext]:
        """브라우저 설정"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=False)

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        return browser, context

    async def capture_network_responses(self, page: Page):
        """네트워크 응답 캡처"""
        async def handle_response(response):
            url = response.url
            if any(keyword in url.lower() for keyword in ['api', 'calc', 'premium', 'quote']):
                try:
                    if 'json' in response.headers.get('content-type', ''):
                        data = await response.json()
                        self.captured_data.append({
                            'url': url,
                            'method': response.request.method,
                            'status': response.status,
                            'data': data,
                            'timestamp': datetime.now().isoformat()
                        })
                        logger.info(f"📊 데이터 캡처: {url}")
                except:
                    pass

        page.on('response', handle_response)

    async def wait_and_check_changes(self, page: Page, action_description: str) -> Dict:
        """액션 후 변화 확인"""
        logger.info(f"⏳ {action_description} 후 변화 확인 중...")

        await page.wait_for_timeout(3000)  # 3초 대기

        # 보험료 관련 요소들 확인
        premium_selectors = [
            '[class*="premium"]', '[class*="price"]', '[class*="amount"]',
            '[id*="premium"]', '[id*="price"]', '[id*="amount"]',
            'span:has-text("원")', 'div:has-text("원")'
        ]

        changes = {}
        for selector in premium_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for i, element in enumerate(elements):
                    text = await element.inner_text()
                    if '원' in text or ',' in text:
                        changes[f"{selector}_{i}"] = text.strip()
            except:
                continue

        return changes

    async def interact_with_age_gender(self, page: Page, age: int, gender: str) -> Dict:
        """나이/성별 선택 인터랙션"""
        logger.info(f"👤 나이/성별 설정: {age}세 {gender}")

        results = {"age": age, "gender": gender, "changes": []}

        # 나이 입력 시도
        age_selectors = [
            'input[placeholder*="나이"]', 'input[placeholder*="연령"]',
            'input[name*="age"]', 'select[name*="age"]',
            '[data-age]', '#age', '.age-input'
        ]

        for selector in age_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    if await element.get_attribute('type') == 'text' or await element.tag_name() == 'INPUT':
                        await element.fill(str(age))
                        logger.info(f"✅ 나이 입력: {selector}")

                        changes = await self.wait_and_check_changes(page, f"{age}세 나이 입력")
                        results["changes"].append({"action": "age_input", "changes": changes})
                        break
            except Exception as e:
                logger.debug(f"나이 입력 실패 {selector}: {e}")
                continue

        # 성별 선택 시도
        gender_selectors = [
            'input[value*="남성"]', 'input[value*="여성"]',
            'button:has-text("남성")', 'button:has-text("여성")',
            'label:has-text("남성")', 'label:has-text("여성")',
            '[data-gender]'
        ]

        target_gender = "남성" if gender == "남성" else "여성"

        for selector in gender_selectors:
            try:
                if target_gender in selector:
                    element = await page.query_selector(selector)
                    if element:
                        await element.click()
                        logger.info(f"✅ 성별 선택: {selector}")

                        changes = await self.wait_and_check_changes(page, f"{gender} 성별 선택")
                        results["changes"].append({"action": "gender_select", "changes": changes})
                        break
            except Exception as e:
                logger.debug(f"성별 선택 실패 {selector}: {e}")
                continue

        return results

    async def interact_with_options(self, page: Page) -> List[Dict]:
        """다양한 옵션들과 인터랙션"""
        logger.info("⚙️ 옵션 인터랙션 시작")

        results = []

        # 버튼 클릭 시도
        clickable_selectors = [
            'button:has-text("견적")', 'button:has-text("계산")',
            'button:has-text("조회")', 'button:has-text("가입")',
            'a:has-text("견적")', 'a:has-text("계산")',
            '.btn-estimate', '.btn-quote', '.btn-calc'
        ]

        for selector in clickable_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    button_text = await element.inner_text()
                    logger.info(f"🔘 버튼 클릭: {button_text}")

                    await element.click()
                    changes = await self.wait_and_check_changes(page, f"'{button_text}' 버튼 클릭")

                    results.append({
                        "action": "button_click",
                        "button_text": button_text,
                        "selector": selector,
                        "changes": changes
                    })

                    await page.wait_for_timeout(2000)  # 다음 액션 전 대기
            except Exception as e:
                logger.debug(f"버튼 클릭 실패 {selector}: {e}")
                continue

        # 드롭다운/셀렉트 박스 인터랙션
        select_selectors = ['select', '[role="combobox"]', '.select-box']

        for selector in select_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    if await element.tag_name() == 'SELECT':
                        options = await element.query_selector_all('option')
                        for option in options[:3]:  # 처음 3개 옵션만 테스트
                            value = await option.get_attribute('value')
                            if value:
                                await element.select_option(value)
                                option_text = await option.inner_text()

                                changes = await self.wait_and_check_changes(page, f"'{option_text}' 옵션 선택")
                                results.append({
                                    "action": "select_option",
                                    "option_text": option_text,
                                    "value": value,
                                    "changes": changes
                                })

                                await page.wait_for_timeout(1000)
            except Exception as e:
                logger.debug(f"셀렉트 박스 인터랙션 실패: {e}")
                continue

        return results

    async def comprehensive_interaction_test(self, page: Page, url: str):
        """종합적인 인터랙션 테스트"""
        logger.info(f"🚀 종합 인터랙션 테스트 시작: {url}")

        # 페이지 방문
        await page.goto(url, wait_until='networkidle', timeout=60000)
        await page.wait_for_timeout(5000)

        all_results = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "interactions": []
        }

        # 1. 다양한 나이/성별 조합 테스트
        for combo in self.interaction_scenarios["age_gender_combinations"]:
            try:
                result = await self.interact_with_age_gender(page, combo["age"], combo["gender"])
                all_results["interactions"].append(result)
                await page.wait_for_timeout(3000)  # 각 테스트 간 대기
            except Exception as e:
                logger.error(f"나이/성별 인터랙션 실패: {e}")

        # 2. 옵션 인터랙션 테스트
        try:
            option_results = await self.interact_with_options(page)
            all_results["interactions"].extend(option_results)
        except Exception as e:
            logger.error(f"옵션 인터랙션 실패: {e}")

        # 3. 추가 폼 필드 탐색
        try:
            form_results = await self.explore_form_fields(page)
            all_results["interactions"].extend(form_results)
        except Exception as e:
            logger.error(f"폼 필드 탐색 실패: {e}")

        return all_results

    async def explore_form_fields(self, page: Page) -> List[Dict]:
        """폼 필드 탐색 및 인터랙션"""
        logger.info("📝 폼 필드 탐색")

        results = []

        # 다양한 입력 필드들
        input_selectors = [
            'input[type="number"]', 'input[type="text"]', 'input[type="tel"]',
            'textarea', '[contenteditable]'
        ]

        for selector in input_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for i, element in enumerate(elements):
                    placeholder = await element.get_attribute('placeholder')
                    name = await element.get_attribute('name')

                    # 숫자형 필드에 테스트 값 입력
                    if await element.get_attribute('type') == 'number' or 'age' in (name or '').lower():
                        test_value = str(random.randint(20, 60))
                        await element.fill(test_value)

                        changes = await self.wait_and_check_changes(page, f"숫자 입력: {test_value}")
                        results.append({
                            "action": "number_input",
                            "selector": selector,
                            "placeholder": placeholder,
                            "name": name,
                            "value": test_value,
                            "changes": changes
                        })

                        await page.wait_for_timeout(1000)
            except Exception as e:
                logger.debug(f"폼 필드 인터랙션 실패: {e}")

        return results

    async def save_results(self, results: Dict, product_name: str):
        """결과 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'kb_interactive_results_{product_name}_{timestamp}.json'

        # 캡처된 네트워크 데이터도 포함
        final_results = {
            "interaction_results": results,
            "network_captures": self.captured_data,
            "summary": {
                "total_interactions": len(results.get("interactions", [])),
                "network_captures": len(self.captured_data),
                "timestamp": timestamp
            }
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(final_results, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 결과 저장: {filename}")

        # 요약 출력
        print(f"\n{'='*60}")
        print(f"KB 라이프 인터랙티브 데이터 수집 결과")
        print(f"{'='*60}")
        print(f"상품: {product_name}")
        print(f"총 인터랙션: {len(results.get('interactions', []))}개")
        print(f"네트워크 캡처: {len(self.captured_data)}개")

        if results.get("interactions"):
            print(f"\n📊 인터랙션 유형별 요약:")
            action_counts = {}
            for interaction in results["interactions"]:
                action = interaction.get("action", "unknown")
                action_counts[action] = action_counts.get(action, 0) + 1

            for action, count in action_counts.items():
                print(f"- {action}: {count}개")

    async def run_full_test(self):
        """전체 테스트 실행"""
        browser = None
        context = None

        try:
            browser, context = await self.setup_browser()
            page = await context.new_page()

            # 네트워크 모니터링 시작
            await self.capture_network_responses(page)

            # KB 착한암보험 테스트
            product_name = "KB_착한암보험"
            url = self.product_info["KB 착한암보험"]["url"]

            results = await self.comprehensive_interaction_test(page, url)
            await self.save_results(results, product_name)

        except Exception as e:
            logger.error(f"전체 테스트 실행 중 오류: {e}")
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

async def main():
    """메인 함수"""
    print("KB 라이프 인터랙티브 데이터 수집기를 시작합니다...")
    print("사용자 상호작용에 따른 동적 변화를 자동으로 수집합니다.")

    scraper = KBInteractiveScraper()
    await scraper.run_full_test()

    print("\n인터랙티브 데이터 수집 완료!")

if __name__ == "__main__":
    asyncio.run(main())