"""
Playwright를 사용한 KB생명 보험 상품 스크래핑 시스템
더 안정적이고 빠른 웹 스크래핑을 위한 개선된 버전
"""

import json
import time
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('playwright_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class InsuranceProduct:
    """보험 상품 정보 데이터 클래스"""
    product_code: str
    product_name: str
    description: str
    key_features: List[str]
    coverage_details: List[str]
    premium_info: Dict[str, str]
    terms_conditions: str
    age_limits: Dict[str, int]
    scraped_at: str
    url: str
    additional_info: Dict[str, Any]

class PlaywrightKBScraper:
    """Playwright 기반 KB생명 보험 상품 스크래퍼"""

    def __init__(self):
        self.urls = [
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YT_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_SR_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_NP_01&productType=5"
        ]
        self.test_ages = [19, 25, 30, 35, 40, 45, 50, 55, 60, 65]

        # CSS 셀렉터들
        self.selectors = {
            'product_name': [
                'h1.product-title',
                '.product-name',
                'h1',
                '.title',
                '#productName',
                '.product-tit',
                '.prod-name',
                '.ins-title'
            ],
            'description': [
                '.product-description',
                '.product-summary',
                '.description',
                '.summary',
                '.product-cont',
                '.prod-desc'
            ],
            'features': [
                '.feature-list li',
                '.benefit-list li',
                '.key-point li',
                '.point-list li',
                '[class*="feature"] li',
                '[class*="benefit"] li',
                '.spec-list li'
            ],
            'coverage': [
                'table.coverage-table tr',
                '.coverage-list li',
                '.guarantee-list li',
                '[class*="coverage"] tr',
                '.보장내용 li',
                '.coverage-item',
                '.guarantee-item'
            ],
            'age_input': [
                'input[name*="age"]',
                'input[id*="age"]',
                '.age-input',
                'input[placeholder*="나이"]',
                'input[type="number"]',
                'input[placeholder*="연령"]',
                'select[name*="age"]'
            ],
            'calc_button': [
                'button[class*="calc"]',
                'button[class*="계산"]',
                '.calc-btn',
                'input[type="button"][value*="계산"]',
                'button[type="submit"]',
                '.btn-calc'
            ],
            'premium_result': [
                '.premium-result',
                '.calc-result',
                '.보험료',
                '.premium-amount',
                '[class*="premium"]',
                '[class*="result"]',
                '.price-result'
            ],
            'terms_button': [
                '.terms-button',
                '.약관보기',
                'a[href*="terms"]',
                '.contract-terms',
                'button[onclick*="terms"]'
            ]
        }

    async def setup_browser(self) -> tuple[Browser, BrowserContext]:
        """브라우저 및 컨텍스트 설정"""
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=False,  # 디버깅을 위해 헤드리스 모드 비활성화
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )

        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        return browser, context

    def extract_product_code(self, url: str) -> str:
        """URL에서 상품 코드 추출"""
        try:
            if 'linkCd=' in url:
                return url.split('linkCd=')[1].split('&')[0]
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'

    async def safe_get_text(self, page: Page, selectors: List[str]) -> str:
        """안전한 텍스트 추출"""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.inner_text()
                    if text and text.strip():
                        return text.strip()
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        return ""

    async def safe_get_texts(self, page: Page, selectors: List[str]) -> List[str]:
        """안전한 다중 텍스트 추출"""
        texts = []
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    text = await element.inner_text()
                    if text and text.strip() and text.strip() not in texts:
                        texts.append(text.strip())
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")
                continue
        return texts

    async def handle_popups(self, page: Page):
        """팝업 처리"""
        popup_selectors = [
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '.popup-close',
            '.modal-close',
            '#popup_close',
            'button[onclick*="close"]',
            '.layer-close'
        ]

        for selector in popup_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    await page.wait_for_timeout(1000)
                    logger.info(f"팝업 닫기 성공: {selector}")
                    break
            except Exception as e:
                logger.debug(f"팝업 처리 실패 {selector}: {e}")
                continue

    async def extract_premium_with_age(self, page: Page) -> Dict[str, str]:
        """나이별 보험료 추출"""
        premium_info = {}

        try:
            # 보험료 계산 섹션 찾기
            calc_selectors = [
                '.premium-calculator',
                '.보험료계산',
                '#premium-calc',
                '.calc-section',
                '[class*="calc"]',
                '.price-calc'
            ]

            # 계산 섹션으로 스크롤
            for selector in calc_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        await element.scroll_into_view_if_needed()
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue

            # 나이 입력 및 계산
            for age in self.test_ages:
                try:
                    age_input_found = False

                    # 나이 입력 필드 찾기
                    for input_selector in self.selectors['age_input']:
                        try:
                            age_element = await page.query_selector(input_selector)
                            if age_element:
                                await age_element.clear()
                                await age_element.fill(str(age))
                                age_input_found = True
                                logger.info(f"나이 {age} 입력 성공")
                                break
                        except Exception as e:
                            logger.debug(f"나이 입력 실패 {input_selector}: {e}")
                            continue

                    if not age_input_found:
                        logger.warning(f"나이 입력 필드를 찾을 수 없습니다: {age}")
                        continue

                    # 계산 버튼 클릭
                    calc_clicked = False
                    for btn_selector in self.selectors['calc_button']:
                        try:
                            calc_btn = await page.query_selector(btn_selector)
                            if calc_btn:
                                await calc_btn.click()
                                calc_clicked = True
                                logger.info("계산 버튼 클릭 성공")
                                break
                        except Exception as e:
                            logger.debug(f"계산 버튼 클릭 실패 {btn_selector}: {e}")
                            continue

                    if not calc_clicked:
                        # Enter 키로 시도
                        try:
                            await page.keyboard.press('Enter')
                            logger.info("Enter 키로 계산 시도")
                        except:
                            pass

                    # 결과 대기 및 추출
                    await page.wait_for_timeout(3000)

                    premium_text = await self.safe_get_text(page, self.selectors['premium_result'])
                    if premium_text and any(char.isdigit() for char in premium_text):
                        premium_info[f"age_{age}"] = premium_text
                        logger.info(f"나이 {age} 보험료: {premium_text}")

                    await page.wait_for_timeout(1000)

                except Exception as e:
                    logger.warning(f"나이 {age} 보험료 계산 중 오류: {e}")
                    continue

        except Exception as e:
            logger.error(f"보험료 추출 중 오류: {e}")

        return premium_info

    async def extract_terms(self, page: Page) -> str:
        """약관 정보 추출"""
        try:
            for selector in self.selectors['terms_button']:
                try:
                    terms_btn = await page.query_selector(selector)
                    if terms_btn:
                        # 새 페이지가 열릴 수 있으므로 새 탭 모니터링
                        async with page.context.expect_page() as new_page_info:
                            await terms_btn.click()
                            await page.wait_for_timeout(3000)

                        # 새 페이지가 열렸는지 확인
                        try:
                            new_page = await asyncio.wait_for(new_page_info.value, timeout=5)
                            content = await new_page.inner_text('body')
                            await new_page.close()
                            if len(content) > 100:
                                return content[:2000] + "..." if len(content) > 2000 else content
                        except asyncio.TimeoutError:
                            # 같은 페이지에서 모달이 열린 경우
                            modal_selectors = [
                                '.terms-content',
                                '.contract-content',
                                '.modal-body',
                                '#terms-modal',
                                '.약관내용'
                            ]
                            terms = await self.safe_get_text(page, modal_selectors)
                            if len(terms) > 100:
                                return terms[:2000] + "..." if len(terms) > 2000 else terms
                        break
                except Exception as e:
                    logger.debug(f"약관 추출 실패 {selector}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"약관 추출 중 오류: {e}")

        return ""

    async def extract_product_info(self, page: Page, url: str) -> Optional[InsuranceProduct]:
        """단일 상품 정보 추출"""
        try:
            logger.info(f"상품 정보 추출 시작: {url}")

            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)

            # 팝업 처리
            await self.handle_popups(page)

            # 기본 정보 추출
            product_name = await self.safe_get_text(page, self.selectors['product_name'])
            description = await self.safe_get_text(page, self.selectors['description'])
            key_features = await self.safe_get_texts(page, self.selectors['features'])
            coverage_details = await self.safe_get_texts(page, self.selectors['coverage'])

            # 보험료 정보 추출
            premium_info = await self.extract_premium_with_age(page)

            # 약관 정보 추출
            terms = await self.extract_terms(page)

            # 나이 제한 정보 추출
            age_limits = await self.extract_age_limits(page)

            # 추가 정보 추출
            additional_info = await self.extract_additional_info(page)

            # 상품 코드 추출
            product_code = self.extract_product_code(url)

            product = InsuranceProduct(
                product_code=product_code,
                product_name=product_name or f"상품_{product_code}",
                description=description,
                key_features=key_features,
                coverage_details=coverage_details,
                premium_info=premium_info,
                terms_conditions=terms,
                age_limits=age_limits,
                scraped_at=datetime.now().isoformat(),
                url=url,
                additional_info=additional_info
            )

            logger.info(f"상품 정보 추출 완료: {product.product_name}")
            return product

        except Exception as e:
            logger.error(f"상품 정보 추출 실패 {url}: {e}")
            return None

    async def extract_age_limits(self, page: Page) -> Dict[str, int]:
        """나이 제한 정보 추출"""
        age_limits = {}
        try:
            # 나이 제한 관련 텍스트 찾기
            age_selectors = [
                '[class*="age"]',
                '[class*="limit"]',
                '.condition',
                '.가입조건',
                '.join-condition'
            ]

            for selector in age_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if any(keyword in text for keyword in ['나이', '세', '연령']):
                            # 나이 범위 파싱
                            import re
                            age_pattern = r'(\d+)세\s*~\s*(\d+)세'
                            matches = re.findall(age_pattern, text)
                            if matches:
                                min_age, max_age = matches[0]
                                age_limits = {
                                    'min_age': int(min_age),
                                    'max_age': int(max_age)
                                }
                                break
                except:
                    continue
                if age_limits:
                    break
        except Exception as e:
            logger.warning(f"나이 제한 추출 중 오류: {e}")

        return age_limits

    async def extract_additional_info(self, page: Page) -> Dict[str, Any]:
        """추가 정보 추출"""
        additional = {
            'contact_info': '',
            'features_count': 0,
            'coverage_count': 0,
            'page_title': '',
            'meta_description': ''
        }

        try:
            # 페이지 제목
            additional['page_title'] = await page.title()

            # 메타 설명
            meta_desc = await page.query_selector('meta[name="description"]')
            if meta_desc:
                additional['meta_description'] = await meta_desc.get_attribute('content') or ''

            # 연락처 정보
            contact_selectors = [
                '.contact-info',
                '.phone-number',
                '[href^="tel:"]'
            ]
            additional['contact_info'] = await self.safe_get_text(page, contact_selectors)

        except Exception as e:
            logger.warning(f"추가 정보 추출 중 오류: {e}")

        return additional

    async def scrape_all_products(self) -> List[InsuranceProduct]:
        """모든 상품 스크래핑"""
        products = []
        browser = None
        context = None

        try:
            browser, context = await self.setup_browser()
            page = await context.new_page()

            for i, url in enumerate(self.urls, 1):
                try:
                    logger.info(f"진행률: {i}/{len(self.urls)} - 상품 처리 중...")

                    product = await self.extract_product_info(page, url)
                    if product:
                        products.append(product)
                        logger.info(f"상품 추출 성공: {product.product_name}")
                    else:
                        logger.warning(f"상품 추출 실패: {url}")

                    # 다음 요청 전 대기
                    if i < len(self.urls):
                        await page.wait_for_timeout(3000)

                except Exception as e:
                    logger.error(f"URL 처리 중 오류 {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"스크래핑 중 오류: {e}")
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

        logger.info(f"총 {len(products)}개 상품 정보 추출 완료")
        return products

    def save_to_json(self, products: List[InsuranceProduct]):
        """JSON 저장"""
        filename = f"kb_insurance_playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "metadata": {
                "scraped_at": datetime.now().isoformat(),
                "total_products": len(products),
                "scraper_version": "playwright_1.0",
                "scraper_type": "Playwright"
            },
            "products": [asdict(product) for product in products]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 데이터 저장: {filename}")
        return filename

    def save_to_csv(self, products: List[InsuranceProduct]):
        """CSV 저장"""
        filename = f"kb_insurance_playwright_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            import csv

            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                # 헤더 작성
                writer.writerow([
                    'Product Code', 'Product Name', 'Description',
                    'Key Features Count', 'Coverage Count', 'Premium Ages',
                    'Age Min', 'Age Max', 'Terms Length', 'Page Title',
                    'Scraped At', 'URL'
                ])

                # 데이터 작성
                for product in products:
                    writer.writerow([
                        product.product_code,
                        product.product_name,
                        product.description[:200] + '...' if len(product.description) > 200 else product.description,
                        len(product.key_features),
                        len(product.coverage_details),
                        len(product.premium_info),
                        product.age_limits.get('min_age', ''),
                        product.age_limits.get('max_age', ''),
                        len(product.terms_conditions),
                        product.additional_info.get('page_title', ''),
                        product.scraped_at,
                        product.url
                    ])

            logger.info(f"CSV 데이터 저장: {filename}")
            return filename

        except Exception as e:
            logger.error(f"CSV 저장 실패: {e}")
            return None

async def main():
    """메인 실행 함수"""
    try:
        print("Playwright KB생명 보험 상품 스크래핑을 시작합니다...")

        scraper = PlaywrightKBScraper()

        # 스크래핑 실행
        products = await scraper.scrape_all_products()

        if products:
            print(f"\n총 {len(products)}개의 보험 상품 정보 추출 완료!")

            # JSON 저장
            json_file = scraper.save_to_json(products)

            # CSV 저장
            csv_file = scraper.save_to_csv(products)

            # 결과 요약 출력
            print(f"\n추출 결과 요약:")
            print(f"JSON 파일: {json_file}")
            if csv_file:
                print(f"CSV 파일: {csv_file}")

            for i, product in enumerate(products, 1):
                print(f"\n{i}. {product.product_name} ({product.product_code})")
                print(f"   - 특징: {len(product.key_features)}개")
                print(f"   - 보장: {len(product.coverage_details)}개")
                print(f"   - 나이별 보험료: {len(product.premium_info)}개")
                print(f"   - 약관 길이: {len(product.terms_conditions)}자")
                if product.age_limits:
                    print(f"   - 가입연령: {product.age_limits.get('min_age', '?')}~{product.age_limits.get('max_age', '?')}세")

        else:
            print("추출된 상품 정보가 없습니다.")
            print("로그 파일(playwright_scraper.log)을 확인해주세요.")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"실행 중 오류: {e}")
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())