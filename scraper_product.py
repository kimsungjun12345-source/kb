"""
KB 딱좋은 e-건강보험 상품 보장내용 스크래퍼
주계약 보장내용, 선택 특약, 가입 조건을 수집하여 JSON으로 저장
"""

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime

class KBHealthInsuranceProductScraper:
    """KB 딱좋은 e-건강보험 상품 보장내용 스크래퍼"""

    def __init__(self):
        self.target_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.output_dir = Path("./outputs")
        self.output_dir.mkdir(exist_ok=True)

        # 수집할 데이터 구조
        self.product_data = {
            "product_info": {
                "name": "",
                "code": "",
                "type": "",
                "collected_at": datetime.now().isoformat()
            },
            "main_coverage": [],      # 주계약 보장내용
            "optional_riders": [],    # 선택 특약
            "subscription_conditions": {  # 가입 조건
                "age_range": "",
                "payment_period": [],
                "insurance_period": [],
                "coverage_amounts": []
            }
        }

    def setup_browser(self):
        """브라우저 설정"""
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=False,
            slow_mo=300,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        print("브라우저 설정 완료")

    def navigate_to_product_page(self):
        """상품 페이지로 이동"""
        print(f"상품 페이지 이동: {self.target_url}")

        try:
            self.page.goto(self.target_url, wait_until='networkidle', timeout=30000)
            self.page.wait_for_timeout(3000)

            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            # 상품명 추출
            product_name = self.extract_product_name()
            self.product_data["product_info"]["name"] = product_name

            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def extract_product_name(self):
        """상품명 추출"""
        try:
            # 다양한 상품명 선택자 시도
            name_selectors = [
                'h1', 'h2', '.product-title', '.title',
                '[class*="product"]', '[class*="title"]'
            ]

            for selector in name_selectors:
                try:
                    element = self.page.query_selector(selector)
                    if element and element.is_visible():
                        text = element.inner_text().strip()
                        if "건강보험" in text or "e-건강" in text:
                            print(f"상품명 발견: {text}")
                            return text
                except:
                    continue

            # 페이지 타이틀에서 추출
            title = self.page.title()
            if "건강보험" in title:
                return title.split(" > ")[0]  # 첫 번째 부분만

            return "KB 딱좋은 e-건강보험"

        except Exception as e:
            print(f"상품명 추출 실패: {e}")
            return "KB 딱좋은 e-건강보험"

    def extract_main_coverage(self):
        """주계약 보장내용 추출"""
        print("\n주계약 보장내용 추출 중...")

        try:
            # 보장내용 섹션 찾기
            coverage_selectors = [
                '[class*="coverage"]', '[class*="guarantee"]',
                '[class*="benefit"]', '[class*="보장"]',
                'table', '.table', '[role="table"]'
            ]

            main_coverage = []

            for selector in coverage_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if not element.is_visible():
                            continue

                        text = element.inner_text().strip()

                        # 보장내용 관련 키워드가 있는지 확인
                        coverage_keywords = ['보장', '급여', '지급', '보험금', '진단', '수술', '입원']
                        if any(keyword in text for keyword in coverage_keywords):
                            # 테이블 구조인지 확인
                            if element.tag_name().lower() == 'table':
                                coverage_data = self.parse_coverage_table(element)
                                main_coverage.extend(coverage_data)
                            else:
                                # 일반 텍스트에서 보장내용 추출
                                coverage_items = self.parse_coverage_text(text)
                                main_coverage.extend(coverage_items)

                except Exception as e:
                    continue

            # 중복 제거
            unique_coverage = []
            seen_names = set()
            for item in main_coverage:
                if item.get('coverage_name') not in seen_names:
                    unique_coverage.append(item)
                    seen_names.add(item.get('coverage_name'))

            self.product_data["main_coverage"] = unique_coverage[:10]  # 상위 10개만
            print(f"주계약 보장내용 {len(unique_coverage)}개 추출 완료")

        except Exception as e:
            print(f"주계약 보장내용 추출 실패: {e}")

    def parse_coverage_table(self, table_element):
        """테이블에서 보장내용 파싱"""
        coverage_data = []

        try:
            rows = table_element.query_selector_all('tr')
            headers = []

            for i, row in enumerate(rows):
                cells = row.query_selector_all('td, th')

                if i == 0:  # 헤더 행
                    headers = [cell.inner_text().strip() for cell in cells]
                    continue

                if len(cells) >= 2:
                    coverage_item = {
                        'coverage_name': cells[0].inner_text().strip(),
                        'payment_condition': cells[1].inner_text().strip() if len(cells) > 1 else '',
                        'payment_amount': cells[2].inner_text().strip() if len(cells) > 2 else '',
                        'additional_info': cells[3].inner_text().strip() if len(cells) > 3 else ''
                    }
                    coverage_data.append(coverage_item)

        except Exception as e:
            print(f"테이블 파싱 오류: {e}")

        return coverage_data

    def parse_coverage_text(self, text):
        """텍스트에서 보장내용 파싱"""
        coverage_data = []

        try:
            lines = text.split('\n')
            current_coverage = {}

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 보장명 패턴 (일반적으로 첫 번째 또는 굵은 글씨)
                if any(keyword in line for keyword in ['진단', '수술', '입원', '치료', '보장']):
                    if current_coverage:
                        coverage_data.append(current_coverage)

                    current_coverage = {
                        'coverage_name': line,
                        'payment_condition': '',
                        'payment_amount': '',
                        'additional_info': ''
                    }
                elif '원' in line or '%' in line:
                    if current_coverage:
                        if not current_coverage['payment_amount']:
                            current_coverage['payment_amount'] = line
                        else:
                            current_coverage['additional_info'] += ' ' + line
                elif current_coverage:
                    current_coverage['payment_condition'] += ' ' + line

            if current_coverage:
                coverage_data.append(current_coverage)

        except Exception as e:
            print(f"텍스트 파싱 오류: {e}")

        return coverage_data

    def extract_optional_riders(self):
        """선택 특약 추출"""
        print("\n선택 특약 추출 중...")

        try:
            # 특약 섹션 찾기
            rider_selectors = [
                '[class*="rider"]', '[class*="special"]', '[class*="option"]',
                '[class*="특약"]', '.accordion', '.tab-content'
            ]

            optional_riders = []

            # 페이지 스크롤하면서 모든 특약 섹션 로드
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.page.wait_for_timeout(2000)

            for selector in rider_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if not element.is_visible():
                            continue

                        text = element.inner_text().strip()

                        # 특약 관련 키워드 확인
                        if any(keyword in text for keyword in ['특약', '추가', '선택', '옵션']):
                            rider_items = self.parse_rider_text(text)
                            optional_riders.extend(rider_items)

                except Exception as e:
                    continue

            # 중복 제거
            unique_riders = []
            seen_names = set()
            for rider in optional_riders:
                if rider.get('rider_name') not in seen_names:
                    unique_riders.append(rider)
                    seen_names.add(rider.get('rider_name'))

            self.product_data["optional_riders"] = unique_riders
            print(f"선택 특약 {len(unique_riders)}개 추출 완료")

        except Exception as e:
            print(f"선택 특약 추출 실패: {e}")

    def parse_rider_text(self, text):
        """특약 텍스트 파싱"""
        riders = []

        try:
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # 특약명 패턴
                if ('특약' in line or '보장' in line) and len(line) < 100:
                    rider_item = {
                        'rider_name': line,
                        'coverage_summary': '',
                        'premium_info': ''
                    }

                    # 다음 몇 줄에서 요약 정보 찾기
                    rider_lines = text.split(line)
                    if len(rider_lines) > 1:
                        following_text = rider_lines[1][:200]  # 다음 200자
                        if '원' in following_text:
                            rider_item['premium_info'] = following_text.strip()
                        else:
                            rider_item['coverage_summary'] = following_text.strip()

                    riders.append(rider_item)

        except Exception as e:
            print(f"특약 파싱 오류: {e}")

        return riders

    def extract_subscription_conditions(self):
        """가입 조건 추출"""
        print("\n가입 조건 추출 중...")

        try:
            page_text = self.page.content()

            # 가입 나이 추출
            age_patterns = [
                r'가입연령[:\s]*(\d+)세?\s*~\s*(\d+)세?',
                r'(\d+)세\s*~\s*(\d+)세.*가입',
                r'만\s*(\d+)세?\s*~\s*만?\s*(\d+)세?'
            ]

            import re
            age_range = ""
            for pattern in age_patterns:
                match = re.search(pattern, page_text)
                if match:
                    age_range = f"{match.group(1)}세 ~ {match.group(2)}세"
                    break

            # 납입기간 추출
            payment_periods = []
            payment_patterns = [
                r'(\d+년)\s*납입', r'납입기간[:\s]*(\d+년)',
                r'전기납', r'일시납', r'월납'
            ]

            for pattern in payment_patterns:
                matches = re.findall(pattern, page_text)
                payment_periods.extend(matches)

            # 보험기간 추출
            insurance_periods = []
            period_patterns = [
                r'보험기간[:\s]*(\d+년)', r'(\d+년)\s*만기',
                r'(\d+세)\s*만기', r'종신', r'평생'
            ]

            for pattern in period_patterns:
                matches = re.findall(pattern, page_text)
                insurance_periods.extend(matches)

            # 가입금액 추출
            coverage_amounts = []
            amount_patterns = [
                r'(\d+,?\d*만원)', r'(\d+억원)',
                r'가입금액[:\s]*(\d+[만억]?원)'
            ]

            for pattern in amount_patterns:
                matches = re.findall(pattern, page_text)
                coverage_amounts.extend(matches)

            self.product_data["subscription_conditions"] = {
                "age_range": age_range,
                "payment_period": list(set(payment_periods)),
                "insurance_period": list(set(insurance_periods)),
                "coverage_amounts": list(set(coverage_amounts))[:10]
            }

            print(f"가입 조건 추출 완료: 가입연령 {age_range}")

        except Exception as e:
            print(f"가입 조건 추출 실패: {e}")

    def save_product_data(self):
        """상품 데이터 JSON 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.output_dir / f'product_coverage_{timestamp}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.product_data, f, ensure_ascii=False, indent=2)

        print(f"\n상품 데이터 저장 완료: {filename}")
        return filename

    def print_summary(self):
        """수집 결과 요약 출력"""
        print("\n" + "="*60)
        print("KB 딱좋은 e-건강보험 상품 정보 수집 결과")
        print("="*60)

        product_info = self.product_data["product_info"]
        print(f"상품명: {product_info['name']}")

        main_coverage = self.product_data["main_coverage"]
        print(f"주계약 보장: {len(main_coverage)}개")
        for i, coverage in enumerate(main_coverage[:3], 1):
            print(f"  {i}. {coverage.get('coverage_name', '')}")

        optional_riders = self.product_data["optional_riders"]
        print(f"선택 특약: {len(optional_riders)}개")
        for i, rider in enumerate(optional_riders[:3], 1):
            print(f"  {i}. {rider.get('rider_name', '')}")

        conditions = self.product_data["subscription_conditions"]
        print(f"가입 조건:")
        print(f"  - 가입연령: {conditions.get('age_range', '정보 없음')}")
        print(f"  - 납입기간: {', '.join(conditions.get('payment_period', []))}")
        print(f"  - 보험기간: {', '.join(conditions.get('insurance_period', []))}")

    def run_scraper(self):
        """메인 스크래핑 실행"""
        print("KB 딱좋은 e-건강보험 상품 보장내용 스크래퍼 시작")
        print("="*60)

        try:
            # 1. 브라우저 설정
            self.setup_browser()

            # 2. 상품 페이지 이동
            if not self.navigate_to_product_page():
                return

            # 3. 주계약 보장내용 추출
            self.extract_main_coverage()

            # 4. 선택 특약 추출
            self.extract_optional_riders()

            # 5. 가입 조건 추출
            self.extract_subscription_conditions()

            # 6. 데이터 저장
            saved_file = self.save_product_data()

            # 7. 결과 요약
            self.print_summary()

            print(f"\n상세 데이터: {saved_file}")

        except Exception as e:
            print(f"스크래퍼 실행 중 오류: {e}")

        finally:
            try:
                if hasattr(self, 'context'):
                    self.context.close()
                if hasattr(self, 'browser'):
                    self.browser.close()
                if hasattr(self, 'playwright'):
                    self.playwright.stop()
                print("\n브라우저 종료 완료")
            except:
                pass

def main():
    """메인 함수"""
    scraper = KBHealthInsuranceProductScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()