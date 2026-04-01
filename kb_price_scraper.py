"""
KB생명 보험가격공시실 API 기반 나이별 보험료 스크래퍼
개발자도구 네트워크 분석을 통한 직접 API 호출 방식
"""

import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

import requests
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('price_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class PremiumData:
    """보험료 데이터 구조"""
    product_code: str
    product_name: str
    age: int
    gender: str  # "M" or "F"
    coverage_amount: str
    monthly_premium: str
    annual_premium: str
    payment_period: str
    guarantee_period: str
    scraped_at: str

class KBPriceScraper:
    """KB생명 보험료 스크래퍼"""

    def __init__(self):
        self.base_url = "https://www.kblife.co.kr"
        self.price_office_url = "https://www.kblife.co.kr/customer-common/insurancePricePublicNoticeOffice.do"

        # KB생명 보험 상품 정보
        self.products = {
            "ON_PD_KC_01": {
                "name": "KB 착한암보험 무배당",
                "type": "질병보험"
            },
            "ON_PD_YG_01": {
                "name": "KB 딱좋은 e-건강보험 무배당(갱신형)(일반심사형)",
                "type": "건강보험"
            },
            "ON_PD_YT_01": {
                "name": "KB 딱좋은 e-건강보험 간편형",
                "type": "건강보험"
            },
            "ON_PD_SR_01": {
                "name": "KB 착한정기보험II 무배당",
                "type": "정기보험"
            },
            "ON_PD_NP_01": {
                "name": "KB 하이파이브평생연금보험 무배당",
                "type": "연금보험"
            }
        }

        # 나이 범위 (19~65세)
        self.age_range = list(range(19, 66))

        # 성별
        self.genders = ["M", "F"]  # Male, Female

        # 세션 유지용 requests session
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest'
        })

    async def setup_browser(self) -> tuple[Browser, BrowserContext, Page]:
        """브라우저 설정 및 보험가격공시실 페이지 로딩"""
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=False,  # 디버깅을 위해 브라우저 창 표시
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security'
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = await context.new_page()

        # 네트워크 요청 모니터링 설정
        await self.setup_network_monitoring(page)

        return browser, context, page

    async def setup_network_monitoring(self, page: Page):
        """네트워크 요청 모니터링 설정"""
        self.captured_requests = []

        async def handle_request(request):
            """요청 캡처"""
            if any(keyword in request.url for keyword in ['premium', 'price', 'calc', 'api']):
                self.captured_requests.append({
                    'method': request.method,
                    'url': request.url,
                    'headers': dict(request.headers),
                    'post_data': request.post_data
                })
                logger.info(f"API 요청 캡처: {request.method} {request.url}")

        async def handle_response(response):
            """응답 캡처"""
            if any(keyword in response.url for keyword in ['premium', 'price', 'calc', 'api']):
                try:
                    response_data = await response.text()
                    logger.info(f"API 응답 캡처: {response.url} - {len(response_data)} bytes")

                    # JSON 응답인 경우 파싱 시도
                    if 'application/json' in response.headers.get('content-type', ''):
                        try:
                            json_data = json.loads(response_data)
                            logger.info(f"JSON 응답 내용: {json.dumps(json_data, ensure_ascii=False, indent=2)[:500]}...")
                        except:
                            pass
                except Exception as e:
                    logger.debug(f"응답 처리 중 오류: {e}")

        page.on('request', handle_request)
        page.on('response', handle_response)

    async def navigate_to_price_office(self, page: Page):
        """보험가격공시실 페이지로 이동"""
        logger.info("보험가격공시실 페이지로 이동...")
        await page.goto(self.price_office_url, wait_until='networkidle', timeout=30000)
        await page.wait_for_timeout(3000)

        # 팝업 처리
        await self.handle_popups(page)

    async def handle_popups(self, page: Page):
        """팝업 처리"""
        popup_selectors = [
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '.popup-close', '.modal-close', '#popup_close'
        ]

        for selector in popup_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    await page.wait_for_timeout(1000)
                    logger.info(f"팝업 닫기: {selector}")
                    break
            except:
                continue

    async def find_product_in_price_office(self, page: Page, product_code: str) -> bool:
        """보험가격공시실에서 상품 찾기"""
        product_info = self.products.get(product_code)
        if not product_info:
            logger.error(f"알 수 없는 상품 코드: {product_code}")
            return False

        product_name = product_info["name"]
        logger.info(f"상품 검색: {product_name}")

        try:
            # 상품 검색 (여러 방법 시도)
            search_methods = [
                # 방법 1: 검색창 사용
                self.search_by_input_field,
                # 방법 2: 상품 목록에서 클릭
                self.search_by_product_list,
                # 방법 3: 카테고리별 검색
                self.search_by_category
            ]

            for search_method in search_methods:
                try:
                    result = await search_method(page, product_code, product_name)
                    if result:
                        logger.info(f"상품 찾기 성공: {product_name}")
                        return True
                except Exception as e:
                    logger.debug(f"검색 방법 실패: {e}")
                    continue

            logger.warning(f"상품을 찾을 수 없습니다: {product_name}")
            return False

        except Exception as e:
            logger.error(f"상품 검색 중 오류: {e}")
            return False

    async def search_by_input_field(self, page: Page, product_code: str, product_name: str) -> bool:
        """검색창으로 상품 찾기"""
        search_selectors = [
            'input[name*="search"]',
            'input[placeholder*="검색"]',
            'input[placeholder*="상품"]',
            '#searchInput',
            '.search-input'
        ]

        for selector in search_selectors:
            try:
                search_input = await page.query_selector(selector)
                if search_input:
                    await search_input.fill(product_name)
                    await page.keyboard.press('Enter')
                    await page.wait_for_timeout(3000)

                    # 검색 결과 확인
                    if await self.check_search_results(page, product_code):
                        return True
            except:
                continue
        return False

    async def search_by_product_list(self, page: Page, product_code: str, product_name: str) -> bool:
        """상품 목록에서 클릭하여 찾기"""
        product_selectors = [
            'a[data-product-code="' + product_code + '"]',
            f'a[href*="{product_code}"]',
            '.product-item a',
            '.insurance-list a'
        ]

        for selector in product_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if product_code in text or any(word in text for word in product_name.split()):
                        await element.click()
                        await page.wait_for_timeout(3000)
                        return True
            except:
                continue
        return False

    async def search_by_category(self, page: Page, product_code: str, product_name: str) -> bool:
        """카테고리별로 상품 찾기"""
        product_type = self.products[product_code]["type"]

        # 카테고리 탭 클릭
        category_selectors = [
            f'a[data-category*="{product_type}"]',
            '.category-tab a',
            '.insurance-type a'
        ]

        for selector in category_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if product_type in text:
                        await element.click()
                        await page.wait_for_timeout(3000)

                        # 해당 카테고리에서 상품 찾기
                        if await self.search_by_product_list(page, product_code, product_name):
                            return True
            except:
                continue
        return False

    async def check_search_results(self, page: Page, product_code: str) -> bool:
        """검색 결과 확인"""
        result_selectors = [
            '.search-result a',
            '.product-result a',
            '.insurance-item a'
        ]

        for selector in result_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute('href')
                    text = await element.inner_text()

                    if product_code in (href or '') or product_code in text:
                        await element.click()
                        await page.wait_for_timeout(3000)
                        return True
            except:
                continue
        return False

    async def extract_premium_for_age_gender(self, page: Page, age: int, gender: str) -> Optional[Dict[str, Any]]:
        """특정 나이/성별에 대한 보험료 추출"""
        logger.info(f"보험료 계산: {age}세, {'남성' if gender == 'M' else '여성'}")

        try:
            # 나이 입력
            age_selectors = [
                'input[name*="age"]',
                'input[id*="age"]',
                '#age',
                '.age-input',
                'select[name*="age"]'
            ]

            age_input_success = False
            for selector in age_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        tag_name = await element.evaluate('el => el.tagName')

                        if tag_name.lower() == 'select':
                            # 셀렉트 박스인 경우
                            await element.select_option(str(age))
                        else:
                            # 입력 필드인 경우
                            await element.clear()
                            await element.fill(str(age))

                        age_input_success = True
                        logger.debug(f"나이 입력 성공: {age}")
                        break
                except Exception as e:
                    logger.debug(f"나이 입력 실패 {selector}: {e}")
                    continue

            if not age_input_success:
                logger.warning(f"나이 입력 필드를 찾을 수 없습니다: {age}")
                return None

            # 성별 선택
            gender_selectors = [
                f'input[name*="gender"][value*="{gender}"]',
                f'input[name*="sex"][value*="{gender}"]',
                f'#gender{gender}',
                f'.gender-{gender.lower()}'
            ]

            gender_input_success = False
            for selector in gender_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await element.click()
                        gender_input_success = True
                        logger.debug(f"성별 선택 성공: {gender}")
                        break
                except:
                    continue

            # 성별 선택 실패한 경우 라디오 버튼 시도
            if not gender_input_success:
                try:
                    radio_selectors = [
                        'input[type="radio"][name*="gender"]',
                        'input[type="radio"][name*="sex"]'
                    ]

                    for radio_selector in radio_selectors:
                        radios = await page.query_selector_all(radio_selector)
                        for radio in radios:
                            value = await radio.get_attribute('value')
                            if (gender == 'M' and value in ['M', 'male', '남', '1']) or \
                               (gender == 'F' and value in ['F', 'female', '여', '2']):
                                await radio.click()
                                gender_input_success = True
                                break
                        if gender_input_success:
                            break
                except:
                    pass

            # 계산 버튼 클릭
            calc_selectors = [
                'button[onclick*="calc"]',
                'button[class*="calc"]',
                '.calc-btn',
                '#calcBtn',
                'input[type="submit"]',
                'button[type="submit"]'
            ]

            calc_success = False
            for selector in calc_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        # 네트워크 요청 모니터링 시작
                        self.captured_requests.clear()

                        await element.click()
                        await page.wait_for_timeout(5000)  # API 응답 대기
                        calc_success = True
                        logger.debug("계산 버튼 클릭 성공")
                        break
                except:
                    continue

            if not calc_success:
                logger.warning("계산 버튼을 찾을 수 없습니다")

            # 결과 추출
            premium_data = await self.extract_premium_result(page, age, gender)
            return premium_data

        except Exception as e:
            logger.error(f"보험료 추출 중 오류 ({age}세, {gender}): {e}")
            return None

    async def extract_premium_result(self, page: Page, age: int, gender: str) -> Optional[Dict[str, Any]]:
        """보험료 계산 결과 추출"""
        try:
            # 결과 표시 영역 찾기
            result_selectors = [
                '.premium-result',
                '.calc-result',
                '.price-result',
                '#premiumResult',
                '.result-table'
            ]

            premium_data = {
                'age': age,
                'gender': gender,
                'monthly_premium': '',
                'annual_premium': '',
                'coverage_amount': '',
                'payment_period': '',
                'guarantee_period': ''
            }

            # 화면에서 결과 추출
            for selector in result_selectors:
                try:
                    result_element = await page.query_selector(selector)
                    if result_element:
                        result_text = await result_element.inner_text()
                        logger.info(f"결과 텍스트: {result_text}")

                        # 텍스트에서 보험료 정보 파싱
                        parsed_data = self.parse_premium_text(result_text)
                        if parsed_data:
                            premium_data.update(parsed_data)
                            return premium_data
                except:
                    continue

            # API 응답에서 데이터 추출 시도
            if self.captured_requests:
                for request_data in self.captured_requests:
                    # API 호출 재현하여 데이터 가져오기
                    api_data = await self.call_premium_api(request_data, age, gender)
                    if api_data:
                        premium_data.update(api_data)
                        return premium_data

            return None

        except Exception as e:
            logger.error(f"결과 추출 중 오류: {e}")
            return None

    def parse_premium_text(self, text: str) -> Optional[Dict[str, str]]:
        """보험료 텍스트 파싱"""
        try:
            import re

            result = {}

            # 월 보험료 패턴
            monthly_patterns = [
                r'월\s*보험료[:\s]*(\d{1,3}(?:,\d{3})*)\s*원',
                r'월[:\s]*(\d{1,3}(?:,\d{3})*)\s*원',
                r'(\d{1,3}(?:,\d{3})*)\s*원\s*/\s*월'
            ]

            for pattern in monthly_patterns:
                match = re.search(pattern, text)
                if match:
                    result['monthly_premium'] = match.group(1) + '원'
                    break

            # 연 보험료 패턴
            annual_patterns = [
                r'연\s*보험료[:\s]*(\d{1,3}(?:,\d{3})*)\s*원',
                r'년[:\s]*(\d{1,3}(?:,\d{3})*)\s*원',
                r'(\d{1,3}(?:,\d{3})*)\s*원\s*/\s*년'
            ]

            for pattern in annual_patterns:
                match = re.search(pattern, text)
                if match:
                    result['annual_premium'] = match.group(1) + '원'
                    break

            # 보장금액 패턴
            coverage_patterns = [
                r'보장금액[:\s]*(\d{1,3}(?:,\d{3})*(?:\s*[억만천원]+)?)',
                r'가입금액[:\s]*(\d{1,3}(?:,\d{3})*(?:\s*[억만천원]+)?)'
            ]

            for pattern in coverage_patterns:
                match = re.search(pattern, text)
                if match:
                    result['coverage_amount'] = match.group(1)
                    break

            return result if result else None

        except Exception as e:
            logger.debug(f"텍스트 파싱 실패: {e}")
            return None

    async def call_premium_api(self, request_data: Dict, age: int, gender: str) -> Optional[Dict[str, str]]:
        """캡처된 API 호출을 재현하여 보험료 데이터 가져오기"""
        try:
            method = request_data['method']
            url = request_data['url']
            headers = request_data['headers']
            post_data = request_data['post_data']

            # POST 데이터에 나이/성별 정보 업데이트
            if post_data and method == 'POST':
                # URL 인코딩된 데이터 파싱
                from urllib.parse import parse_qs, urlencode

                if 'application/x-www-form-urlencoded' in headers.get('content-type', ''):
                    params = parse_qs(post_data)

                    # 나이/성별 파라미터 업데이트
                    age_keys = ['age', 'userAge', 'calcAge', 'inputAge']
                    gender_keys = ['gender', 'sex', 'userSex', 'calcGender']

                    for key in age_keys:
                        if key in params:
                            params[key] = [str(age)]

                    for key in gender_keys:
                        if key in params:
                            params[key] = [gender]

                    post_data = urlencode(params, doseq=True)

            # API 호출
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                data=post_data if method == 'POST' else None,
                timeout=30
            )

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    logger.info(f"API 응답 성공: {json.dumps(json_data, ensure_ascii=False)[:200]}...")

                    # JSON에서 보험료 정보 추출
                    return self.extract_premium_from_json(json_data)
                except:
                    # HTML 응답인 경우
                    html_data = response.text
                    return self.extract_premium_from_html(html_data)

        except Exception as e:
            logger.debug(f"API 호출 실패: {e}")

        return None

    def extract_premium_from_json(self, json_data: Dict) -> Optional[Dict[str, str]]:
        """JSON 응답에서 보험료 정보 추출"""
        try:
            result = {}

            # 일반적인 키 패턴들
            premium_keys = ['premium', 'monthlyPremium', 'price', 'amount']
            coverage_keys = ['coverage', 'coverageAmount', 'insuredAmount']

            def find_value_by_keys(data, keys):
                if isinstance(data, dict):
                    for key in keys:
                        if key in data:
                            return str(data[key])
                    # 중첩된 딕셔너리 검색
                    for value in data.values():
                        found = find_value_by_keys(value, keys)
                        if found:
                            return found
                elif isinstance(data, list):
                    for item in data:
                        found = find_value_by_keys(item, keys)
                        if found:
                            return found
                return None

            # 보험료 찾기
            premium = find_value_by_keys(json_data, premium_keys)
            if premium:
                result['monthly_premium'] = premium

            # 보장금액 찾기
            coverage = find_value_by_keys(json_data, coverage_keys)
            if coverage:
                result['coverage_amount'] = coverage

            return result if result else None

        except Exception as e:
            logger.debug(f"JSON 파싱 실패: {e}")
            return None

    def extract_premium_from_html(self, html_data: str) -> Optional[Dict[str, str]]:
        """HTML 응답에서 보험료 정보 추출"""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_data, 'html.parser')
            result = {}

            # 보험료 관련 요소 찾기
            premium_elements = soup.find_all(text=lambda text: text and any(
                keyword in text for keyword in ['보험료', '원', '월', '년']
            ))

            for element in premium_elements:
                parsed = self.parse_premium_text(element.strip())
                if parsed:
                    result.update(parsed)

            return result if result else None

        except Exception as e:
            logger.debug(f"HTML 파싱 실패: {e}")
            return None

    async def scrape_product_premiums(self, product_code: str) -> List[PremiumData]:
        """특정 상품의 모든 나이/성별 조합에 대한 보험료 수집"""
        logger.info(f"상품 보험료 수집 시작: {product_code}")

        premiums = []
        browser = None
        context = None
        page = None

        try:
            browser, context, page = await self.setup_browser()

            # 보험가격공시실 페이지로 이동
            await self.navigate_to_price_office(page)

            # 상품 찾기
            if not await self.find_product_in_price_office(page, product_code):
                logger.error(f"상품을 찾을 수 없습니다: {product_code}")
                return premiums

            product_info = self.products[product_code]

            # 모든 나이/성별 조합에 대해 보험료 추출
            total_combinations = len(self.age_range) * len(self.genders)
            current_count = 0

            for age in self.age_range:
                for gender in self.genders:
                    current_count += 1
                    logger.info(f"진행률: {current_count}/{total_combinations} - {age}세 {'남성' if gender == 'M' else '여성'}")

                    try:
                        premium_data = await self.extract_premium_for_age_gender(page, age, gender)
                        if premium_data:
                            premium = PremiumData(
                                product_code=product_code,
                                product_name=product_info['name'],
                                age=age,
                                gender=gender,
                                coverage_amount=premium_data.get('coverage_amount', ''),
                                monthly_premium=premium_data.get('monthly_premium', ''),
                                annual_premium=premium_data.get('annual_premium', ''),
                                payment_period=premium_data.get('payment_period', ''),
                                guarantee_period=premium_data.get('guarantee_period', ''),
                                scraped_at=datetime.now().isoformat()
                            )
                            premiums.append(premium)
                            logger.info(f"수집 성공: {age}세 {gender} - {premium_data.get('monthly_premium', '정보없음')}")

                        # 다음 계산 전 잠시 대기
                        await page.wait_for_timeout(2000)

                    except Exception as e:
                        logger.warning(f"보험료 수집 실패 {age}세 {gender}: {e}")
                        continue

        except Exception as e:
            logger.error(f"상품 보험료 수집 중 오류: {e}")
        finally:
            if browser:
                await browser.close()

        logger.info(f"보험료 수집 완료: {len(premiums)}개")
        return premiums

    def save_premiums(self, premiums: List[PremiumData], product_code: str):
        """보험료 데이터 저장"""
        if not premiums:
            logger.warning("저장할 보험료 데이터가 없습니다")
            return

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"kb_premiums_{product_code}_{timestamp}.json"

        data = {
            "metadata": {
                "product_code": product_code,
                "product_name": self.products[product_code]['name'],
                "scraped_at": datetime.now().isoformat(),
                "total_records": len(premiums),
                "age_range": f"{min(self.age_range)}-{max(self.age_range)}",
                "genders": self.genders
            },
            "premiums": [asdict(premium) for premium in premiums]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"보험료 데이터 저장: {filename}")

        # CSV 형태로도 저장
        self.save_premiums_csv(premiums, product_code, timestamp)

    def save_premiums_csv(self, premiums: List[PremiumData], product_code: str, timestamp: str):
        """보험료 데이터 CSV 저장"""
        try:
            import csv

            filename = f"kb_premiums_{product_code}_{timestamp}.csv"

            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                # 헤더
                writer.writerow([
                    'Product Code', 'Product Name', 'Age', 'Gender',
                    'Coverage Amount', 'Monthly Premium', 'Annual Premium',
                    'Payment Period', 'Guarantee Period', 'Scraped At'
                ])

                # 데이터
                for premium in premiums:
                    writer.writerow([
                        premium.product_code,
                        premium.product_name,
                        premium.age,
                        '남성' if premium.gender == 'M' else '여성',
                        premium.coverage_amount,
                        premium.monthly_premium,
                        premium.annual_premium,
                        premium.payment_period,
                        premium.guarantee_period,
                        premium.scraped_at
                    ])

            logger.info(f"CSV 저장: {filename}")

        except Exception as e:
            logger.error(f"CSV 저장 실패: {e}")

async def main():
    """메인 실행 함수"""
    try:
        print("KB생명 보험료 스크래퍼를 시작합니다...")
        print("개발자 도구 네트워크 분석 기반 API 호출 방식")

        scraper = KBPriceScraper()

        # KB 착한암보험 테스트
        product_code = "ON_PD_KC_01"
        print(f"\n테스트 상품: {scraper.products[product_code]['name']}")
        print("브라우저가 열리면 보험가격공시실에서 수동으로 보험료 계산을 한 번 해보세요.")
        print("네트워크 요청을 분석하여 API 호출 패턴을 학습합니다.")

        # 보험료 수집
        premiums = await scraper.scrape_product_premiums(product_code)

        if premiums:
            print(f"\n수집 완료: {len(premiums)}개의 보험료 데이터")

            # 저장
            scraper.save_premiums(premiums, product_code)

            # 샘플 출력
            print("\n샘플 데이터:")
            for premium in premiums[:5]:
                print(f"  {premium.age}세 {'남성' if premium.gender == 'M' else '여성'}: {premium.monthly_premium}")
        else:
            print("\n수집된 보험료 데이터가 없습니다.")
            print("브라우저에서 수동으로 보험료 계산 과정을 확인해보세요.")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"실행 중 오류: {e}")
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())