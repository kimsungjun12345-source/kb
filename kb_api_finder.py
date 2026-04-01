"""
KB라이프 실제 API 호출 분석기
F12 개발자 도구 방식으로 실제 보험료 계산 API를 찾아내는 스크래퍼
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from datetime import datetime
import re

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api_finder.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KBAPIFinder:
    """KB라이프 API 탐지 및 분석"""

    def __init__(self):
        self.found_apis = []
        self.interaction_apis = []
        self.product_urls = [
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5",  # 암보험
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5",  # 건강보험
        ]

    async def setup_browser(self) -> tuple[Browser, BrowserContext]:
        """브라우저 설정 및 네트워크 모니터링"""
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=False,  # 브라우저 창 표시로 실제 동작 확인
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security'
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )

        return browser, context

    async def monitor_network_requests(self, page: Page):
        """네트워크 요청 모니터링"""

        async def handle_request(request):
            url = request.url
            method = request.method

            # 관심 있는 API 패턴들
            api_patterns = [
                'premium', 'price', 'calc', 'quote', 'estimate',
                'insurance', 'product', 'detail', 'info',
                '보험', '계산', '견적', '상품'
            ]

            if any(pattern in url.lower() for pattern in api_patterns):
                api_info = {
                    'timestamp': datetime.now().isoformat(),
                    'method': method,
                    'url': url,
                    'headers': dict(request.headers),
                    'post_data': request.post_data if request.post_data else None,
                    'resource_type': request.resource_type
                }

                self.found_apis.append(api_info)
                logger.info(f"🔍 관심 API 발견: {method} {url}")

        async def handle_response(response):
            if response.url in [api['url'] for api in self.found_apis]:
                try:
                    if 'json' in response.headers.get('content-type', ''):
                        body = await response.json()
                        logger.info(f"📋 API 응답 데이터: {json.dumps(body, ensure_ascii=False, indent=2)[:500]}...")
                except:
                    pass

        page.on('request', handle_request)
        page.on('response', handle_response)

    async def find_interactive_elements(self, page: Page) -> List[Dict]:
        """페이지에서 상호작용 가능한 요소들 찾기"""

        logger.info("🔍 상호작용 요소 탐지 중...")

        # 다양한 선택자로 요소 찾기
        selectors_to_check = [
            # 버튼들
            'button:has-text("견적")', 'button:has-text("계산")', 'button:has-text("조회")',
            'button:has-text("가입")', 'button:has-text("상담")', 'button:has-text("문의")',

            # 입력 필드들
            'input[placeholder*="나이"]', 'input[placeholder*="연령"]',
            'input[type="number"]', 'input[name*="age"]',

            # 선택 박스들
            'select[name*="age"]', 'select[name*="gender"]',

            # 링크들
            'a:has-text("견적")', 'a:has-text("계산")', 'a:has-text("상담신청")',

            # 일반적인 패턴들
            '[class*="calc"]', '[class*="quote"]', '[class*="premium"]',
            '[id*="calc"]', '[id*="quote"]', '[id*="premium"]'
        ]

        found_elements = []

        for selector in selectors_to_check:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        text = await element.inner_text()
                        html = await element.inner_html()

                        element_info = {
                            'selector': selector,
                            'text': text.strip()[:100],
                            'html': html[:200],
                            'tag': await element.evaluate('el => el.tagName'),
                            'attributes': await element.evaluate('''el => {
                                const attrs = {};
                                for (let attr of el.attributes) {
                                    attrs[attr.name] = attr.value;
                                }
                                return attrs;
                            }''')
                        }
                        found_elements.append(element_info)
                        logger.info(f"✅ 요소 발견: {element_info['tag']} - {text.strip()[:50]}")
                    except:
                        continue
            except:
                continue

        return found_elements

    async def try_interactions(self, page: Page, elements: List[Dict]):
        """찾은 요소들과 상호작용 시도"""

        logger.info("🤖 상호작용 시도 시작...")

        for element_info in elements[:5]:  # 처음 5개 요소만 시도
            try:
                selector = element_info['selector']
                text = element_info['text']

                logger.info(f"👆 클릭 시도: {text}")

                # API 호출 전 현재 상태 저장
                before_count = len(self.found_apis)

                # 클릭 시도
                await page.click(selector)
                await page.wait_for_timeout(3000)  # 3초 대기

                # 새로운 API 호출이 있었는지 확인
                after_count = len(self.found_apis)
                if after_count > before_count:
                    logger.info(f"🎯 클릭으로 새로운 API 발견! ({after_count - before_count}개)")

                    # 새로 발견된 API들 기록
                    new_apis = self.found_apis[before_count:]
                    for api in new_apis:
                        self.interaction_apis.append({
                            'trigger_element': element_info,
                            'api_call': api
                        })

                # 모달이나 새로운 폼이 나타났는지 확인
                await self.check_for_new_forms(page)

            except Exception as e:
                logger.debug(f"클릭 실패: {e}")
                continue

    async def check_for_new_forms(self, page: Page):
        """새로 나타난 폼이나 모달 확인"""

        form_selectors = [
            'form', '.modal', '.popup', '.layer',
            '[class*="modal"]', '[class*="popup"]', '[class*="layer"]'
        ]

        for selector in form_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    # 폼 내부의 입력 필드들 확인
                    inputs = await element.query_selector_all('input, select, button')
                    if inputs:
                        logger.info(f"📝 새로운 폼 발견: {len(inputs)}개 입력 요소")

                        # 나이 관련 필드가 있는지 확인
                        for input_elem in inputs:
                            try:
                                placeholder = await input_elem.get_attribute('placeholder')
                                name = await input_elem.get_attribute('name')
                                if placeholder and ('나이' in placeholder or 'age' in placeholder.lower()):
                                    logger.info(f"🎯 나이 입력 필드 발견! placeholder: {placeholder}")
                                if name and ('age' in name.lower() or '나이' in name):
                                    logger.info(f"🎯 나이 입력 필드 발견! name: {name}")
                            except:
                                continue
            except:
                continue

    async def analyze_product_page(self, url: str):
        """단일 상품 페이지 분석"""

        logger.info(f"📄 페이지 분석 시작: {url}")

        browser, context = await self.setup_browser()
        page = await context.new_page()

        try:
            # 네트워크 모니터링 시작
            await self.monitor_network_requests(page)

            # 페이지 방문
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)

            # 상호작용 요소 찾기
            elements = await self.find_interactive_elements(page)

            if elements:
                logger.info(f"📋 총 {len(elements)}개 상호작용 요소 발견")

                # 요소들과 상호작용 시도
                await self.try_interactions(page, elements)

                # 추가 탐색 - 페이지 스크롤하면서 더 많은 요소 로드
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(3000)

                # 다시 요소 찾기
                more_elements = await self.find_interactive_elements(page)
                if len(more_elements) > len(elements):
                    logger.info(f"🔍 스크롤 후 추가 요소 발견: {len(more_elements) - len(elements)}개")
                    await self.try_interactions(page, more_elements[len(elements):])

            else:
                logger.warning("❌ 상호작용 요소를 찾을 수 없습니다.")

        except Exception as e:
            logger.error(f"페이지 분석 중 오류: {e}")
        finally:
            await context.close()
            await browser.close()

    async def save_results(self):
        """분석 결과 저장"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        results = {
            'timestamp': timestamp,
            'total_apis_found': len(self.found_apis),
            'interaction_triggered_apis': len(self.interaction_apis),
            'found_apis': self.found_apis,
            'interaction_apis': self.interaction_apis
        }

        filename = f'kb_api_analysis_{timestamp}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"📊 분석 결과 저장: {filename}")

        # 요약 출력
        print(f"\n{'='*50}")
        print(f"KB라이프 API 분석 결과")
        print(f"{'='*50}")
        print(f"📊 총 발견 API: {len(self.found_apis)}개")
        print(f"🤖 상호작용으로 발견: {len(self.interaction_apis)}개")

        if self.found_apis:
            print(f"\n🔍 발견된 주요 API:")
            for i, api in enumerate(self.found_apis[:5], 1):
                print(f"{i}. {api['method']} {api['url']}")

        if self.interaction_apis:
            print(f"\n🎯 상호작용으로 발견된 API:")
            for i, interaction in enumerate(self.interaction_apis[:3], 1):
                trigger = interaction['trigger_element']['text'][:30]
                api_url = interaction['api_call']['url']
                print(f"{i}. '{trigger}' 클릭 → {api_url}")

    async def run_full_analysis(self):
        """전체 분석 실행"""

        logger.info("🚀 KB라이프 API 분석 시작")

        for url in self.product_urls:
            await self.analyze_product_page(url)
            await asyncio.sleep(5)  # 페이지 간 대기

        await self.save_results()

async def main():
    """메인 실행 함수"""

    print("KB라이프 실제 API 탐지기를 시작합니다...")
    print("브라우저 창이 열리며 자동으로 페이지를 분석합니다.")

    finder = KBAPIFinder()
    await finder.run_full_analysis()

    print("\n분석 완료! 결과 파일을 확인해주세요.")

if __name__ == "__main__":
    asyncio.run(main())