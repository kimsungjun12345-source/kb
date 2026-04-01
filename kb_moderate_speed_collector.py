"""
KB생명 적정 속도 수집기 - 안전하면서도 빠른 수집
10-15초 대기로 효율성과 안전성의 균형
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


class KBModerateSpeedCollector:
    """KB생명 적정 속도 수집기"""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None

        # 테스트 범위 (4개 케이스)
        self.test_ages = [30, 35]
        self.genders = [
            {"value": "male", "text": "남자", "korean": "남자"},
            {"value": "female", "text": "여자", "korean": "여자"}
        ]

        # 두 개 조합 테스트
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

        # 적정 속도 설정
        self.min_delay = 10  # 최소 10초 대기
        self.max_delay = 15  # 최대 15초 대기
        self.calculation_wait = 8   # 계산 결과 대기 8초

    def random_delay(self, min_sec=None, max_sec=None):
        """적정 랜덤 지연"""
        min_time = min_sec if min_sec is not None else self.min_delay
        max_time = max_sec if max_sec is not None else self.max_delay
        delay = random.uniform(min_time, max_time)
        print(f"  대기: {delay:.1f}초...")
        time.sleep(delay)

    def setup_browser(self):
        """브라우저 설정 - 적정 속도"""
        playwright = sync_playwright().start()

        self.browser = playwright.chromium.launch(
            headless=False,
            slow_mo=1000,  # 1초 지연 (적정)
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ]
        )

        self.context = self.browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            locale='ko-KR'
        )

        self.page = self.context.new_page()
        self.page.set_default_timeout(60000)  # 1분 타임아웃

    def dismiss_blocking_modal(self):
        """모달 제거"""
        try:
            # 확인 버튼들 찾기
            button_texts = ["확인", "동의", "계속", "닫기", "예", "취소"]

            for text in button_texts:
                try:
                    btn = self.page.locator(f'button:has-text("{text}")').first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=2000, force=True)
                        time.sleep(1)
                        print(f"  모달 버튼 클릭: {text}")
                        break
                except Exception:
                    continue

            # 기본 모달 제거
            try:
                self.page.evaluate("""
                    document.querySelectorAll('.modal-overlay, #systemAlert1').forEach(modal => {
                        if (modal) modal.style.display = 'none';
                    });
                """)
            except Exception:
                pass

        except Exception as e:
            print(f"  모달 제거 오류: {e}")

    def find_input_fields(self):
        """입력 필드 찾기 - 기존 성공 로직"""
        print("입력 필드 검색 중...")
        fields = {}
        time.sleep(3)  # 적당한 대기

        # 생년월일 필드
        birth_selectors = [
            'input[placeholder*="생년월일"]',
            'input[placeholder*="yyyymmdd"]',
            'input[name*="birth"]',
            'input[maxlength="8"]'
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

        # 성별 선택
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

        # 보험기간/납입기간
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
        """적정 속도 클릭"""
        print(f"  {description} 클릭...")

        # 적당한 대기
        time.sleep(2)

        try:
            # 모달 제거
            self.dismiss_blocking_modal()
            time.sleep(1)

            # 클릭 시도
            if hasattr(element, 'click'):
                element.click(timeout=5000, force=True)
            else:
                self.page.evaluate("(element) => element.click()", element)

            print(f"  {description} 클릭 성공")
            time.sleep(2)  # 클릭 후 대기
            return True

        except Exception as e:
            print(f"  {description} 클릭 실패: {e}")
            return False

    def set_period_combination(self, fields, combination):
        """기간 조합 설정"""
        try:
            print(f"  기간 설정: {combination['insurance']}/{combination['payment']}")

            # 보험기간 설정
            if "insurance_period" in fields:
                success = self.page.evaluate(f"""
                    (select) => {{
                        try {{
                            for (let option of select.options) {{
                                if (option.value === "{combination['insurance_value']}" ||
                                    option.text.includes("{combination['insurance_value']}년") ||
                                    (option.text.includes("종신") && "{combination['insurance']}" === "종신")) {{
                                    select.value = option.value;
                                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                            return false;
                        }} catch (e) {{ return false; }}
                    }}
                """, fields["insurance_period"])

                if success:
                    print(f"  보험기간 설정 성공")
                    time.sleep(2)

            # 납입기간 설정
            if "payment_period" in fields:
                success = self.page.evaluate(f"""
                    (select) => {{
                        try {{
                            for (let option of select.options) {{
                                if (option.value === "{combination['payment_value']}" ||
                                    option.text.includes("{combination['payment_value']}년")) {{
                                    select.value = option.value;
                                    select.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }}
                            }}
                            return false;
                        }} catch (e) {{ return false; }}
                    }}
                """, fields["payment_period"])

                if success:
                    print(f"  납입기간 설정 성공")
                    time.sleep(2)

            return True

        except Exception as e:
            print(f"기간 설정 실패: {e}")
            return False

    def wait_for_calculation(self):
        """적정 시간 계산 대기"""
        print("  보험료 계산 대기...")

        # 기본 대기
        time.sleep(self.calculation_wait)

        # 결과 확인
        for i in range(3):
            try:
                body_text = self.page.inner_text('body')
                if "원/월" in body_text or "월보험료" in body_text or "보험료" in body_text:
                    print(f"  계산 완료 확인 (시도 {i+1})")
                    break
                else:
                    print(f"  추가 대기 중... ({i+1}/3)")
                    time.sleep(3)
            except Exception:
                time.sleep(3)

    def extract_price_data(self):
        """보험료 추출"""
        try:
            body_text = self.page.inner_text('body')

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
        """적정 속도 데이터 수집"""
        total_cases = len(self.test_ages) * len(self.genders) * len(self.period_combinations)
        print(f"KB생명 적정 속도 데이터 수집 시작")
        print(f"대상: {total_cases}케이스 (예상 시간: {total_cases * 0.5}분)")

        try:
            print(f"페이지 이동: {self.url}")
            self.page.goto(self.url, wait_until='networkidle')
            time.sleep(8)  # 적당한 로딩 대기

            print(f"페이지 로딩 완료: {self.page.title()}")

            # 모달 처리
            self.dismiss_blocking_modal()
            time.sleep(3)

            # 필드 찾기
            fields = self.find_input_fields()
            if not fields:
                print("필요한 입력 필드를 찾을 수 없습니다.")
                return False

            # 데이터 수집
            case_num = 0

            for age in self.test_ages:
                for gender in self.genders:
                    for combination in self.period_combinations:
                        case_num += 1
                        print(f"\n[{case_num}/{total_cases}] {age}세 {gender['korean']} - {combination['insurance']}/{combination['payment']}")

                        # 케이스 간 대기 (첫 번째 제외)
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
                                time.sleep(2)

                            # 성별 선택
                            if "gender" in fields:
                                gender_element = fields["gender"][gender["value"]]
                                self.safe_click(gender_element, f"성별({gender['korean']})")

                            # 기간 설정
                            self.set_period_combination(fields, combination)

                            # 계산 버튼 클릭
                            if "calc_button" in fields:
                                if self.safe_click(fields["calc_button"], "계산 버튼"):
                                    # 계산 완료 대기
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
                                        "insurance_period_value": combination["insurance_value"],
                                        "payment_period_value": combination["payment_value"],
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
        csv_file = self.output_dir / f'kb_moderate_data_{timestamp}.csv'

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

        print(f"\n결과 저장: {csv_file}")
        print(f"수집 데이터: {len(self.collected_data)}건")

        if self.collected_data:
            valid_data = [d for d in self.collected_data if d['monthly_premium'] > 0]
            print(f"유효 데이터: {len(valid_data)}건")

            for data in self.collected_data:
                print(f"  {data['age']}세 {data['gender_korean']} {data['insurance_period']}/{data['payment_period']}: {data['monthly_premium']:,}원")

    def run(self):
        """메인 실행"""
        print("KB생명 적정 속도 수집기 시작")
        print("=" * 50)

        try:
            self.setup_browser()
            print("브라우저 설정 완료")

            success = self.collect_data()

            if success:
                self.save_results()
            else:
                print("데이터 수집에 실패했습니다.")

        except Exception as e:
            print(f"실행 중 오류: {e}")
        finally:
            if self.browser:
                self.browser.close()
                print("\n브라우저 종료 완료")


if __name__ == "__main__":
    collector = KBModerateSpeedCollector()
    collector.run()