"""
KB생명 보험기간/납입기간별 가격 변화 데이터 수집기
다양한 나이대(20~65세)에서 보험기간/납입기간 조합별 가격 변화 수집
"""

import sys
import json
import time
import random
import re
import csv
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime, date

class KBPeriodPriceCollector:
    """KB생명 보험기간/납입기간별 가격 수집기"""

    def __init__(self):
        # Windows 콘솔 인코딩 설정
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

        # KB생명 연금보험 URL
        self.target_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

        # 출력 디렉토리
        self.output_dir = Path("./outputs")
        self.output_dir.mkdir(exist_ok=True)

        # 전체 나이 범위 (19-65세)
        self.test_ages = list(range(19, 66))  # 19세~65세 전체

        # 성별
        self.genders = ["male", "female"]
        self.gender_korean = {"male": "남자", "female": "여자"}

        # 전체 보험기간/납입기간 조합
        self.period_combinations = [
            {"insurance": "정기 10년", "payment": "납입 10년", "insurance_value": "10", "payment_value": "10"},
            {"insurance": "정기 15년", "payment": "납입 15년", "insurance_value": "15", "payment_value": "15"},
            {"insurance": "정기 20년", "payment": "납입 15년", "insurance_value": "20", "payment_value": "15"},
            {"insurance": "정기 20년", "payment": "납입 20년", "insurance_value": "20", "payment_value": "20"},
            {"insurance": "정기 30년", "payment": "납입 20년", "insurance_value": "30", "payment_value": "20"},
            {"insurance": "종신", "payment": "납입 20년", "insurance_value": "99", "payment_value": "20"},
            {"insurance": "종신", "payment": "납입 30년", "insurance_value": "99", "payment_value": "30"},
            {"insurance": "종신", "payment": "전기납", "insurance_value": "99", "payment_value": "99"}
        ]

        # 수집된 데이터 저장
        self.collected_data = []

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

        # JS 다이얼로그 자동 수락
        try:
            self.page.on("dialog", lambda d: d.accept())
        except Exception:
            pass

        print("브라우저 설정 완료")

    def human_pause(self, a: int = 300, b: int = 800):
        """사람처럼 대기"""
        try:
            self.page.wait_for_timeout(random.randint(a, b))
        except Exception:
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
                print(f"  {description} 안전 클릭 오류: {e}")

        return False

    def navigate_to_page(self):
        """KB생명 연금보험 페이지로 이동"""
        print(f"페이지 이동: {self.target_url}")

        try:
            self.page.goto(self.target_url, wait_until='networkidle', timeout=30000)
            self.page.wait_for_timeout(3000)

            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            # 초기 모달 닫기
            self.dismiss_blocking_modal()
            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def dismiss_blocking_modal(self):
        """강화된 블로킹 모달 제거"""
        try:
            # JavaScript로 직접 모달 제거
            self.page.evaluate("""
                // 모든 모달 오버레이 제거
                document.querySelectorAll('.modal-overlay, .modal.open, .alert.open').forEach(el => {
                    el.style.display = 'none';
                    el.remove();
                });

                // systemAlert 특별 처리
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

            # 추가 JavaScript 정리
            self.page.evaluate("""
                // 이벤트 차단 요소들 제거
                document.querySelectorAll('[class*="overlay"], [class*="backdrop"]').forEach(el => {
                    el.style.pointerEvents = 'none';
                    el.style.display = 'none';
                });
            """)

        except Exception as e:
            print(f"  모달 제거 시도 중 오류: {e}")
            pass

    def find_input_fields(self):
        """입력 필드들 찾기"""
        fields = {}

        # 생년월일 입력 필드
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
        gender_male = None
        gender_female = None

        try:
            # 라디오 버튼 형태
            male_radios = self.page.query_selector_all('input[type="radio"][value*="M"], input[type="radio"][value*="1"]')
            female_radios = self.page.query_selector_all('input[type="radio"][value*="F"], input[type="radio"][value*="2"]')

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
                    # 근처 텍스트로 용도 파악
                    parent_text = ""
                    try:
                        parent = select.locator('xpath=./..')
                        if parent.count() > 0:
                            parent_text = parent.inner_text().strip()
                    except Exception:
                        pass

                    if "보험기간" in parent_text:
                        fields["insurance_period"] = select
                        print("보험기간 선택 필드 발견")
                    elif "납입기간" in parent_text or "납입" in parent_text:
                        fields["payment_period"] = select
                        print("납입기간 선택 필드 발견")

        except Exception:
            pass

        return fields

    def find_calculate_button(self):
        """계산 버튼 찾기"""
        calc_selectors = [
            'button:has-text("계산")',
            'button:has-text("조회")',
            'button:has-text("확인")',
            'input[type="submit"]'
        ]

        for selector in calc_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"계산 버튼 발견: {selector}")
                    return element
            except Exception:
                continue

        return None

    def yyyymmdd_for_age(self, age: int) -> str:
        """나이를 생년월일(yyyymmdd)로 변환"""
        year = date.today().year - age
        return f"{year:04d}0101"

    def set_period_combination(self, fields, combination):
        """보험기간/납입기간 조합 설정"""
        try:
            # 보험기간 설정
            if "insurance_period" in fields:
                insurance_select = fields["insurance_period"]
                try:
                    # 옵션들 확인
                    options = insurance_select.query_selector_all('option')
                    for option in options:
                        value = option.get_attribute('value') or ""
                        text = option.inner_text().strip()

                        # 값이나 텍스트가 매치되면 선택
                        if (combination["insurance_value"] in value or
                            combination["insurance"] in text or
                            combination["insurance_value"] == value):
                            option.click()
                            print(f"  보험기간 설정: {text}")
                            break
                except Exception as e:
                    print(f"  보험기간 설정 실패: {e}")

            self.page.wait_for_timeout(500)

            # 납입기간 설정
            if "payment_period" in fields:
                payment_select = fields["payment_period"]
                try:
                    options = payment_select.query_selector_all('option')
                    for option in options:
                        value = option.get_attribute('value') or ""
                        text = option.inner_text().strip()

                        if (combination["payment_value"] in value or
                            combination["payment"] in text or
                            combination["payment_value"] == value):
                            option.click()
                            print(f"  납입기간 설정: {text}")
                            break
                except Exception as e:
                    print(f"  납입기간 설정 실패: {e}")

            self.page.wait_for_timeout(500)
            return True

        except Exception as e:
            print(f"기간 조합 설정 실패: {e}")
            return False

    def extract_premium_result(self):
        """보험료 결과 추출"""
        try:
            self.page.wait_for_timeout(2000)

            # 페이지 스크롤하여 결과 확인
            try:
                self.page.mouse.wheel(0, 500)
            except Exception:
                pass

            # 페이지 텍스트 수집
            body_text = ""
            try:
                body_text = self.page.locator("body").inner_text(timeout=15000)
            except Exception:
                body_text = self.page.content()

            # 월 보험료 패턴들
            premium_patterns = [
                r"월\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"월\s*납입보험료\s*[:：]\s*([\d,]+)\s*원",
                r"보험료\s*\(\s*월\s*\)\s*([\d,]+)\s*원",
                r"월\s*([\d,]{3,})\s*원"
            ]

            monthly_premium = 0
            found_pattern = ""

            for pattern in premium_patterns:
                match = re.search(pattern, body_text)
                if match:
                    try:
                        monthly_premium = int(match.group(1).replace(",", ""))
                        found_pattern = pattern
                        break
                    except ValueError:
                        continue

            # 추가 정보 추출
            details = {
                "found_pattern": found_pattern,
                "raw_snippet": body_text[:3000]  # 처음 3000자
            }

            # 보험기간/납입기간 정보 확인
            period_info = {}

            insurance_match = re.search(r"보험기간\s*[:：]\s*([^\n]+)", body_text)
            if insurance_match:
                period_info["insurance_period"] = insurance_match.group(1).strip()

            payment_match = re.search(r"납입기간\s*[:：]\s*([^\n]+)", body_text)
            if payment_match:
                period_info["payment_period"] = payment_match.group(1).strip()

            details["period_info"] = period_info

            if monthly_premium > 0:
                return {
                    "monthly_premium": monthly_premium,
                    "details": details
                }

            # 실패 시 로그용 정보 반환
            return {
                "monthly_premium": 0,
                "details": {
                    "error": "보험료 추출 실패",
                    "raw_snippet": body_text[:1000]
                }
            }

        except Exception as e:
            print(f"결과 추출 오류: {e}")
            return {
                "monthly_premium": 0,
                "details": {"error": str(e)}
            }

    def collect_period_data(self):
        """보험기간/납입기간별 데이터 수집"""
        print(f"\n보험기간/납입기간별 데이터 수집 시작")
        print(f"대상: {len(self.test_ages)}개 나이 × {len(self.genders)}개 성별 × {len(self.period_combinations)}개 조합")

        # 페이지 요소들 찾기
        fields = self.find_input_fields()
        calc_button = self.find_calculate_button()

        if not fields.get("birthdate"):
            print("생년월일 입력 필드를 찾을 수 없습니다.")
            return False

        if not calc_button:
            print("계산 버튼을 찾을 수 없습니다.")
            return False

        total_cases = len(self.test_ages) * len(self.genders) * len(self.period_combinations)
        current_case = 0

        # 고정 생년월일 사용 (입력 검증 이슈 회피)
        fixed_birthdate = "19940101"  # 30세

        for age in self.test_ages:
            for gender in self.genders:
                for combination in self.period_combinations:
                    current_case += 1

                    print(f"\n[{current_case}/{total_cases}] {age}세 {self.gender_korean[gender]} - {combination['insurance']}/{combination['payment']}")

                    try:
                        # 모달 정리
                        self.dismiss_blocking_modal()

                        # 1. 생년월일 입력 (고정값 사용)
                        birthdate_field = fields["birthdate"]
                        birthdate_field.fill(fixed_birthdate)
                        print(f"  생년월일 입력: {fixed_birthdate}")
                        self.page.wait_for_timeout(500)

                        # 2. 성별 선택
                        if "gender" in fields and gender in fields["gender"]:
                            gender_field = fields["gender"][gender]
                            if not self.safe_click(gender_field, f"성별({self.gender_korean[gender]})"):
                                print(f"  성별 선택 실패")
                                continue

                        # 3. 보험기간/납입기간 설정
                        self.set_period_combination(fields, combination)

                        # 4. 계산 실행
                        if not self.safe_click(calc_button, "계산 버튼"):
                            print("  계산 버튼 클릭 실패")
                            continue

                        # 5. 결과 추출
                        result = self.extract_premium_result()

                        if result:
                            data = {
                                "age": age,
                                "gender": gender,
                                "gender_korean": self.gender_korean[gender],
                                "insurance_period": combination["insurance"],
                                "payment_period": combination["payment"],
                                "insurance_period_value": combination["insurance_value"],
                                "payment_period_value": combination["payment_value"],
                                "monthly_premium": result["monthly_premium"],
                                "details": result["details"],
                                "collected_at": datetime.now().isoformat()
                            }

                            self.collected_data.append(data)
                            print(f"  결과: {result['monthly_premium']:,}원")
                        else:
                            print("  결과 추출 실패")

                        # 다음 케이스를 위한 대기
                        self.human_pause(800, 1500)

                        # 20케이스마다 페이지 리로드 (안정성)
                        if current_case % 20 == 0:
                            print("  페이지 리로드...")
                            self.navigate_to_page()
                            fields = self.find_input_fields()
                            calc_button = self.find_calculate_button()

                    except Exception as e:
                        print(f"  케이스 처리 실패: {e}")
                        continue

        print(f"\n보험기간/납입기간 데이터 수집 완료: {len(self.collected_data)}건")
        return len(self.collected_data) > 0

    def save_collected_data(self):
        """수집된 데이터 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # JSON 파일
        json_file = self.output_dir / f'kb_period_price_data_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "period_price_data": self.collected_data,
                "collection_info": {
                    "total_records": len(self.collected_data),
                    "test_ages": self.test_ages,
                    "period_combinations": self.period_combinations,
                    "collected_at": timestamp
                }
            }, f, ensure_ascii=False, indent=2)

        # CSV 파일
        csv_file = self.output_dir / f'kb_period_price_data_{timestamp}.csv'
        if self.collected_data:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                # details 컬럼을 제외하고 저장 (JSON 때문에 CSV가 복잡해짐)
                simplified_data = []
                for item in self.collected_data:
                    simplified = {k: v for k, v in item.items() if k != 'details'}
                    simplified_data.append(simplified)

                writer = csv.DictWriter(f, fieldnames=simplified_data[0].keys())
                writer.writeheader()
                writer.writerows(simplified_data)

        print(f"\n데이터 저장 완료:")
        print(f"  JSON: {json_file}")
        print(f"  CSV: {csv_file}")

        return json_file

    def print_summary(self):
        """수집 결과 요약"""
        print("\n" + "="*60)
        print("KB생명 보험기간/납입기간별 가격 수집 결과")
        print("="*60)

        if not self.collected_data:
            print("수집된 데이터가 없습니다.")
            return

        print(f"총 수집 건수: {len(self.collected_data)}건")

        # 조합별 통계
        combination_stats = {}
        for data in self.collected_data:
            combo_key = f"{data['insurance_period']}/{data['payment_period']}"
            if combo_key not in combination_stats:
                combination_stats[combo_key] = []
            combination_stats[combo_key].append(data['monthly_premium'])

        print(f"\n기간 조합별 평균 보험료:")
        for combo, premiums in combination_stats.items():
            if premiums and any(p > 0 for p in premiums):
                valid_premiums = [p for p in premiums if p > 0]
                if valid_premiums:
                    avg_premium = sum(valid_premiums) / len(valid_premiums)
                    print(f"  {combo}: {avg_premium:,.0f}원 ({len(valid_premiums)}건)")

        # 샘플 데이터
        print(f"\n샘플 데이터 (처음 5건):")
        for i, data in enumerate(self.collected_data[:5], 1):
            print(f"  {i}. {data['age']}세 {data['gender_korean']} - {data['insurance_period']}/{data['payment_period']}: {data['monthly_premium']:,}원")

    def run_collection(self):
        """메인 수집 실행"""
        print("KB생명 보험기간/납입기간별 가격 수집기 시작")
        print("="*60)

        try:
            # 1. 브라우저 설정
            self.setup_browser()

            # 2. 페이지 이동
            if not self.navigate_to_page():
                return False

            # 3. 데이터 수집
            success = self.collect_period_data()

            if success:
                # 4. 데이터 저장
                saved_file = self.save_collected_data()

                # 5. 결과 요약
                self.print_summary()

                print(f"\n수집 완료! 파일: {saved_file}")
                return True
            else:
                print("데이터 수집 실패")
                return False

        except Exception as e:
            print(f"수집기 실행 중 오류: {e}")
            return False

        finally:
            try:
                if hasattr(self, 'context'):
                    self.context.close()
                if hasattr(self, 'browser'):
                    self.browser.close()
                if hasattr(self, 'playwright'):
                    self.playwright.stop()
                print("\n브라우저 종료 완료")
            except Exception:
                pass

def main():
    """메인 함수"""
    collector = KBPeriodPriceCollector()
    collector.run_collection()

if __name__ == "__main__":
    main()