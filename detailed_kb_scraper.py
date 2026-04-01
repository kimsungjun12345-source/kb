"""
KB생명 보험 상품별 세부항목 및 특약 전용 스크래퍼
각 상품의 고유한 특성을 고려한 맞춤형 데이터 수집
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
        logging.FileHandler('detailed_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class SpecialClause:
    """특약 정보"""
    name: str
    description: str
    premium: str
    conditions: str

@dataclass
class CoverageItem:
    """보장 항목"""
    category: str
    name: str
    amount: str
    period: str
    conditions: str

@dataclass
class DetailedInsuranceProduct:
    """상세 보험 상품 정보"""
    product_code: str
    product_name: str
    product_type: str
    description: str

    # 기본 보장
    main_coverage: List[CoverageItem]

    # 특약
    special_clauses: List[SpecialClause]

    # 나이별/성별 보험료
    premium_table: Dict[str, Dict[str, str]]  # {age: {male: price, female: price}}

    # 가입 조건
    join_conditions: Dict[str, Any]

    # 지급 조건
    payment_conditions: List[str]

    # 면책 사항
    exclusions: List[str]

    # 약관 정보
    terms_summary: str
    terms_full_text: str

    # 기타 정보
    company_info: str
    contact_info: str

    scraped_at: str
    url: str

class DetailedKBScraper:
    """KB생명 상세 정보 스크래퍼"""

    def __init__(self):
        self.products_config = {
            "ON_PD_KC_01": {  # KB 착한암보험
                "name": "KB 착한암보험 무배당",
                "type": "암보험",
                "special_selectors": {
                    "cancer_types": [".cancer-list li", ".암종류 li"],
                    "surgery_benefit": [".수술급여 li", ".surgery-list li"],
                    "diagnosis_benefit": [".진단급여", ".diagnosis-benefit"]
                }
            },
            "ON_PD_YG_01": {  # KB e-건강보험 (일반심사)
                "name": "KB 딱좋은 e-건강보험",
                "type": "건강보험",
                "special_selectors": {
                    "health_checkup": [".건강검진 li", ".checkup-list li"],
                    "medical_benefit": [".의료급여", ".medical-benefit"],
                    "hospitalization": [".입원급여", ".hospitalization-benefit"]
                }
            },
            "ON_PD_YT_01": {  # KB e-건강보험 (간편심사)
                "name": "KB 딱좋은 e-건강보험 간편형",
                "type": "건강보험",
                "special_selectors": {
                    "simple_questions": [".간편심사 li", ".simple-check li"],
                    "limited_coverage": [".제한보장", ".limited-benefit"],
                    "quick_join": [".빠른가입", ".quick-join"]
                }
            },
            "ON_PD_SR_01": {  # KB 착한정기보험
                "name": "KB 착한정기보험II",
                "type": "정기보험",
                "special_selectors": {
                    "term_options": [".보험기간", ".term-options li"],
                    "death_benefit": [".사망보장", ".death-benefit"],
                    "renewal_conditions": [".갱신조건", ".renewal-info"]
                }
            },
            "ON_PD_NP_01": {  # KB 평생연금보험
                "name": "KB 하이파이브평생연금보험",
                "type": "연금보험",
                "special_selectors": {
                    "pension_start": [".연금개시", ".pension-start"],
                    "guaranteed_period": [".보증기간", ".guarantee-period"],
                    "payment_options": [".납입방법", ".payment-method li"]
                }
            }
        }

        self.common_selectors = {
            "main_title": [
                "h1", ".product-title", ".prod-title",
                ".insurance-title", ".main-title"
            ],
            "subtitle": [
                ".product-subtitle", ".prod-subtitle",
                ".sub-title", "h2"
            ],
            "main_benefits": [
                ".main-benefit li", ".primary-coverage li",
                ".기본보장 li", ".주계약 li", ".보장내용 li"
            ],
            "special_benefits": [
                ".special-benefit li", ".특약 li",
                ".additional-coverage li", ".선택특약 li"
            ],
            "premium_table": [
                ".premium-table", ".보험료표", ".price-table",
                "table[class*='premium']", "table[class*='price']"
            ],
            "conditions": [
                ".join-condition li", ".가입조건 li",
                ".condition li", ".requirement li"
            ],
            "exclusions": [
                ".exclusion li", ".면책 li", ".exception li",
                ".불보장 li", ".제외사항 li"
            ],
            "age_range": [
                ".age-limit", ".연령제한", ".age-condition",
                ".가입연령", "[class*='age'][class*='limit']"
            ],
            "contact": [
                ".contact-info", ".문의전화", ".customer-center",
                ".연락처", "[href^='tel:']"
            ]
        }

    async def setup_browser(self):
        """브라우저 설정"""
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=False,
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

    async def extract_coverage_items(self, page: Page, product_code: str) -> List[CoverageItem]:
        """보장 항목 상세 추출"""
        coverage_items = []

        try:
            # 상품별 맞춤 셀렉터 사용
            config = self.products_config.get(product_code, {})
            special_selectors = config.get("special_selectors", {})

            # 기본 보장 항목 추출
            main_selectors = self.common_selectors["main_benefits"]

            for selector in main_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if text and text.strip():
                            # 텍스트 파싱하여 구조화
                            coverage_item = await self.parse_coverage_text(text.strip())
                            if coverage_item:
                                coverage_items.append(coverage_item)
                except Exception as e:
                    logger.debug(f"보장항목 추출 실패 {selector}: {e}")
                    continue

            # 상품별 특수 보장 항목
            for special_type, selectors in special_selectors.items():
                for selector in selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            text = await element.inner_text()
                            if text and text.strip():
                                coverage_item = await self.parse_coverage_text(
                                    text.strip(), category=special_type
                                )
                                if coverage_item:
                                    coverage_items.append(coverage_item)
                    except Exception as e:
                        logger.debug(f"특수 보장항목 추출 실패 {selector}: {e}")
                        continue

        except Exception as e:
            logger.error(f"보장 항목 추출 중 오류: {e}")

        return coverage_items

    async def parse_coverage_text(self, text: str, category: str = "기본보장") -> Optional[CoverageItem]:
        """보장 텍스트 파싱"""
        try:
            # 일반적인 보장 항목 패턴 매칭
            import re

            # 금액 패턴 (예: 1억원, 5000만원, 100% 등)
            amount_patterns = [
                r'(\d+(?:,\d+)*(?:\.\d+)?)\s*([억만천원%]+)',
                r'(\d+(?:,\d+)*)\s*(원|%)',
                r'최대\s*(\d+(?:,\d+)*)\s*([억만천원%]+)'
            ]

            amount = ""
            for pattern in amount_patterns:
                match = re.search(pattern, text)
                if match:
                    amount = f"{match.group(1)}{match.group(2)}"
                    break

            # 기간 패턴 (예: 100세까지, 10년, 평생 등)
            period_patterns = [
                r'(\d+)\s*세\s*까지',
                r'(\d+)\s*년',
                r'(평생|종신|갱신|만기)',
                r'(\d+)\s*회'
            ]

            period = ""
            for pattern in period_patterns:
                match = re.search(pattern, text)
                if match:
                    period = match.group(0)
                    break

            # 조건 추출 (나머지 텍스트)
            conditions = text
            if amount:
                conditions = conditions.replace(amount, "").strip()
            if period:
                conditions = conditions.replace(period, "").strip()

            return CoverageItem(
                category=category,
                name=text[:50],  # 첫 50자를 이름으로
                amount=amount,
                period=period,
                conditions=conditions[:200] if conditions else ""
            )

        except Exception as e:
            logger.debug(f"보장 텍스트 파싱 실패: {e}")
            return None

    async def extract_special_clauses(self, page: Page, product_code: str) -> List[SpecialClause]:
        """특약 정보 추출"""
        special_clauses = []

        try:
            # 특약 섹션 찾기
            special_selectors = [
                ".special-clause", ".특약", ".additional-benefit",
                ".option-benefit", ".선택특약", ".부가특약"
            ]

            for selector in special_selectors:
                try:
                    # 특약 섹션으로 이동
                    section = await page.query_selector(selector)
                    if section:
                        await section.scroll_into_view_if_needed()
                        await page.wait_for_timeout(1000)

                        # 특약 리스트 추출
                        clause_elements = await section.query_selector_all("li, .clause-item, .특약항목")

                        for element in clause_elements:
                            text = await element.inner_text()
                            if text and len(text.strip()) > 5:
                                clause = await self.parse_special_clause(text.strip())
                                if clause:
                                    special_clauses.append(clause)
                        break

                except Exception as e:
                    logger.debug(f"특약 추출 실패 {selector}: {e}")
                    continue

        except Exception as e:
            logger.error(f"특약 추출 중 오류: {e}")

        return special_clauses

    async def parse_special_clause(self, text: str) -> Optional[SpecialClause]:
        """특약 텍스트 파싱"""
        try:
            import re

            # 특약명 추출 (첫 줄 또는 괄호 앞)
            name_match = re.search(r'^([^(]+)', text)
            name = name_match.group(1).strip() if name_match else text[:30]

            # 보험료 패턴
            premium_patterns = [
                r'월\s*(\d+(?:,\d+)*)\s*원',
                r'(\d+(?:,\d+)*)\s*원',
                r'(\d+(?:\.\d+)?)\s*%'
            ]

            premium = ""
            for pattern in premium_patterns:
                match = re.search(pattern, text)
                if match:
                    premium = match.group(0)
                    break

            # 설명 (전체 텍스트에서 이름과 보험료 제외)
            description = text
            if premium:
                description = description.replace(premium, "").strip()

            return SpecialClause(
                name=name,
                description=description[:300],
                premium=premium,
                conditions=""
            )

        except Exception as e:
            logger.debug(f"특약 파싱 실패: {e}")
            return None

    async def extract_premium_table(self, page: Page) -> Dict[str, Dict[str, str]]:
        """보험료 테이블 추출"""
        premium_table = {}

        try:
            # 보험료 테이블 찾기
            table_selectors = self.common_selectors["premium_table"]

            for selector in table_selectors:
                try:
                    table = await page.query_selector(selector)
                    if table:
                        # 테이블 행 추출
                        rows = await table.query_selector_all("tr")

                        headers = []
                        for i, row in enumerate(rows):
                            cells = await row.query_selector_all("td, th")
                            cell_texts = []

                            for cell in cells:
                                text = await cell.inner_text()
                                cell_texts.append(text.strip())

                            if i == 0:  # 헤더 행
                                headers = cell_texts
                            else:  # 데이터 행
                                if len(cell_texts) >= 2:
                                    age_or_key = cell_texts[0]
                                    if age_or_key.isdigit() or '세' in age_or_key:
                                        premium_table[age_or_key] = {}
                                        for j, value in enumerate(cell_texts[1:], 1):
                                            if j < len(headers):
                                                premium_table[age_or_key][headers[j]] = value
                        break

                except Exception as e:
                    logger.debug(f"보험료 테이블 추출 실패 {selector}: {e}")
                    continue

        except Exception as e:
            logger.error(f"보험료 테이블 추출 중 오류: {e}")

        return premium_table

    async def extract_detailed_product(self, page: Page, url: str) -> Optional[DetailedInsuranceProduct]:
        """상세 상품 정보 추출"""
        try:
            product_code = self.extract_product_code(url)
            config = self.products_config.get(product_code, {})

            logger.info(f"상세 정보 추출 시작: {config.get('name', product_code)}")

            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)

            # 팝업 처리
            await self.handle_popups(page)

            # 기본 정보
            product_name = await self.safe_get_text(page, self.common_selectors["main_title"])
            if not product_name:
                product_name = config.get("name", f"상품_{product_code}")

            description = await self.safe_get_text(page, self.common_selectors["subtitle"])

            # 보장 항목 상세 추출
            main_coverage = await self.extract_coverage_items(page, product_code)

            # 특약 추출
            special_clauses = await self.extract_special_clauses(page, product_code)

            # 보험료 테이블
            premium_table = await self.extract_premium_table(page)

            # 가입 조건
            join_conditions = await self.extract_join_conditions(page)

            # 지급 조건
            payment_conditions = await self.safe_get_texts(page, [
                ".payment-condition li", ".지급조건 li",
                ".benefit-condition li", ".급여조건 li"
            ])

            # 면책 사항
            exclusions = await self.safe_get_texts(page, self.common_selectors["exclusions"])

            # 약관 정보
            terms_summary, terms_full = await self.extract_terms_info(page)

            # 연락처 정보
            contact_info = await self.safe_get_text(page, self.common_selectors["contact"])

            product = DetailedInsuranceProduct(
                product_code=product_code,
                product_name=product_name,
                product_type=config.get("type", "보험"),
                description=description,
                main_coverage=main_coverage,
                special_clauses=special_clauses,
                premium_table=premium_table,
                join_conditions=join_conditions,
                payment_conditions=payment_conditions,
                exclusions=exclusions,
                terms_summary=terms_summary,
                terms_full_text=terms_full,
                company_info="KB생명보험",
                contact_info=contact_info,
                scraped_at=datetime.now().isoformat(),
                url=url
            )

            logger.info(f"상세 정보 추출 완료: {product_name}")
            logger.info(f"  - 기본 보장: {len(main_coverage)}개")
            logger.info(f"  - 특약: {len(special_clauses)}개")
            logger.info(f"  - 보험료 정보: {len(premium_table)}개 연령대")
            logger.info(f"  - 면책사항: {len(exclusions)}개")

            return product

        except Exception as e:
            logger.error(f"상세 상품 정보 추출 실패 {url}: {e}")
            return None

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
            except:
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
            except:
                continue
        return texts

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
                    break
            except:
                continue

    async def extract_join_conditions(self, page: Page) -> Dict[str, Any]:
        """가입 조건 추출"""
        conditions = {}

        try:
            # 나이 제한
            age_text = await self.safe_get_text(page, self.common_selectors["age_range"])
            if age_text:
                import re
                age_match = re.search(r'(\d+)세\s*~\s*(\d+)세', age_text)
                if age_match:
                    conditions['age_min'] = int(age_match.group(1))
                    conditions['age_max'] = int(age_match.group(2))

            # 기타 조건
            condition_texts = await self.safe_get_texts(page, self.common_selectors["conditions"])
            conditions['requirements'] = condition_texts

        except Exception as e:
            logger.warning(f"가입 조건 추출 중 오류: {e}")

        return conditions

    async def extract_terms_info(self, page: Page) -> tuple[str, str]:
        """약관 정보 추출"""
        terms_summary = ""
        terms_full = ""

        try:
            # 약관 버튼 찾기
            terms_selectors = [
                '.terms-button', '.약관보기', 'a[href*="terms"]',
                '.contract-terms', 'button[onclick*="terms"]'
            ]

            for selector in terms_selectors:
                try:
                    terms_btn = await page.query_selector(selector)
                    if terms_btn:
                        await terms_btn.click()
                        await page.wait_for_timeout(3000)

                        # 약관 내용 추출
                        content_selectors = [
                            '.terms-content', '.contract-content',
                            '.modal-body', '#terms-modal', '.약관내용'
                        ]

                        full_content = await self.safe_get_text(page, content_selectors)
                        if full_content:
                            terms_full = full_content
                            terms_summary = full_content[:500] + "..." if len(full_content) > 500 else full_content
                        break

                except Exception as e:
                    logger.debug(f"약관 추출 실패 {selector}: {e}")
                    continue

        except Exception as e:
            logger.warning(f"약관 추출 중 오류: {e}")

        return terms_summary, terms_full

    async def scrape_all_detailed_products(self) -> List[DetailedInsuranceProduct]:
        """모든 상품 상세 정보 스크래핑"""
        products = []
        browser = None
        context = None

        try:
            browser, context = await self.setup_browser()
            page = await context.new_page()

            urls = [
                "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5",
                "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5",
                "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YT_01&productType=5",
                "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_SR_01&productType=5",
                "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_NP_01&productType=5"
            ]

            for i, url in enumerate(urls, 1):
                try:
                    logger.info(f"진행률: {i}/{len(urls)}")

                    product = await self.extract_detailed_product(page, url)
                    if product:
                        products.append(product)

                    # 다음 요청 전 대기
                    if i < len(urls):
                        await page.wait_for_timeout(3000)

                except Exception as e:
                    logger.error(f"상품 처리 중 오류 {url}: {e}")
                    continue

        except Exception as e:
            logger.error(f"스크래핑 중 오류: {e}")
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

        return products

    def save_detailed_results(self, products: List[DetailedInsuranceProduct]):
        """상세 결과 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f"kb_detailed_products_{timestamp}.json"

        # JSON 저장
        data = {
            "metadata": {
                "scraped_at": datetime.now().isoformat(),
                "total_products": len(products),
                "scraper_version": "detailed_1.0",
                "includes_special_clauses": True,
                "includes_coverage_details": True
            },
            "products": [asdict(product) for product in products]
        }

        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"상세 데이터 저장: {json_filename}")
        return json_filename

async def main():
    """메인 실행 함수"""
    try:
        print("KB생명 보험 상품 상세 정보 스크래핑을 시작합니다...")

        scraper = DetailedKBScraper()
        products = await scraper.scrape_all_detailed_products()

        if products:
            print(f"\n총 {len(products)}개의 상세 보험 상품 정보 추출 완료!")

            filename = scraper.save_detailed_results(products)
            print(f"저장된 파일: {filename}")

            # 상세 요약 출력
            for product in products:
                print(f"\n=== {product.product_name} ({product.product_type}) ===")
                print(f"기본 보장: {len(product.main_coverage)}개")
                print(f"특약: {len(product.special_clauses)}개")
                print(f"보험료 테이블: {len(product.premium_table)}개 연령대")
                print(f"지급 조건: {len(product.payment_conditions)}개")
                print(f"면책 사항: {len(product.exclusions)}개")

                if product.join_conditions.get('age_min'):
                    print(f"가입 연령: {product.join_conditions['age_min']}~{product.join_conditions['age_max']}세")

                # 특약 요약
                if product.special_clauses:
                    print("주요 특약:")
                    for i, clause in enumerate(product.special_clauses[:3], 1):
                        print(f"  {i}. {clause.name}")
        else:
            print("추출된 상세 정보가 없습니다.")

    except Exception as e:
        print(f"실행 중 오류: {e}")
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())