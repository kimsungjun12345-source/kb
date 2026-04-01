"""
KB생명 보험기간/납입기간별 가격 변화 데이터 수집기 - 대기시간 수정됨
다양한 나이대(20~65세)에서 보험기간/납입기간 조합별 가격 변화 수집
"""

import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


class KBWaitFixedCollector:
    """KB생명 보험기간/납입기간별 가격 수집기 - 충분한 대기시간"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

        # 테스트 나이 범위 (3개만 테스트)
        self.test_ages = [30, 35]
        self.genders = [
            {"value": "male", "text": "남자", "korean": "남자"},
            {"value": "female", "text": "여자", "korean": "여자"}
        ]

        # 전체 보험기간/납입기간 조합 - 실제 사이트에서 확인된 옵션들
        self.period_combinations = [
            {"insurance": "정기 10년", "payment": "납입 10년", "insurance_value": "10", "payment_value": "10"},
            {"insurance": "종신", "payment": "납입 20년", "insurance_value": "99", "payment_value": "20"}
        ]

        # URL
        self.url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

        # 데이터 저장
        self.collected_data = []
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)

    def setup_browser(self):
        """브라우저 설정"""
        playwright = sync_playwright().start()

        self.browser = playwright.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        self.page = self.context.new_page()
        self.page.set_default_timeout(30000)

    def dismiss_blocking_modal(self):
        """강화된 블로킹 모달 제거"""
        try:
            # JavaScript로 모든 블로킹 요소 제거
            self.page.evaluate("""
                // 모든 모달과 오버레이 요소 제거
                document.querySelectorAll('.modal-overlay, .modal.open, .alert.open, .fade').forEach(el => {
                    el.style.display = 'none';
                    el.remove();
                });

                // systemAlert1 요소 특별 처리
                const systemAlert = document.getElementById('systemAlert1');
                if (systemAlert) {
                    systemAlert.style.display = 'none';
                    systemAlert.remove();
                }

                // 모든 z-index 높은 요소들 숨기기
                document.querySelectorAll('[style*="z-index"]').forEach(el => {
                    const zIndex = parseInt(el.style.zIndex);
                    if (zIndex > 1000) {
                        el.style.display = 'none';
                    }
                });
            """)

            # 버튼 클릭으로 정상적으로 닫기 시도
            button_texts = ["확인", "동의", "계속", "닫기", "예", "취소"]

            for text in button_texts:
                try:
                    btn = self.page.locator(f'button:has-text("{text}")').first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=500, force=True)
                        self.page.wait_for_timeout(200)
                        print(f"  모달 버튼 클릭: {text}")
                        break
                except Exception:
                    continue

            # ESC 키로 모달 닫기
            try:
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
            except Exception:
                pass

        except Exception as e:
            print(f"  모달 제거 시도 중 오류: {e}")
            pass

    def safe_click(self, element, description="요소"):
        """안전한 클릭 (모달 제거 + force 클릭)"""
        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                print(f"  {description} 클릭 시도 {attempt + 1}/{max_attempts}")

                # 강력한 모달 제거
                self.dismiss_blocking_modal()
                self.page.wait_for_timeout(500)

                # JavaScript로 직접 클릭 시도
                try:
                    if hasattr(element, 'click'):
                        element.click(timeout=3000, force=True)
                    else:
                        # query_selector로 얻은 경우
                        self.page.evaluate("(element) => element.click()", element)

                    print(f"  {description} 클릭 성공")
                    self.page.wait_for_timeout(500)
                    return True

                except Exception as e:
                    print(f"  {description} 클릭 실패: {e}")
                    if attempt < max_attempts - 1:
                        self.page.wait_for_timeout(1000)
                    continue

            except Exception as e:
                print(f"  {description} 클릭 중 오류: {e}")
                if attempt < max_attempts - 1:
                    self.page.wait_for_timeout(1000)

        print(f"  {description} 클릭 최종 실패")
        return False

    def find_input_fields(self):
        """입력 필드들 찾기"""
        fields = {}
        try:
            # 생년월일 입력 필드
            birthdate_selectors = [
                'input[placeholder*="생년월일"]',
                'input[name*="birth"]',
                'input[name*="Birth"]',
                'input[id*="birth"]'
            ]

            for selector in birthdate_selectors:
                element = self.page.query_selector(selector)
                if element:
                    fields["birthdate"] = element
                    print("생년월일 필드 발견: " + selector)
                    break

            # 성별 선택
            gender_selectors = [
                'input[type="radio"][value="male"]',
                'input[type="radio"][value="M"]',
                'input[name*="gender"]'
            ]

            male_radio = None
            female_radio = None

            for selector in gender_selectors:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    value = element.get_attribute('value') or ""
                    if value.lower() in ['male', 'm']:
                        male_radio = element
                    elif value.lower() in ['female', 'f']:
                        female_radio = element

            if male_radio and female_radio:
                fields["gender_male"] = male_radio
                fields["gender_female"] = female_radio
                print("성별 선택 필드 발견")

            # 보험기간/납입기간 셀렉트 박스
            selects = self.page.query_selector_all('select')
            for select in selects:
                parent = select.query_selector('xpath=..')
                if parent:
                    parent_text = parent.inner_text()
                    if "보험기간" in parent_text:
                        fields["insurance_period"] = select
                        print("보험기간 선택 필드 발견")
                    elif "납입기간" in parent_text or "납입" in parent_text:
                        fields["payment_period"] = select
                        print("납입기간 선택 필드 발견")

            # 계산 버튼
            calc_selectors = [
                'button:has-text("계산")',
                'input[value*="계산"]',
                'button[onclick*="calc"]'
            ]

            for selector in calc_selectors:
                element = self.page.query_selector(selector)
                if element:
                    fields["calc_button"] = element
                    print("계산 버튼 발견: " + selector)
                    break

            return fields

        except Exception as e:
            print(f"필드 찾기 실패: {e}")
            return {}

    def set_period_combination(self, fields, combination):
        """보험기간/납입기간 조합 설정 - 개선된 방식"""
        try:
            print(f"  기간 조합 설정: {combination['insurance']}/{combination['payment']}")

            # 보험기간 설정 - JavaScript로 직접 설정
            if "insurance_period" in fields:
                insurance_select = fields["insurance_period"]
                success = self.page.evaluate(f"""
                    (select) => {{
                        const targetValue = "{combination['insurance_value']}";
                        const targetText = "{combination['insurance']}";

                        // 먼저 값으로 찾기
                        for (let option of select.options) {{
                            if (option.value === targetValue || option.text.includes(targetText.replace('정기 ', '').replace('년', ''))) {{
                                select.value = option.value;
                                select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                console.log('보험기간 설정됨:', option.text);
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """, insurance_select)

                if success:
                    print(f"  보험기간 설정 성공: {combination['insurance']}")
                else:
                    print(f"  보험기간 설정 실패: {combination['insurance']}")

            self.page.wait_for_timeout(1000)

            # 납입기간 설정 - JavaScript로 직접 설정
            if "payment_period" in fields:
                payment_select = fields["payment_period"]
                success = self.page.evaluate(f"""
                    (select) => {{
                        const targetValue = "{combination['payment_value']}";
                        const targetText = "{combination['payment']}";

                        for (let option of select.options) {{
                            if (option.value === targetValue || option.text.includes(targetText.replace('납입 ', '').replace('년', ''))) {{
                                select.value = option.value;
                                select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                console.log('납입기간 설정됨:', option.text);
                                return true;
                            }}
                        }}
                        return false;
                    }}
                """, payment_select)

                if success:
                    print(f"  납입기간 설정 성공: {combination['payment']}")
                else:
                    print(f"  납입기간 설정 실패: {combination['payment']}")

            self.page.wait_for_timeout(1000)
            return True

        except Exception as e:
            print(f"기간 조합 설정 실패: {e}")
            return False

    def wait_for_calculation_result(self):
        """보험료 계산 완료까지 대기"""
        print("  보험료 계산 중... 결과 대기")

        # 기본 대기 시간 (최소 10초)
        self.page.wait_for_timeout(10000)

        # 계산이 완료될 때까지 추가 확인 (최대 30초)
        for wait_attempt in range(10):
            try:
                # 보험료 결과가 나타났는지 확인
                body_text = self.page.inner_text('body')

                # 보험료 관련 텍스트가 있는지 확인
                price_indicators = ["원/월", "월보험료", "보험료", "계산결과", "예상보험료"]
                if any(indicator in body_text for indicator in price_indicators):
                    print(f"  계산 완료 확인됨 (대기 시도 {wait_attempt + 1})")
                    break
                else:
                    print(f"  결과 대기 중... (시도 {wait_attempt + 1}/10)")
                    self.page.wait_for_timeout(3000)
            except Exception:
                self.page.wait_for_timeout(3000)

        # 추가 안전 대기
        self.page.wait_for_timeout(2000)

    def extract_price_data(self):
        """보험료 가격 추출"""
        try:
            details = {}

            # 페이지 텍스트에서 가격 정보 추출
            body_text = self.page.inner_text('body')

            # 월 보험료 추출 - 더 다양한 패턴
            price_patterns = [
                r"월\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"월보험료\s*[:：]\s*([\d,]+)\s*원",
                r"보험료\s*[:：]\s*([\d,]+)\s*원",
                r"([\d,]+)\s*원/월",
                r"월\s*([\d,]+)\s*원",
                r"예상\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"계산\s*결과\s*[:：]\s*([\d,]+)\s*원"
            ]

            monthly_premium = 0
            for pattern in price_patterns:
                match = re.search(pattern, body_text)
                if match:
                    price_str = match.group(1).replace(',', '')
                    monthly_premium = int(price_str)
                    details["monthly_premium"] = monthly_premium
                    print(f"  가격 추출 성공: {monthly_premium:,}원")
                    break

            # 보험기간/납입기간 정보 확인
            period_info = {}

            insurance_match = re.search(r"보험기간\s*[:：]\s*([^\n]+)", body_text)
            if insurance_match:
                period_info["insurance_period"] = insurance_match.group(1).strip()

            payment_match = re.search(r"납입기간\s*[:：]\s*([^\n]+)", body_text)
            if payment_match:
                period_info["payment_period"] = payment_match.group(1).strip()

            details["period_info"] = period_info

            # 기본값 설정
            if "monthly_premium" not in details:
                details["monthly_premium"] = 0
                print("  가격 추출 실패 - 0원으로 설정")

            return details

        except Exception as e:
            print(f"데이터 추출 실패: {e}")
            return {"monthly_premium": 0, "period_info": {}}

    def collect_period_data(self):
        """보험기간/납입기간별 데이터 수집"""
        print(f"\n보험기간/납입기간별 데이터 수집 시작")
        print(f"대상: {len(self.test_ages)}개 나이 × {len(self.genders)}개 성별 × {len(self.period_combinations)}개 조합")

        try:
            self.page.goto(self.url, wait_until='networkidle')
            self.page.wait_for_timeout(3000)
            print(f"페이지 로딩 완료: {self.page.title()}")

            # 초기 모달 제거
            self.dismiss_blocking_modal()
            self.page.wait_for_timeout(2000)

            # 입력 필드 찾기
            fields = self.find_input_fields()
            if not fields:
                print("필요한 입력 필드를 찾을 수 없습니다.")
                return False

            total_cases = len(self.test_ages) * len(self.genders) * len(self.period_combinations)
            case_num = 0

            for age in self.test_ages:
                for gender in self.genders:
                    for combination in self.period_combinations:
                        case_num += 1
                        print(f"\n[{case_num}/{total_cases}] {age}세 {gender['korean']} - {combination['insurance']}/{combination['payment']}")

                        try:
                            # 1. 모달 제거
                            self.dismiss_blocking_modal()

                            # 2. 생년월일 입력
                            if "birthdate" in fields:
                                birth_year = 2024 - age
                                birthdate = f"{birth_year}0101"
                                fields["birthdate"].fill(birthdate)
                                print(f"  생년월일 입력: {birthdate}")

                            # 3. 성별 선택
                            gender_field = f"gender_{gender['value']}"
                            if gender_field in fields:
                                self.safe_click(fields[gender_field], f"성별({gender['korean']})")

                            # 4. 보험기간/납입기간 설정
                            if not self.set_period_combination(fields, combination):
                                print("  기간 설정 실패, 다음으로 넘어감")
                                continue

                            # 5. 계산 버튼 클릭
                            if "calc_button" in fields:
                                if self.safe_click(fields["calc_button"], "계산 버튼"):

                                    # 6. 보험료 계산 완료까지 충분히 대기
                                    self.wait_for_calculation_result()

                                    # 7. 결과 추출
                                    result = self.extract_price_data()

                                    data_entry = {
                                        "age": age,
                                        "gender": gender["value"],
                                        "gender_korean": gender["korean"],
                                        "insurance_period": combination["insurance"],
                                        "payment_period": combination["payment"],
                                        "insurance_period_value": combination["insurance_value"],
                                        "payment_period_value": combination["payment_value"],
                                        "monthly_premium": result.get("monthly_premium", 0),
                                        "collected_at": datetime.now().isoformat()
                                    }

                                    self.collected_data.append(data_entry)
                                    print(f"  결과: {data_entry['monthly_premium']:,}원")

                            # 케이스 간 안전 대기
                            self.page.wait_for_timeout(3000)

                        except Exception as e:
                            print(f"  케이스 처리 실패: {e}")
                            continue

            print(f"\n보험기간/납입기간 데이터 수집 완료: {len(self.collected_data)}건")
            return len(self.collected_data) > 0

        except Exception as e:
            print(f"데이터 수집 실패: {e}")
            return False

    def save_results(self):
        """결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON 저장
        json_file = self.output_dir / f'kb_wait_period_data_{timestamp}.json'
        result_data = {
            "collected_at": datetime.now().isoformat(),
            "total_collected": len(self.collected_data),
            "period_price_data": self.collected_data,
            "metadata": {
                "ages": self.test_ages,
                "genders": self.genders,
                "period_combinations": self.period_combinations,
                "url": self.url
            }
        }

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        # CSV 저장
        csv_file = self.output_dir / f'kb_wait_period_data_{timestamp}.csv'

        if self.collected_data:
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'age', 'gender', 'gender_korean',
                    'insurance_period', 'payment_period',
                    'insurance_period_value', 'payment_period_value',
                    'monthly_premium', 'collected_at'
                ])
                writer.writeheader()
                writer.writerows(self.collected_data)

        print(f"결과 저장 완료:")
        print(f"  JSON: {json_file}")
        print(f"  CSV: {csv_file}")

    def print_summary(self):
        """결과 요약 출력"""
        print("\n" + "="*60)
        print("KB생명 보험기간/납입기간별 가격 수집 결과")
        print("="*60)

        if not self.collected_data:
            print("수집된 데이터가 없습니다.")
            return

        # 조합별 통계
        combo_stats = {}
        for data in self.collected_data:
            combo_key = f"{data['insurance_period']}/{data['payment_period']}"
            if combo_key not in combo_stats:
                combo_stats[combo_key] = []
            combo_stats[combo_key].append(data['monthly_premium'])

        for combo, prices in combo_stats.items():
            valid_prices = [p for p in prices if p > 0]
            if valid_prices:
                avg_price = sum(valid_prices) / len(valid_prices)
                print(f"{combo}: 평균 {avg_price:,.0f}원 (유효한 케이스 {len(valid_prices)}개)")

        # 수집된 데이터 샘플
        print("\n최근 수집 데이터:")
        for i, data in enumerate(self.collected_data[-5:], 1):
            print(f"  {i}. {data['age']}세 {data['gender_korean']} - {data['insurance_period']}/{data['payment_period']}: {data['monthly_premium']:,}원")

    def run(self):
        """메인 실행"""
        print("KB생명 보험기간/납입기간별 가격 수집기 시작")
        print("="*60)

        try:
            # 브라우저 설정
            self.setup_browser()
            print("브라우저 설정 완료")

            # 데이터 수집
            success = self.collect_period_data()

            if success:
                # 결과 저장 및 출력
                self.save_results()
                self.print_summary()
            else:
                print("데이터 수집에 실패했습니다.")

        except Exception as e:
            print(f"실행 중 오류 발생: {e}")
        finally:
            # 브라우저 정리
            if self.browser:
                self.browser.close()
                print("\n브라우저 종료 완료")


if __name__ == "__main__":
    collector = KBWaitFixedCollector()
    collector.run()