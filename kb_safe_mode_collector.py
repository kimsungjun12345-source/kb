"""
KB생명 연금보험 안전 모드 데이터 수집기
블락 방지를 위한 매우 긴 대기 시간과 신중한 접근
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

class KBSafeModeCollector:
    """KB생명 안전 모드 데이터 수집기 - 블락 방지"""

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

        # 안전 모드 - 작은 범위부터 시작
        self.test_ages = [25, 30, 35, 40, 45, 50, 55, 60]  # 8개 연령만
        self.genders = ["male", "female"]
        self.gender_korean = {"male": "남자", "female": "여자"}

        # 간단한 조합만 (블락 방지)
        self.period_combinations = [
            {"insurance": "정기 10년", "payment": "납입 10년", "insurance_value": "10", "payment_value": "10"},
            {"insurance": "정기 20년", "payment": "납입 20년", "insurance_value": "20", "payment_value": "20"},
            {"insurance": "종신", "payment": "납입 20년", "insurance_value": "99", "payment_value": "20"}
        ]

        # 수집된 데이터 저장
        self.collected_data = []

        # 안전 대기 시간 (초)
        self.safe_wait_time = 10  # 10초 대기
        self.long_wait_time = 30  # 30초 긴 대기
        self.case_wait_time = 60   # 케이스 간 1분 대기

    def setup_browser(self):
        """브라우저 설정 - 안전 모드"""
        self.playwright = sync_playwright().start()

        # 더 느린 속도와 안전한 설정
        self.browser = self.playwright.chromium.launch(
            headless=False,
            slow_mo=1000,  # 매우 느린 모드 (1초 딜레이)
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
        )

        self.context = self.browser.new_context()
        self.page = self.context.new_page()

        # JS 다이얼로그 자동 수락
        try:
            self.page.on("dialog", lambda d: d.accept())
        except Exception:
            pass

        print("안전 모드 브라우저 설정 완료")

    def safe_pause(self, mode="normal"):
        """안전한 대기 시간"""
        if mode == "short":
            wait_time = random.randint(self.safe_wait_time, self.safe_wait_time + 5)
        elif mode == "long":
            wait_time = random.randint(self.long_wait_time, self.long_wait_time + 10)
        elif mode == "case":
            wait_time = random.randint(self.case_wait_time, self.case_wait_time + 20)
        else:
            wait_time = random.randint(5, 10)

        print(f"  안전 대기: {wait_time}초...")
        try:
            self.page.wait_for_timeout(wait_time * 1000)
        except Exception:
            time.sleep(wait_time)

    def navigate_to_page(self):
        """KB생명 연금보험 페이지로 이동 - 안전 모드"""
        print(f"안전 모드 페이지 이동: {self.target_url}")

        try:
            self.page.goto(self.target_url, wait_until='networkidle', timeout=60000)
            self.safe_pause("long")  # 페이지 로딩 후 긴 대기

            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            # 초기 모달 처리
            self.gentle_modal_dismiss()
            self.safe_pause("short")

            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def gentle_modal_dismiss(self):
        """부드러운 모달 제거 (블락 방지)"""
        try:
            # 부드럽게 모달 찾아서 닫기
            button_texts = ["확인", "동의", "예"]

            for text in button_texts:
                try:
                    btn = self.page.locator(f'button:has-text("{text}")').first
                    if btn.count() > 0 and btn.is_visible():
                        self.safe_pause("short")  # 클릭 전 대기
                        btn.click(timeout=5000, force=True)
                        print(f"  모달 버튼 클릭: {text}")
                        self.safe_pause("short")  # 클릭 후 대기
                        break
                except Exception:
                    continue

        except Exception:
            pass

    def find_input_fields_safely(self):
        """안전하게 입력 필드들 찾기"""
        fields = {}

        print("  입력 필드 탐색 중...")

        # 생년월일 입력 필드
        birth_selectors = [
            'input[placeholder*="생년월일"]',
            'input[placeholder*="yyyymmdd"]',
            'input[name*="birth"]',
            'input[maxlength="8"]'
        ]

        for selector in birth_selectors:
            try:
                self.safe_pause("short")
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    fields["birthdate"] = element
                    print(f"  생년월일 필드 발견: {selector}")
                    break
            except Exception:
                continue

        # 성별 선택 (안전하게)
        try:
            self.safe_pause("short")
            # 라디오 버튼 찾기
            male_radios = self.page.query_selector_all('input[type="radio"]')
            gender_elements = {"male": None, "female": None}

            for radio in male_radios:
                try:
                    if radio.is_visible():
                        value = radio.get_attribute("value") or ""
                        name = radio.get_attribute("name") or ""

                        # 값으로 성별 추정
                        if "1" in value or "M" in value.upper() or "남" in name:
                            gender_elements["male"] = radio
                        elif "2" in value or "F" in value.upper() or "여" in name:
                            gender_elements["female"] = radio
                except Exception:
                    continue

            if gender_elements["male"] and gender_elements["female"]:
                fields["gender"] = gender_elements
                print("  성별 선택 필드 발견")

        except Exception:
            pass

        return fields

    def find_calculate_button_safely(self):
        """안전하게 계산 버튼 찾기"""
        calc_selectors = [
            'button:has-text("계산")',
            'button:has-text("조회")',
            'button:has-text("확인")',
            'input[type="submit"]'
        ]

        for selector in calc_selectors:
            try:
                self.safe_pause("short")
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"  계산 버튼 발견: {selector}")
                    return element
            except Exception:
                continue

        return None

    def safe_click(self, element, description="요소"):
        """매우 안전한 클릭"""
        try:
            print(f"  {description} 클릭 준비...")

            # 클릭 전 긴 대기
            self.safe_pause("short")

            # 모달 정리
            self.gentle_modal_dismiss()

            # 스크롤해서 요소 보이게 하기
            try:
                if hasattr(element, 'scroll_into_view_if_needed'):
                    element.scroll_into_view_if_needed()
                else:
                    self.page.evaluate("(element) => element.scrollIntoView()", element)
            except Exception:
                pass

            self.safe_pause("short")

            # 부드럽게 클릭
            if hasattr(element, 'click'):
                element.click(timeout=10000, force=True)
            else:
                self.page.evaluate("(element) => element.click()", element)

            print(f"  {description} 클릭 완료")
            self.safe_pause("short")  # 클릭 후 대기
            return True

        except Exception as e:
            print(f"  {description} 클릭 실패: {e}")
            return False

    def safe_fill_input(self, input_element, value, description="입력"):
        """안전한 입력 필드 채우기"""
        try:
            print(f"  {description}: {value}")

            self.safe_pause("short")

            # 기존 값 지우기
            input_element.click(timeout=5000)
            self.safe_pause("short")

            try:
                input_element.press("Control+A")
                self.safe_pause("short")
                input_element.press("Delete")
                self.safe_pause("short")
            except Exception:
                pass

            # 천천히 타이핑
            input_element.type(value, delay=100)  # 100ms 딜레이
            self.safe_pause("short")

            # Tab으로 포커스 이동
            try:
                input_element.press("Tab")
            except Exception:
                pass

            self.safe_pause("short")
            return True

        except Exception as e:
            print(f"  {description} 실패: {e}")
            return False

    def yyyymmdd_for_age(self, age: int) -> str:
        """나이를 생년월일(yyyymmdd)로 변환"""
        year = date.today().year - age
        return f"{year:04d}0101"

    def extract_premium_safely(self):
        """안전하게 보험료 결과 추출"""
        try:
            print("  결과 추출 중...")
            self.safe_pause("long")  # 결과 로딩 대기

            # 결과 영역 확인을 위한 스크롤
            try:
                self.page.mouse.wheel(0, 300)
                self.safe_pause("short")
            except Exception:
                pass

            # 페이지 텍스트 수집
            body_text = ""
            try:
                body_text = self.page.locator("body").inner_text(timeout=20000)
            except Exception:
                body_text = self.page.content()

            # 보험료 패턴 찾기
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

            return {
                "monthly_premium": monthly_premium,
                "found_pattern": found_pattern,
                "snippet": body_text[:1000]
            }

        except Exception as e:
            print(f"  결과 추출 오류: {e}")
            return {"monthly_premium": 0, "error": str(e)}

    def collect_single_case_safely(self, age, gender, combination, fields, calc_button):
        """안전하게 단일 케이스 데이터 수집"""
        try:
            combo_name = f"{combination['insurance']}/{combination['payment']}"
            print(f"\n--- {age}세 {self.gender_korean[gender]} - {combo_name} ---")

            # 1. 생년월일 입력
            if "birthdate" not in fields:
                print("  생년월일 입력 필드 없음")
                return None

            birthdate = self.yyyymmdd_for_age(age)
            if not self.safe_fill_input(fields["birthdate"], birthdate, "생년월일"):
                return None

            # 2. 성별 선택
            if "gender" in fields and gender in fields["gender"]:
                if not self.safe_click(fields["gender"][gender], f"성별({self.gender_korean[gender]})"):
                    return None
            else:
                print(f"  성별 선택 필드 없음")

            # 3. 계산 실행
            if not self.safe_click(calc_button, "계산 버튼"):
                return None

            # 4. 결과 추출
            result = self.extract_premium_safely()

            if result:
                data = {
                    "age": age,
                    "gender": gender,
                    "gender_korean": self.gender_korean[gender],
                    "insurance_period": combination["insurance"],
                    "payment_period": combination["payment"],
                    "monthly_premium": result["monthly_premium"],
                    "found_pattern": result.get("found_pattern", ""),
                    "collected_at": datetime.now().isoformat()
                }

                print(f"  결과: {result['monthly_premium']:,}원")
                return data
            else:
                print("  결과 추출 실패")
                return None

        except Exception as e:
            print(f"  케이스 처리 실패: {e}")
            return None

    def collect_data_safely(self):
        """안전 모드 데이터 수집"""
        print(f"\n안전 모드 데이터 수집 시작")
        print(f"대상: {len(self.test_ages)}개 연령 × {len(self.genders)}개 성별 × {len(self.period_combinations)}개 조합")
        print(f"총 {len(self.test_ages) * len(self.genders) * len(self.period_combinations)}케이스")

        # 페이지 요소들 찾기
        fields = self.find_input_fields_safely()
        calc_button = self.find_calculate_button_safely()

        if not fields.get("birthdate"):
            print("생년월일 입력 필드를 찾을 수 없습니다.")
            return False

        if not calc_button:
            print("계산 버튼을 찾을 수 없습니다.")
            return False

        # 케이스별 수집 (매우 천천히)
        total_cases = len(self.test_ages) * len(self.genders) * len(self.period_combinations)
        current_case = 0

        for age in self.test_ages:
            for gender in self.genders:
                for combination in self.period_combinations:
                    current_case += 1

                    print(f"\n진행률: {current_case}/{total_cases}")

                    # 케이스 간 긴 대기 (블락 방지)
                    if current_case > 1:
                        self.safe_pause("case")

                    # 단일 케이스 수집
                    data = self.collect_single_case_safely(age, gender, combination, fields, calc_button)

                    if data:
                        self.collected_data.append(data)
                        print(f"  수집 성공! 총 {len(self.collected_data)}건")
                    else:
                        print(f"  수집 실패")

                    # 모달 정리
                    self.gentle_modal_dismiss()

                    # 10케이스마다 페이지 새로고침
                    if current_case % 10 == 0 and current_case < total_cases:
                        print("  안전을 위한 페이지 새로고침...")
                        self.safe_pause("long")
                        self.navigate_to_page()
                        fields = self.find_input_fields_safely()
                        calc_button = self.find_calculate_button_safely()
                        self.safe_pause("long")

        print(f"\n안전 모드 데이터 수집 완료: {len(self.collected_data)}건")
        return len(self.collected_data) > 0

    def save_safe_data(self):
        """수집된 데이터 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # JSON 파일
        json_file = self.output_dir / f'kb_safe_mode_data_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "safe_mode_data": self.collected_data,
                "collection_info": {
                    "total_records": len(self.collected_data),
                    "mode": "safe_mode",
                    "wait_times": {
                        "safe_wait": self.safe_wait_time,
                        "long_wait": self.long_wait_time,
                        "case_wait": self.case_wait_time
                    },
                    "collected_at": timestamp
                }
            }, f, ensure_ascii=False, indent=2)

        # CSV 파일
        csv_file = self.output_dir / f'kb_safe_mode_data_{timestamp}.csv'
        if self.collected_data:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.collected_data[0].keys())
                writer.writeheader()
                writer.writerows(self.collected_data)

        print(f"\n안전 모드 데이터 저장 완료:")
        print(f"  JSON: {json_file}")
        print(f"  CSV: {csv_file}")

        return json_file

    def run_safe_collection(self):
        """안전 모드 수집 실행"""
        print("KB생명 안전 모드 데이터 수집기 시작")
        print("="*60)
        print("블락 방지를 위한 매우 신중한 접근 모드")
        print("="*60)

        try:
            # 1. 브라우저 설정
            self.setup_browser()

            # 2. 페이지 이동
            if not self.navigate_to_page():
                print("페이지 이동 실패")
                return False

            # 3. 안전 모드 데이터 수집
            success = self.collect_data_safely()

            if success:
                # 4. 데이터 저장
                saved_file = self.save_safe_data()

                # 5. 결과 요약
                self.print_safe_summary()

                print(f"\n안전 모드 수집 완료! 파일: {saved_file}")
                return True
            else:
                print("안전 모드 데이터 수집 실패")
                return False

        except Exception as e:
            print(f"안전 모드 수집기 실행 중 오류: {e}")
            return False

        finally:
            try:
                if hasattr(self, 'context'):
                    self.context.close()
                if hasattr(self, 'browser'):
                    self.browser.close()
                if hasattr(self, 'playwright'):
                    self.playwright.stop()
                print("\n브라우저 안전 종료 완료")
            except Exception:
                pass

    def print_safe_summary(self):
        """안전 모드 결과 요약"""
        print("\n" + "="*60)
        print("KB생명 안전 모드 데이터 수집 결과")
        print("="*60)

        if not self.collected_data:
            print("수집된 데이터가 없습니다.")
            return

        print(f"총 수집 건수: {len(self.collected_data)}건")

        # 연령별 통계
        age_stats = {}
        for data in self.collected_data:
            age = data["age"]
            if age not in age_stats:
                age_stats[age] = []
            age_stats[age].append(data["monthly_premium"])

        print(f"\n연령별 평균 보험료:")
        for age in sorted(age_stats.keys()):
            premiums = [p for p in age_stats[age] if p > 0]
            if premiums:
                avg_premium = sum(premiums) / len(premiums)
                print(f"  {age}세: {avg_premium:,.0f}원 ({len(premiums)}건)")

        # 샘플 데이터
        print(f"\n수집된 데이터 샘플:")
        for i, data in enumerate(self.collected_data[:5], 1):
            print(f"  {i}. {data['age']}세 {data['gender_korean']} - {data['insurance_period']}/{data['payment_period']}: {data['monthly_premium']:,}원")

def main():
    """메인 함수"""
    collector = KBSafeModeCollector()
    collector.run_safe_collection()

if __name__ == "__main__":
    main()