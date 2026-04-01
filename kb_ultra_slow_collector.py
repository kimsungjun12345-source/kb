"""
KB생명 초저속 안전 수집기 - 차단 방지 최우선
매우 긴 시간 간격과 단일 프로세스로 안전하게 데이터 수집
"""

import csv
import json
import re
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext


class KBUltraSlowCollector:
    """KB생명 초저속 안전 수집기 - 차단 방지"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

        # 소량 테스트 (2개 나이, 1개 조합만)
        self.test_ages = [30, 35]
        self.genders = [
            {"value": "male", "text": "남자", "korean": "남자"},
            {"value": "female", "text": "여자", "korean": "여자"}
        ]

        # 단순한 조합만 테스트
        self.period_combinations = [
            {"insurance": "정기 10년", "payment": "납입 10년", "insurance_value": "10", "payment_value": "10"}
        ]

        # URL
        self.url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

        # 데이터 저장
        self.collected_data = []
        self.output_dir = Path("outputs")
        self.output_dir.mkdir(exist_ok=True)

        # 안전 설정 - 빠른 버전
        self.min_delay = 10  # 최소 10초 대기
        self.max_delay = 15  # 최대 15초 대기
        self.calculation_wait = 10  # 계산 결과 대기 10초

    def random_delay(self, min_sec=None, max_sec=None):
        """랜덤 지연"""
        min_time = min_sec if min_sec is not None else self.min_delay
        max_time = max_sec if max_sec is not None else self.max_delay
        delay = random.uniform(min_time, max_time)
        print(f"  안전 대기: {delay:.1f}초...")
        time.sleep(delay)

    def setup_browser(self):
        """브라우저 설정 - 인간처럼 보이도록"""
        playwright = sync_playwright().start()

        self.browser = playwright.chromium.launch(
            headless=False,
            slow_mo=500,  # 모든 동작을 0.5초씩 지연
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            locale='ko-KR'
        )

        self.page = self.context.new_page()
        self.page.set_default_timeout(120000)  # 2분 타임아웃

    def dismiss_blocking_modal(self):
        """모달 제거 - 안전하게"""
        try:
            # 먼저 확인 버튼들 찾기
            button_texts = ["확인", "동의", "계속", "닫기", "예", "취소"]

            for text in button_texts:
                try:
                    btn = self.page.locator(f'button:has-text("{text}")').first
                    if btn.count() > 0 and btn.is_visible():
                        print(f"  모달 버튼 발견: {text}")
                        btn.click(timeout=2000, force=True)
                        time.sleep(1)
                        print(f"  모달 버튼 클릭: {text}")
                        break
                except Exception:
                    continue

            # JavaScript 정리 (최소한으로)
            try:
                self.page.evaluate("""
                    // 가장 기본적인 모달만 제거
                    const modals = document.querySelectorAll('.modal-overlay, #systemAlert1');
                    modals.forEach(modal => {
                        if (modal) {
                            modal.style.display = 'none';
                        }
                    });
                """)
            except Exception:
                pass

        except Exception as e:
            print(f"  모달 제거 시도 중 오류: {e}")

    def find_input_fields(self):
        """입력 필드 찾기 - 기존 성공 로직 사용"""
        print("입력 필드 검색 중...")
        fields = {}

        # 긴 대기 시간
        time.sleep(5)

        # 생년월일 입력 필드 - 더 많은 시도
        birth_selectors = [
            'input[placeholder*="생년월일"]',
            'input[placeholder*="yyyymmdd"]',
            'input[name*="birth"]',
            'input[maxlength="8"]',
            'input[type="text"]'
        ]

        for selector in birth_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    fields["birthdate"] = element
                    print(f"생년월일 필드 발견: {selector}")
                    break
            except Exception:
                continue

        # 성별 선택 - 기존 성공 로직
        try:
            male_radios = self.page.query_selector_all('input[type="radio"][value*="M"], input[type="radio"][value*="1"]')
            female_radios = self.page.query_selector_all('input[type="radio"][value*="F"], input[type="radio"][value*="2"]')

            gender_male = None
            gender_female = None

            for radio in male_radios:
                if radio.is_visible():
                    gender_male = radio
                    break

            for radio in female_radios:
                if radio.is_visible():
                    gender_female = radio
                    break

            if gender_male and gender_female:
                fields["gender"] = {"male": gender_male, "female": gender_female}
                print("성별 선택 필드 발견")

        except Exception:
            pass

        # 보험기간/납입기간 셀렉트 박스
        try:
            insurance_selects = self.page.query_selector_all('select')

            for select in insurance_selects:
                if select.is_visible():
                    try:
                        parent = select.locator('xpath=./..')
                        if parent.count() > 0:
                            parent_text = parent.inner_text().strip()
                            if "보험기간" in parent_text:
                                fields["insurance_period"] = select
                                print("보험기간 선택 필드 발견")
                            elif "납입기간" in parent_text or "납입" in parent_text:
                                fields["payment_period"] = select
                                print("납입기간 선택 필드 발견")
                    except Exception:
                        continue
        except Exception:
            pass

        # 계산 버튼
        calc_selectors = [
            'button:has-text("계산")',
            'button:has-text("조회")',
            'input[type="submit"]'
        ]

        for selector in calc_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    fields["calc_button"] = element
                    print(f"계산 버튼 발견: {selector}")
                    break
            except Exception:
                continue

        print(f"발견된 필드: {list(fields.keys())}")
        return fields

    def safe_click(self, element, description="요소"):
        """매우 안전한 클릭"""
        print(f"  {description} 클릭 준비...")

        # 클릭 전 대기
        self.random_delay(2, 5)

        try:
            # 모달 제거
            self.dismiss_blocking_modal()
            time.sleep(2)

            # 요소가 보이는지 확인
            if hasattr(element, 'is_visible') and not element.is_visible():
                print(f"  {description}가 보이지 않음")
                return False

            # 클릭 시도
            if hasattr(element, 'click'):
                element.click(timeout=5000, force=True)
            else:
                self.page.evaluate("(element) => element.click()", element)

            print(f"  {description} 클릭 성공")

            # 클릭 후 대기
            time.sleep(3)
            return True

        except Exception as e:
            print(f"  {description} 클릭 실패: {e}")
            return False

    def set_period_combination(self, fields, combination):
        """기간 조합 설정 - JavaScript 사용"""
        try:
            print(f"  기간 조합 설정: {combination['insurance']}/{combination['payment']}")

            # 보험기간 설정
            if "insurance_period" in fields:
                insurance_select = fields["insurance_period"]
                success = self.page.evaluate(f"""
                    (select) => {{
                        try {{
                            const targetValue = "{combination['insurance_value']}";
                            const targetText = "{combination['insurance']}";

                            for (let option of select.options) {{
                                if (option.value === targetValue || option.text.includes('10년')) {{
                                    select.value = option.value;
                                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                            return false;
                        }} catch (e) {{
                            return false;
                        }}
                    }}
                """, insurance_select)

                if success:
                    print(f"  보험기간 설정 성공")
                    time.sleep(2)

            # 납입기간 설정
            if "payment_period" in fields:
                payment_select = fields["payment_period"]
                success = self.page.evaluate(f"""
                    (select) => {{
                        try {{
                            const targetValue = "{combination['payment_value']}";
                            const targetText = "{combination['payment']}";

                            for (let option of select.options) {{
                                if (option.value === targetValue || option.text.includes('10년')) {{
                                    select.value = option.value;
                                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                            return false;
                        }} catch (e) {{
                            return false;
                        }}
                    }}
                """, payment_select)

                if success:
                    print(f"  납입기간 설정 성공")
                    time.sleep(2)

            return True

        except Exception as e:
            print(f"기간 조합 설정 실패: {e}")
            return False

    def wait_for_calculation(self):
        """계산 완료까지 충분히 대기"""
        print("  보험료 계산 대기...")

        # 기본 대기
        time.sleep(self.calculation_wait)

        # 추가 확인
        for i in range(5):
            try:
                body_text = self.page.inner_text('body')
                if "원/월" in body_text or "월보험료" in body_text or "보험료" in body_text:
                    print(f"  계산 완료 확인 (시도 {i+1})")
                    break
                else:
                    print(f"  계산 결과 대기 중... ({i+1}/5)")
                    time.sleep(5)
            except Exception:
                time.sleep(5)

    def extract_price_data(self):
        """보험료 추출"""
        try:
            body_text = self.page.inner_text('body')

            # 다양한 패턴으로 가격 찾기
            price_patterns = [
                r"월\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"월보험료\s*[:：]\s*([\d,]+)\s*원",
                r"보험료\s*[:：]\s*([\d,]+)\s*원",
                r"([\d,]+)\s*원/월",
                r"월\s*([\d,]+)\s*원"
            ]

            monthly_premium = 0
            for pattern in price_patterns:
                match = re.search(pattern, body_text)
                if match:
                    price_str = match.group(1).replace(',', '')
                    monthly_premium = int(price_str)
                    print(f"  가격 추출: {monthly_premium:,}원")
                    break

            return {"monthly_premium": monthly_premium}

        except Exception as e:
            print(f"가격 추출 실패: {e}")
            return {"monthly_premium": 0}

    def collect_data(self):
        """데이터 수집 - 초저속 안전 모드"""
        print("KB생명 초저속 안전 데이터 수집 시작")
        print(f"대상: {len(self.test_ages)}개 나이 × {len(self.genders)}개 성별 × {len(self.period_combinations)}개 조합")
        print(f"예상 소요 시간: 약 {len(self.test_ages) * len(self.genders) * len(self.period_combinations) * 2}분")

        try:
            # 페이지 이동 - 매우 느리게
            print(f"페이지 이동: {self.url}")
            self.page.goto(self.url, wait_until='networkidle', timeout=120000)

            # 충분한 로딩 대기
            print("페이지 로딩 대기...")
            time.sleep(15)

            print(f"페이지 로딩 완료: {self.page.title()}")

            # 초기 모달 처리
            self.dismiss_blocking_modal()
            time.sleep(5)

            # 입력 필드 찾기
            fields = self.find_input_fields()
            if not fields:
                print("필요한 입력 필드를 찾을 수 없습니다.")
                return False

            # 데이터 수집 시작
            case_num = 0
            total_cases = len(self.test_ages) * len(self.genders) * len(self.period_combinations)

            for age in self.test_ages:
                for gender in self.genders:
                    for combination in self.period_combinations:
                        case_num += 1
                        print(f"\n[{case_num}/{total_cases}] {age}세 {gender['korean']} - {combination['insurance']}/{combination['payment']}")

                        # 케이스 시작 전 대기
                        if case_num > 1:
                            self.random_delay()

                        try:
                            # 모달 제거
                            self.dismiss_blocking_modal()

                            # 생년월일 입력
                            if "birthdate" in fields:
                                birth_year = 2024 - age
                                birthdate = f"{birth_year}0101"
                                fields["birthdate"].fill(birthdate)
                                print(f"  생년월일 입력: {birthdate}")
                                time.sleep(3)

                            # 성별 선택
                            if "gender" in fields:
                                gender_element = fields["gender"][gender["value"]]
                                self.safe_click(gender_element, f"성별({gender['korean']})")

                            # 기간 설정
                            self.set_period_combination(fields, combination)

                            # 계산 버튼 클릭
                            if "calc_button" in fields:
                                if self.safe_click(fields["calc_button"], "계산 버튼"):
                                    # 계산 완료까지 대기
                                    self.wait_for_calculation()

                                    # 결과 추출
                                    result = self.extract_price_data()

                                    # 데이터 저장
                                    data_entry = {
                                        "age": age,
                                        "gender": gender["value"],
                                        "gender_korean": gender["korean"],
                                        "insurance_period": combination["insurance"],
                                        "payment_period": combination["payment"],
                                        "monthly_premium": result.get("monthly_premium", 0),
                                        "collected_at": datetime.now().isoformat()
                                    }

                                    self.collected_data.append(data_entry)
                                    print(f"  수집 완료: {data_entry['monthly_premium']:,}원")

                        except Exception as e:
                            print(f"  케이스 처리 실패: {e}")
                            continue

            return len(self.collected_data) > 0

        except Exception as e:
            print(f"데이터 수집 실패: {e}")
            return False

    def save_results(self):
        """결과 저장"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # CSV 저장
        csv_file = self.output_dir / f'kb_ultra_slow_data_{timestamp}.csv'

        if self.collected_data:
            with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'age', 'gender', 'gender_korean',
                    'insurance_period', 'payment_period',
                    'monthly_premium', 'collected_at'
                ])
                writer.writeheader()
                writer.writerows(self.collected_data)

        print(f"\n결과 저장: {csv_file}")
        print(f"수집 데이터: {len(self.collected_data)}건")

        # 결과 요약
        if self.collected_data:
            valid_data = [d for d in self.collected_data if d['monthly_premium'] > 0]
            print(f"유효 데이터: {len(valid_data)}건")

            for data in self.collected_data:
                print(f"  {data['age']}세 {data['gender_korean']}: {data['monthly_premium']:,}원")

    def run(self):
        """메인 실행"""
        print("KB생명 초저속 안전 수집기 시작")
        print("=" * 60)

        try:
            # 브라우저 설정
            self.setup_browser()
            print("브라우저 설정 완료")

            # 데이터 수집
            success = self.collect_data()

            if success:
                self.save_results()
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
    collector = KBUltraSlowCollector()
    collector.run()