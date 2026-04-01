"""
KB생명 보험 상품 정보 스크래핑 간단 버전
pandas 없이 동작하는 가벼운 버전
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('kb_scraper.log', encoding='utf-8'),
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
    scraped_at: str
    url: str

class SimpleKBInsuranceScraper:
    """간단한 KB생명 보험 상품 스크래핑 클래스"""

    def __init__(self):
        self.urls = [
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YT_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_SR_01&productType=5",
            "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_NP_01&productType=5"
        ]
        self.driver = None
        self.wait = None
        self.test_ages = [19, 25, 30, 35, 40, 45, 50, 55, 60, 65]

    def setup_driver(self):
        """WebDriver 설정"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            service = webdriver.chrome.service.Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # 자동화 감지 회피
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            self.wait = WebDriverWait(self.driver, 15)
            self.driver.set_page_load_timeout(30)

            logger.info("WebDriver 설정 완료")

        except Exception as e:
            logger.error(f"WebDriver 설정 실패: {e}")
            # 백업 방법으로 기본 Chrome 사용
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 15)

    def close_driver(self):
        """WebDriver 종료"""
        if self.driver:
            self.driver.quit()

    def extract_product_code(self, url: str) -> str:
        """URL에서 상품 코드 추출"""
        try:
            if 'linkCd=' in url:
                return url.split('linkCd=')[1].split('&')[0]
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'

    def safe_find_element_text(self, selectors: List[str]) -> str:
        """안전한 요소 텍스트 추출"""
        for selector in selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = element.text.strip()
                if text:
                    return text
            except:
                continue
        return ""

    def safe_find_elements_text(self, selectors: List[str]) -> List[str]:
        """안전한 여러 요소 텍스트 추출"""
        texts = []
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text and text not in texts:
                        texts.append(text)
            except:
                continue
        return texts

    def extract_premium_with_age(self) -> Dict[str, str]:
        """나이별 보험료 추출"""
        premium_info = {}

        try:
            # 보험료 계산 섹션으로 스크롤
            calc_selectors = [
                '.premium-calculator',
                '.보험료계산',
                '#premium-calc',
                '.calc-section',
                '[class*="calc"]'
            ]

            calc_element_found = False
            for selector in calc_selectors:
                try:
                    calc_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", calc_element)
                    time.sleep(2)
                    calc_element_found = True
                    break
                except:
                    continue

            if not calc_element_found:
                logger.warning("보험료 계산 섹션을 찾을 수 없습니다")

            # 나이 입력 필드 찾기
            age_input_selectors = [
                'input[name*="age"]',
                'input[id*="age"]',
                '.age-input',
                'input[placeholder*="나이"]',
                'input[type="number"]',
                'input[type="text"]'
            ]

            for age in self.test_ages:
                try:
                    age_input_found = False

                    # 나이 입력 시도
                    for input_selector in age_input_selectors:
                        try:
                            age_input = self.driver.find_element(By.CSS_SELECTOR, input_selector)
                            age_input.clear()
                            age_input.send_keys(str(age))
                            age_input_found = True
                            break
                        except:
                            continue

                    if not age_input_found:
                        logger.warning(f"나이 입력 필드를 찾을 수 없습니다: {age}")
                        continue

                    # 계산 버튼 클릭 또는 Enter 키
                    calc_button_selectors = [
                        'button[class*="calc"]',
                        'button[class*="계산"]',
                        '.calc-btn',
                        'input[type="button"]',
                        'button[type="submit"]'
                    ]

                    calc_clicked = False
                    for btn_selector in calc_button_selectors:
                        try:
                            calc_btn = self.driver.find_element(By.CSS_SELECTOR, btn_selector)
                            calc_btn.click()
                            calc_clicked = True
                            break
                        except:
                            continue

                    if not calc_clicked:
                        # Enter 키로 시도
                        try:
                            age_input.send_keys(Keys.RETURN)
                        except:
                            pass

                    time.sleep(3)  # 계산 결과 대기

                    # 결과 추출
                    result_selectors = [
                        '.premium-result',
                        '.calc-result',
                        '.보험료',
                        '.premium-amount',
                        '[class*="premium"]',
                        '[class*="result"]'
                    ]

                    premium_text = self.safe_find_element_text(result_selectors)
                    if premium_text and any(char.isdigit() for char in premium_text):
                        premium_info[f"age_{age}"] = premium_text
                        logger.info(f"나이 {age} 보험료: {premium_text}")

                    time.sleep(1)

                except Exception as e:
                    logger.warning(f"나이 {age} 보험료 계산 중 오류: {e}")
                    continue

        except Exception as e:
            logger.error(f"보험료 추출 중 오류: {e}")

        return premium_info

    def extract_product_info(self, url: str) -> Optional[InsuranceProduct]:
        """단일 상품 정보 추출"""
        try:
            logger.info(f"상품 정보 추출 시작: {url}")

            self.driver.get(url)
            time.sleep(5)  # 페이지 로딩 대기

            # 팝업 처리
            self.handle_popups()

            # 상품명 추출
            name_selectors = [
                'h1.product-title',
                '.product-name',
                'h1',
                '.title',
                '#productName',
                '.product-tit'
            ]
            product_name = self.safe_find_element_text(name_selectors)

            # 상품 설명 추출
            desc_selectors = [
                '.product-description',
                '.product-summary',
                '.description',
                '.summary',
                '.product-cont'
            ]
            description = self.safe_find_element_text(desc_selectors)

            # 특징 추출
            feature_selectors = [
                '.feature-list li',
                '.benefit-list li',
                '.key-point li',
                '.point-list li',
                '[class*="feature"] li',
                '[class*="benefit"] li'
            ]
            key_features = self.safe_find_elements_text(feature_selectors)

            # 보장 내용 추출
            coverage_selectors = [
                'table.coverage-table tr',
                '.coverage-list li',
                '.guarantee-list li',
                '[class*="coverage"] tr',
                '.보장내용 li'
            ]
            coverage_details = self.safe_find_elements_text(coverage_selectors)

            # 보험료 정보 추출
            premium_info = self.extract_premium_with_age()

            # 약관 정보 추출 (간단 버전)
            terms = self.extract_terms()

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
                scraped_at=datetime.now().isoformat(),
                url=url
            )

            logger.info(f"상품 정보 추출 완료: {product.product_name}")
            return product

        except Exception as e:
            logger.error(f"상품 정보 추출 실패 {url}: {e}")
            return None

    def handle_popups(self):
        """팝업 처리"""
        popup_selectors = [
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '.popup-close',
            '.modal-close',
            '#popup_close',
            'button[onclick*="close"]'
        ]

        for selector in popup_selectors:
            try:
                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                element.click()
                time.sleep(1)
                logger.info(f"팝업 닫기: {selector}")
                break
            except:
                continue

    def extract_terms(self) -> str:
        """약관 정보 추출"""
        try:
            terms_selectors = [
                '.terms-button',
                '.약관보기',
                'a[href*="terms"]',
                '.contract-terms'
            ]

            for selector in terms_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    element.click()
                    time.sleep(3)

                    # 약관 내용 추출
                    content_selectors = [
                        '.terms-content',
                        '.contract-content',
                        '.modal-body',
                        '#terms-modal',
                        '.약관내용'
                    ]

                    terms = self.safe_find_element_text(content_selectors)
                    if len(terms) > 100:
                        return terms[:2000] + "..." if len(terms) > 2000 else terms

                except:
                    continue

        except Exception as e:
            logger.warning(f"약관 추출 중 오류: {e}")

        return ""

    def scrape_all_products(self) -> List[InsuranceProduct]:
        """모든 상품 스크래핑"""
        products = []

        try:
            self.setup_driver()

            for i, url in enumerate(self.urls, 1):
                try:
                    logger.info(f"진행률: {i}/{len(self.urls)} - 상품 처리 중...")
                    product = self.extract_product_info(url)

                    if product:
                        products.append(product)
                        logger.info(f"상품 추출 성공: {product.product_name}")
                    else:
                        logger.warning(f"상품 추출 실패: {url}")

                    # 다음 요청 전 대기
                    if i < len(self.urls):
                        time.sleep(3)

                except Exception as e:
                    logger.error(f"URL 처리 중 오류 {url}: {e}")
                    continue

        finally:
            self.close_driver()

        logger.info(f"총 {len(products)}개 상품 정보 추출 완료")
        return products

    def save_to_json(self, products: List[InsuranceProduct]):
        """JSON 저장"""
        filename = f"kb_insurance_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        data = {
            "metadata": {
                "scraped_at": datetime.now().isoformat(),
                "total_products": len(products),
                "scraper_version": "simple_1.0"
            },
            "products": [asdict(product) for product in products]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"JSON 데이터 저장: {filename}")
        return filename

    def save_to_csv(self, products: List[InsuranceProduct]):
        """CSV 저장 (pandas 없이)"""
        filename = f"kb_insurance_products_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        try:
            import csv

            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                # 헤더 작성
                writer.writerow([
                    'Product Code', 'Product Name', 'Description',
                    'Key Features', 'Coverage Details', 'Premium Info',
                    'Terms Length', 'Scraped At', 'URL'
                ])

                # 데이터 작성
                for product in products:
                    writer.writerow([
                        product.product_code,
                        product.product_name,
                        product.description[:200] + '...' if len(product.description) > 200 else product.description,
                        ' | '.join(product.key_features),
                        ' | '.join(product.coverage_details),
                        str(product.premium_info),
                        len(product.terms_conditions),
                        product.scraped_at,
                        product.url
                    ])

            logger.info(f"CSV 데이터 저장: {filename}")
            return filename

        except Exception as e:
            logger.error(f"CSV 저장 실패: {e}")
            return None

def main():
    """메인 실행 함수"""
    try:
        print("KB생명 보험 상품 스크래핑을 시작합니다...")

        scraper = SimpleKBInsuranceScraper()

        # 스크래핑 실행
        products = scraper.scrape_all_products()

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

        else:
            print("추출된 상품 정보가 없습니다.")
            print("로그 파일(kb_scraper.log)을 확인해주세요.")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"실행 중 오류: {e}")
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    main()