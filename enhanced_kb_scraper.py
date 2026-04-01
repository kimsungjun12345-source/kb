"""
KB생명 보험 상품 정보 스크래핑 자동화 시스템 (개선 버전)
설정 파일 기반으로 보험 상품 정보, 약관, 보험료 계산 등을 자동으로 수집
AI 에이전트용 구조화된 데이터 생성
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException

import pandas as pd
from webdriver_manager.chrome import ChromeDriverManager

@dataclass
class InsuranceProduct:
    """보험 상품 정보 데이터 클래스"""
    product_code: str
    product_name: str
    product_type: str
    description: str
    key_features: List[str]
    coverage_details: Dict[str, Any]
    premium_info: Dict[str, Any]
    age_limits: Dict[str, int]
    terms_conditions: str
    benefits: List[str]
    exclusions: List[str]
    scraped_at: str
    url: str
    additional_info: Dict[str, Any]

class EnhancedKBInsuranceScraper:
    """개선된 KB생명 보험 상품 스크래핑 클래스"""

    def __init__(self, config_path: str = "config.json"):
        """
        초기화

        Args:
            config_path: 설정 파일 경로
        """
        self.config = self._load_config(config_path)
        self.driver = None
        self.wait = None
        self._setup_logging()

    def _load_config(self, config_path: str) -> Dict:
        """설정 파일 로드"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"설정 파일을 찾을 수 없습니다: {config_path}")
            return self._default_config()
        except json.JSONDecodeError:
            print(f"설정 파일 형식이 올바르지 않습니다: {config_path}")
            return self._default_config()

    def _default_config(self) -> Dict:
        """기본 설정"""
        return {
            "scraper_settings": {
                "headless": False,
                "window_size": "1920,1080",
                "page_load_timeout": 20,
                "element_wait_timeout": 10,
                "request_delay": 2
            },
            "urls": [
                "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5"
            ],
            "test_ages": [30, 40, 50],
            "selectors": {},
            "output": {
                "json_filename": "kb_insurance_products_{timestamp}.json",
                "excel_filename": "kb_insurance_products_{timestamp}.xlsx",
                "log_filename": "kb_scraper.log"
            }
        }

    def _setup_logging(self):
        """로깅 설정"""
        log_filename = self.config.get("output", {}).get("log_filename", "kb_scraper.log")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filename, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_driver(self):
        """Selenium WebDriver 설정"""
        chrome_options = Options()

        settings = self.config.get("scraper_settings", {})

        if settings.get("headless", False):
            chrome_options.add_argument('--headless')

        window_size = settings.get("window_size", "1920,1080")
        chrome_options.add_argument(f'--window-size={window_size}')

        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

        try:
            service = webdriver.chrome.service.Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception as e:
            self.logger.warning(f"ChromeDriverManager 실패, 기본 경로 시도: {e}")
            self.driver = webdriver.Chrome(options=chrome_options)

        # 자동화 감지 회피
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        timeout = settings.get("element_wait_timeout", 10)
        self.wait = WebDriverWait(self.driver, timeout)

        page_timeout = settings.get("page_load_timeout", 20)
        self.driver.set_page_load_timeout(page_timeout)

    def close_driver(self):
        """WebDriver 종료"""
        if self.driver:
            self.driver.quit()

    def extract_product_info(self, url: str) -> Optional[InsuranceProduct]:
        """
        단일 보험 상품 정보 추출

        Args:
            url: 상품 페이지 URL

        Returns:
            InsuranceProduct 객체 또는 None
        """
        try:
            self.logger.info(f"상품 정보 추출 시작: {url}")

            self.driver.get(url)

            # 페이지 로딩 대기
            delay = self.config.get("scraper_settings", {}).get("request_delay", 2)
            time.sleep(delay)

            # 팝업 또는 쿠키 배너 처리
            self._handle_popups()

            # 기본 상품 정보 추출
            product_info = self._extract_basic_info()

            # 보장 내용 추출
            coverage_info = self._extract_coverage_info()

            # 약관 정보 추출
            terms_info = self._extract_terms_info()

            # 보험료 정보 추출 (나이 입력 포함)
            premium_info = self._extract_premium_info_with_age()

            # 추가 정보 추출
            additional_info = self._extract_additional_info()

            # 상품 코드 추출 (URL에서)
            product_code = self._extract_product_code(url)

            product = InsuranceProduct(
                product_code=product_code,
                product_name=product_info.get('name', ''),
                product_type=product_info.get('type', ''),
                description=product_info.get('description', ''),
                key_features=product_info.get('features', []),
                coverage_details=coverage_info,
                premium_info=premium_info,
                age_limits=product_info.get('age_limits', {}),
                terms_conditions=terms_info,
                benefits=product_info.get('benefits', []),
                exclusions=product_info.get('exclusions', []),
                scraped_at=datetime.now().isoformat(),
                url=url,
                additional_info=additional_info
            )

            self.logger.info(f"상품 정보 추출 완료: {product.product_name}")
            return product

        except Exception as e:
            self.logger.error(f"상품 정보 추출 실패 {url}: {str(e)}")
            return None

    def _handle_popups(self):
        """팝업 및 쿠키 배너 처리"""
        popup_selectors = [
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '[class*="cookie"] [class*="accept"]',
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
                self.logger.info(f"팝업 닫기 성공: {selector}")
            except:
                continue

    def _extract_product_code(self, url: str) -> str:
        """URL에서 상품 코드 추출"""
        try:
            if 'linkCd=' in url:
                return url.split('linkCd=')[1].split('&')[0]
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'

    def _extract_basic_info(self) -> Dict[str, Any]:
        """기본 상품 정보 추출"""
        info = {
            'name': '',
            'type': '',
            'description': '',
            'features': [],
            'benefits': [],
            'exclusions': [],
            'age_limits': {}
        }

        try:
            # 설정에서 셀렉터 가져오기
            selectors = self.config.get("selectors", {})

            # 상품명 추출
            name_selectors = selectors.get("product_name", [
                'h1.product-title', '.product-name', 'h1', '.title', '#productName'
            ])

            for selector in name_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text.strip():
                        info['name'] = element.text.strip()
                        break
                except:
                    continue

            # 상품 설명 추출
            desc_selectors = selectors.get("product_description", [
                '.product-description', '.product-summary', '.description', '.summary'
            ])

            for selector in desc_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if element.text.strip():
                        info['description'] = element.text.strip()
                        break
                except:
                    continue

            # 특징 및 혜택 추출
            feature_selectors = [
                '.feature-list li',
                '.benefit-list li',
                '.key-point li',
                '.point-list li',
                '[class*="feature"] li',
                '[class*="benefit"] li'
            ]

            for selector in feature_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    features = [elem.text.strip() for elem in elements if elem.text.strip()]
                    if features:
                        info['features'].extend(features)
                except:
                    continue

            # 나이 제한 정보 추출
            self._extract_age_limits(info)

        except Exception as e:
            self.logger.error(f"기본 정보 추출 중 오류: {str(e)}")

        return info

    def _extract_age_limits(self, info: Dict[str, Any]):
        """나이 제한 정보 추출"""
        try:
            # 나이 제한 관련 텍스트 찾기
            age_text_selectors = [
                '[class*="age"]',
                '[class*="limit"]',
                '.condition',
                '.가입조건'
            ]

            for selector in age_text_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if any(keyword in text for keyword in ['나이', '세', '연령']):
                            # 나이 범위 파싱 로직
                            import re
                            age_pattern = r'(\d+)세\s*~\s*(\d+)세'
                            matches = re.findall(age_pattern, text)
                            if matches:
                                min_age, max_age = matches[0]
                                info['age_limits'] = {
                                    'min_age': int(min_age),
                                    'max_age': int(max_age)
                                }
                                break
                except:
                    continue
        except Exception as e:
            self.logger.warning(f"나이 제한 추출 중 오류: {str(e)}")

    def _extract_coverage_info(self) -> Dict[str, Any]:
        """보장 내용 정보 추출"""
        coverage = {
            'coverage_types': [],
            'coverage_amounts': {},
            'coverage_periods': [],
            'special_clauses': []
        }

        try:
            # 보장내용 탭 클릭 시도
            coverage_tab_selectors = [
                '[data-tab="coverage"]',
                '.coverage-tab',
                '.guarantee-tab',
                'a[href*="coverage"]',
                'button[onclick*="coverage"]'
            ]

            for selector in coverage_tab_selectors:
                try:
                    element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    element.click()
                    time.sleep(2)
                    break
                except:
                    continue

            # 보장 테이블 또는 리스트 추출
            coverage_content_selectors = [
                'table.coverage-table tr',
                '.coverage-list li',
                '.guarantee-list li',
                '[class*="coverage"] tr'
            ]

            for selector in coverage_content_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text and len(text) > 5:  # 의미있는 텍스트만
                            coverage['coverage_types'].append(text)

                    if coverage['coverage_types']:
                        break
                except:
                    continue

        except Exception as e:
            self.logger.error(f"보장 내용 추출 중 오류: {str(e)}")

        return coverage

    def _extract_terms_info(self) -> str:
        """약관 정보 추출"""
        terms = ""

        try:
            # 설정에서 약관 버튼 셀렉터 가져오기
            selectors = self.config.get("selectors", {})
            terms_selectors = selectors.get("terms_button", [
                '.terms-button', '.약관보기', 'a[href*="terms"]', '.contract-terms'
            ])

            for selector in terms_selectors:
                try:
                    element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))

                    # 새 탭에서 열리는 경우를 위해 현재 탭 저장
                    current_window = self.driver.current_window_handle

                    element.click()
                    time.sleep(3)

                    # 새 탭이 열렸는지 확인
                    if len(self.driver.window_handles) > 1:
                        # 새 탭으로 전환
                        for handle in self.driver.window_handles:
                            if handle != current_window:
                                self.driver.switch_to.window(handle)
                                break

                    # 약관 내용 추출
                    terms_content_selectors = [
                        '.terms-content',
                        '.contract-content',
                        '.modal-body',
                        '#terms-modal',
                        '.약관내용',
                        'pre',
                        '.content'
                    ]

                    for content_selector in terms_content_selectors:
                        try:
                            content_element = self.driver.find_element(By.CSS_SELECTOR, content_selector)
                            terms = content_element.text.strip()
                            if len(terms) > 100:  # 충분한 내용이 있는 경우만
                                break
                        except:
                            continue

                    # 새 탭이 열렸다면 다시 원래 탭으로
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(current_window)

                    if terms:
                        break

                except TimeoutException:
                    continue
                except Exception as e:
                    self.logger.warning(f"약관 추출 중 오류 {selector}: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"약관 정보 추출 중 오류: {str(e)}")

        return terms[:5000] if terms else ""  # 너무 긴 약관은 일부만 저장

    def _extract_premium_info_with_age(self) -> Dict[str, Any]:
        """나이 입력을 통한 보험료 정보 추출"""
        premium_info = {
            'age_based_premiums': {},
            'premium_calculation_method': '',
            'payment_periods': [],
            'discount_info': []
        }

        try:
            # 설정에서 테스트할 나이들 가져오기
            test_ages = self.config.get("test_ages", [30, 40, 50])
            selectors = self.config.get("selectors", {})

            # 보험료 계산 섹션 찾기
            calc_section_selectors = [
                '.premium-calculator',
                '.보험료계산',
                '#premium-calc',
                '.calc-section',
                '[class*="calc"]'
            ]

            calc_section_found = False
            for selector in calc_section_selectors:
                try:
                    calc_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", calc_element)
                    time.sleep(2)
                    calc_section_found = True
                    break
                except:
                    continue

            if not calc_section_found:
                self.logger.warning("보험료 계산 섹션을 찾을 수 없습니다")
                return premium_info

            # 나이 입력 및 보험료 계산
            age_input_selectors = selectors.get("age_input", [
                'input[name*="age"]',
                'input[id*="age"]',
                '.age-input',
                'input[placeholder*="나이"]'
            ])

            calc_button_selectors = selectors.get("calc_button", [
                'button[class*="calc"]',
                'button[class*="계산"]',
                '.calc-btn',
                'input[type="button"][value*="계산"]'
            ])

            premium_result_selectors = selectors.get("premium_result", [
                '.premium-result',
                '.calc-result',
                '.보험료',
                '.premium-amount'
            ])

            for age in test_ages:
                try:
                    age_input_found = False

                    # 나이 입력 필드 찾기
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
                        self.logger.warning(f"나이 입력 필드를 찾을 수 없습니다: {age}")
                        continue

                    # 계산 버튼 클릭
                    calc_button_clicked = False
                    for btn_selector in calc_button_selectors:
                        try:
                            calc_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, btn_selector)))
                            calc_btn.click()
                            calc_button_clicked = True
                            time.sleep(3)
                            break
                        except:
                            continue

                    if not calc_button_clicked:
                        # Enter 키로 시도
                        try:
                            age_input.send_keys(Keys.RETURN)
                            time.sleep(3)
                        except:
                            continue

                    # 보험료 결과 추출
                    for result_selector in premium_result_selectors:
                        try:
                            result_element = self.driver.find_element(By.CSS_SELECTOR, result_selector)
                            premium_text = result_element.text.strip()
                            if premium_text and any(char.isdigit() for char in premium_text):
                                premium_info['age_based_premiums'][str(age)] = premium_text
                                self.logger.info(f"나이 {age} 보험료: {premium_text}")
                                break
                        except:
                            continue

                    time.sleep(1)  # 다음 계산 전 대기

                except Exception as e:
                    self.logger.warning(f"나이 {age} 보험료 계산 중 오류: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"보험료 정보 추출 중 오류: {str(e)}")

        return premium_info

    def _extract_additional_info(self) -> Dict[str, Any]:
        """추가 정보 추출"""
        additional = {
            'contact_info': '',
            'branch_info': [],
            'online_services': [],
            'mobile_app_info': '',
            'customer_reviews': []
        }

        try:
            # 연락처 정보
            contact_selectors = [
                '.contact-info',
                '.phone-number',
                '[href^="tel:"]'
            ]

            for selector in contact_selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    additional['contact_info'] = element.text.strip()
                    break
                except:
                    continue

            # 온라인 서비스 정보
            service_selectors = [
                '.online-service',
                '.digital-service',
                '[class*="service"] li'
            ]

            for selector in service_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    services = [elem.text.strip() for elem in elements if elem.text.strip()]
                    additional['online_services'].extend(services)
                except:
                    continue

        except Exception as e:
            self.logger.warning(f"추가 정보 추출 중 오류: {str(e)}")

        return additional

    def scrape_all_products(self) -> List[InsuranceProduct]:
        """모든 보험 상품 정보 스크래핑"""
        products = []

        try:
            self.setup_driver()
            urls = self.config.get("urls", [])

            for i, url in enumerate(urls, 1):
                try:
                    self.logger.info(f"진행률: {i}/{len(urls)} - {url}")
                    product = self.extract_product_info(url)
                    if product:
                        products.append(product)

                    # 요청 간 간격
                    delay = self.config.get("scraper_settings", {}).get("request_delay", 2)
                    if i < len(urls):  # 마지막이 아닌 경우만
                        time.sleep(delay)

                except Exception as e:
                    self.logger.error(f"URL {url} 처리 중 오류: {str(e)}")
                    continue

        finally:
            self.close_driver()

        self.logger.info(f"총 {len(products)}개 상품 정보 추출 완료")
        return products

    def save_to_json(self, products: List[InsuranceProduct], filename: str = None):
        """JSON 파일로 저장"""
        if not filename:
            template = self.config.get("output", {}).get("json_filename", "kb_insurance_products_{timestamp}.json")
            filename = template.format(timestamp=datetime.now().strftime('%Y%m%d_%H%M%S'))

        products_data = [asdict(product) for product in products]

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(products_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"데이터가 {filename}에 저장되었습니다.")

    def save_to_excel(self, products: List[InsuranceProduct], filename: str = None):
        """Excel 파일로 저장"""
        if not filename:
            template = self.config.get("output", {}).get("excel_filename", "kb_insurance_products_{timestamp}.xlsx")
            filename = template.format(timestamp=datetime.now().strftime('%Y%m%d_%H%M%S'))

        try:
            # 기본 정보용 데이터프레임
            basic_data = []
            for product in products:
                basic_data.append({
                    'Product Code': product.product_code,
                    'Product Name': product.product_name,
                    'Product Type': product.product_type,
                    'Description': product.description[:500] + '...' if len(product.description) > 500 else product.description,
                    'Key Features': ' | '.join(product.key_features),
                    'Benefits': ' | '.join(product.benefits),
                    'Age Min': product.age_limits.get('min_age', ''),
                    'Age Max': product.age_limits.get('max_age', ''),
                    'Coverage Types': ' | '.join(product.coverage_details.get('coverage_types', [])),
                    'Contact Info': product.additional_info.get('contact_info', ''),
                    'Scraped At': product.scraped_at,
                    'URL': product.url
                })

            df_basic = pd.DataFrame(basic_data)

            # 나이별 보험료 데이터프레임
            premium_data = []
            for product in products:
                for age, premium in product.premium_info.get('age_based_premiums', {}).items():
                    premium_data.append({
                        'Product Code': product.product_code,
                        'Product Name': product.product_name,
                        'Age': age,
                        'Premium': premium
                    })

            df_premium = pd.DataFrame(premium_data)

            # 보장 내용 데이터프레임
            coverage_data = []
            for product in products:
                for i, coverage_type in enumerate(product.coverage_details.get('coverage_types', [])):
                    coverage_data.append({
                        'Product Code': product.product_code,
                        'Product Name': product.product_name,
                        'Coverage Type': coverage_type
                    })

            df_coverage = pd.DataFrame(coverage_data)

            # Excel 파일에 여러 시트로 저장
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df_basic.to_excel(writer, sheet_name='Products', index=False)
                if not df_premium.empty:
                    df_premium.to_excel(writer, sheet_name='Premiums', index=False)
                if not df_coverage.empty:
                    df_coverage.to_excel(writer, sheet_name='Coverage', index=False)

            self.logger.info(f"Excel 데이터가 {filename}에 저장되었습니다.")

        except Exception as e:
            self.logger.error(f"Excel 저장 중 오류: {str(e)}")

    def generate_ai_agent_data(self, products: List[InsuranceProduct]) -> Dict[str, Any]:
        """AI 에이전트용 구조화된 데이터 생성"""
        ai_data = {
            "metadata": {
                "scraped_at": datetime.now().isoformat(),
                "total_products": len(products),
                "data_version": "1.0"
            },
            "products": {},
            "age_premium_matrix": {},
            "coverage_mapping": {},
            "terms_summary": {}
        }

        for product in products:
            product_code = product.product_code

            # 상품별 구조화된 데이터
            ai_data["products"][product_code] = {
                "name": product.product_name,
                "description": product.description,
                "key_features": product.key_features,
                "age_limits": product.age_limits,
                "benefits": product.benefits,
                "contact_info": product.additional_info.get('contact_info', ''),
                "url": product.url
            }

            # 나이-보험료 매트릭스
            if product.premium_info.get('age_based_premiums'):
                ai_data["age_premium_matrix"][product_code] = product.premium_info['age_based_premiums']

            # 보장 내용 매핑
            ai_data["coverage_mapping"][product_code] = product.coverage_details.get('coverage_types', [])

            # 약관 요약 (첫 500자)
            if product.terms_conditions:
                ai_data["terms_summary"][product_code] = product.terms_conditions[:500] + "..."

        return ai_data

def main():
    """메인 실행 함수"""
    try:
        scraper = EnhancedKBInsuranceScraper()

        print("🚀 KB생명 보험 상품 스크래핑을 시작합니다...")
        print(f"📋 총 {len(scraper.config.get('urls', []))}개 상품 URL 처리 예정")

        # 모든 상품 정보 스크래핑
        products = scraper.scrape_all_products()

        if products:
            print(f"✅ 총 {len(products)}개의 보험 상품 정보가 성공적으로 추출되었습니다.\n")

            # JSON 형태로 저장
            scraper.save_to_json(products)

            # Excel 형태로 저장
            scraper.save_to_excel(products)

            # AI 에이전트용 데이터 생성
            ai_data = scraper.generate_ai_agent_data(products)
            ai_filename = f"ai_agent_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(ai_filename, 'w', encoding='utf-8') as f:
                json.dump(ai_data, f, ensure_ascii=False, indent=2)
            print(f"🤖 AI 에이전트용 데이터: {ai_filename}")

            # 추출된 데이터 요약 출력
            print("\n📊 추출 결과 요약:")
            for product in products:
                print(f"  📋 {product.product_name} ({product.product_code})")
                print(f"     - 특징: {len(product.key_features)}개")
                print(f"     - 보장: {len(product.coverage_details.get('coverage_types', []))}개")
                print(f"     - 나이별 보험료: {len(product.premium_info.get('age_based_premiums', {}))}개")
                print(f"     - 약관 길이: {len(product.terms_conditions)}자")
        else:
            print("❌ 추출된 상품 정보가 없습니다.")
            print("설정을 확인하거나 웹사이트 구조 변경을 확인해주세요.")

    except KeyboardInterrupt:
        print("\n⏹️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"❌ 실행 중 오류가 발생했습니다: {str(e)}")
        logging.error(f"메인 실행 중 오류: {str(e)}")

if __name__ == "__main__":
    main()