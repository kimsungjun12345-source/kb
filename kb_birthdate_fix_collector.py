"""
KB생명 생년월일 입력 오류 해결 버전
다양한 생년월일 형식과 우회 방법을 시도하는 고급 수집기
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

class KBBirthdateFixCollector:
    """생년월일 입력 오류 해결 전문 수집기"""

    def __init__(self):
        # Windows 콘솔 인코딩 설정
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

        self.target_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.output_dir = Path("./outputs")
        self.output_dir.mkdir(exist_ok=True)

        # 테스트용 작은 범위
        self.test_ages = [25, 30, 35, 40, 45, 50]  # 6개 연령
        self.genders = ["male", "female"]
        self.gender_korean = {"male": "남자", "female": "여자"}

        # 수집된 데이터 저장
        self.collected_data = []

        # 다양한 생년월일 형식들 (KB생명 검증 우회용)
        self.birthdate_formats = [
            "yyyymmdd",    # 19940101
            "yyyy-mm-dd",  # 1994-01-01
            "yyyy.mm.dd",  # 1994.01.01
            "yyyy/mm/dd",  # 1994/01/01
            "yymmdd",      # 940101
        ]

        # 검증 통과 가능한 고정 생년월일들 (실제 유효한 날짜들)
        self.valid_birthdates = [
            "19940101",  # 1994년 1월 1일 (30세)
            "19900315",  # 1990년 3월 15일 (34세)
            "19850707",  # 1985년 7월 7일 (39세)
            "19800220",  # 1980년 2월 20일 (44세)
            "19750510",  # 1975년 5월 10일 (49세)
            "19700825",  # 1970년 8월 25일 (54세)
        ]

    def setup_browser(self):
        """브라우저 설정"""
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=False,
            slow_mo=800,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ]
        )

        self.context = self.browser.new_context()
        self.page = self.context.new_page()

        try:
            self.page.on("dialog", lambda d: d.accept())
        except Exception:
            pass

        print("생년월일 해결 전문 브라우저 설정 완료")

    def navigate_to_page(self):
        """페이지 이동"""
        print(f"페이지 이동: {self.target_url}")

        try:
            self.page.goto(self.target_url, wait_until='networkidle', timeout=60000)
            time.sleep(5)

            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            self.dismiss_all_modals()
            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def dismiss_all_modals(self):
        """모든 종류의 모달 강력 제거"""
        try:
            # 1. JavaScript로 직접 제거
            self.page.evaluate("""
                // 모든 모달 관련 요소 제거
                document.querySelectorAll('.modal, .popup, .alert, .overlay, .backdrop').forEach(el => {
                    el.style.display = 'none';
                    el.remove();
                });

                // systemAlert 특별 처리
                const systemAlert = document.getElementById('systemAlert1');
                if (systemAlert) systemAlert.remove();

                // z-index 높은 요소들 제거
                document.querySelectorAll('*').forEach(el => {
                    const style = window.getComputedStyle(el);
                    if (parseInt(style.zIndex) > 1000) {
                        el.style.display = 'none';
                    }
                });
            """)

            # 2. 버튼 클릭으로 정상 처리
            button_texts = ["확인", "동의", "예", "계속", "닫기", "취소", "아니오"]
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

            # 3. ESC 키 시도
            try:
                self.page.keyboard.press("Escape")
                time.sleep(1)
            except Exception:
                pass

        except Exception:
            pass

    def find_birthdate_input_advanced(self):
        """고급 생년월일 입력 필드 탐지"""
        print("  고급 생년월일 필드 탐색...")

        # 다양한 선택자들
        selectors = [
            'input[placeholder*="생년월일"]',
            'input[placeholder*="yyyymmdd"]',
            'input[placeholder*="YYYYMMDD"]',
            'input[name*="birth"]',
            'input[id*="birth"]',
            'input[name*="brth"]',
            'input[maxlength="8"]',
            'input[type="text"][maxlength="8"]',
            'input[pattern*="[0-9]"]',
            'input.birth-input',
            'input#birthDate',
            'input#birth_date',
        ]

        for selector in selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    # 필드 속성 확인
                    placeholder = element.get_attribute("placeholder") or ""
                    name = element.get_attribute("name") or ""
                    id_attr = element.get_attribute("id") or ""

                    print(f"  생년월일 필드 발견: {selector}")
                    print(f"    placeholder: {placeholder}")
                    print(f"    name: {name}")
                    print(f"    id: {id_attr}")

                    return element
            except Exception:
                continue

        return None

    def try_multiple_birthdate_formats(self, input_element, target_age):
        """다양한 생년월일 형식으로 시도"""
        print(f"  다양한 생년월일 형식으로 {target_age}세 입력 시도...")

        # 목표 나이에 맞는 연도 계산
        target_year = date.today().year - target_age

        # 시도할 형식들
        format_attempts = [
            f"{target_year:04d}0101",      # 20240101
            f"{target_year:04d}-01-01",    # 2024-01-01
            f"{target_year:04d}.01.01",    # 2024.01.01
            f"{target_year:04d}/01/01",    # 2024/01/01
            f"{target_year-2000:02d}0101", # 240101 (2자리 연도)
            f"{target_year:04d}1231",      # 20241231 (연말)
            f"{target_year:04d}0630",      # 20240630 (중간)
        ]

        # 미리 검증된 고정값들도 시도
        format_attempts.extend(self.valid_birthdates)

        for birthdate_str in format_attempts:
            try:
                print(f"    시도: {birthdate_str}")

                success = self.safe_input_birthdate(input_element, birthdate_str)

                if success:
                    # 입력 후 검증 오류 확인
                    time.sleep(2)

                    if not self.check_birthdate_error():
                        print(f"    성공: {birthdate_str}")
                        return birthdate_str
                    else:
                        print(f"    검증 실패: {birthdate_str}")
                        self.dismiss_all_modals()

            except Exception as e:
                print(f"    오류: {birthdate_str} - {e}")
                continue

        print("  모든 생년월일 형식 실패")
        return None

    def safe_input_birthdate(self, input_element, birthdate_str):
        """안전한 생년월일 입력"""
        try:
            # 기존 값 완전 삭제
            input_element.click(timeout=5000)
            time.sleep(0.5)

            # 다양한 삭제 방법
            try:
                input_element.press("Control+A")
                time.sleep(0.3)
                input_element.press("Delete")
                time.sleep(0.3)
            except Exception:
                pass

            try:
                input_element.press("Backspace+Backspace+Backspace+Backspace+Backspace+Backspace+Backspace+Backspace+Backspace+Backspace")
                time.sleep(0.3)
            except Exception:
                pass

            # fill() 방식
            input_element.fill(birthdate_str)
            time.sleep(0.5)

            # type() 방식으로 재시도
            input_element.type(birthdate_str, delay=50)
            time.sleep(0.5)

            # Tab으로 포커스 이동 (검증 트리거)
            try:
                input_element.press("Tab")
                time.sleep(1)
            except Exception:
                pass

            return True

        except Exception as e:
            print(f"      입력 실패: {e}")
            return False

    def check_birthdate_error(self):
        """생년월일 오류 메시지 확인"""
        try:
            # 오류 메시지들 확인
            error_patterns = [
                "생년월일",
                "올바르지",
                "유효",
                "형식",
                "잘못",
                "확인"
            ]

            # 페이지 텍스트에서 오류 메시지 찾기
            page_text = self.page.locator("body").inner_text(timeout=3000)

            for pattern in error_patterns:
                if pattern in page_text:
                    # 추가로 오류 관련 단어가 함께 있는지 확인
                    if any(error_word in page_text for error_word in ["오류", "에러", "error", "잘못", "올바르지"]):
                        return True

            # 모달이나 알림창 확인
            alert_elements = self.page.query_selector_all('.alert, .modal, .popup, .error')
            for alert in alert_elements:
                try:
                    if alert.is_visible():
                        alert_text = alert.inner_text()
                        if any(pattern in alert_text for pattern in error_patterns):
                            return True
                except Exception:
                    continue

            return False

        except Exception:
            return False

    def find_gender_selector_advanced(self):
        """고급 성별 선택자 탐지"""
        print("  고급 성별 선택자 탐색...")

        gender_elements = {"male": None, "female": None}

        # 라디오 버튼 방식
        try:
            radios = self.page.query_selector_all('input[type="radio"]')

            for radio in radios:
                if not radio.is_visible():
                    continue

                value = radio.get_attribute("value") or ""
                name = radio.get_attribute("name") or ""
                id_attr = radio.get_attribute("id") or ""

                # 근처 텍스트 확인
                try:
                    parent = radio.locator('xpath=./..')
                    if parent.count() > 0:
                        parent_text = parent.inner_text()
                    else:
                        parent_text = ""
                except Exception:
                    parent_text = ""

                # 남성 판단
                if (value in ["1", "M", "MALE", "남자", "남성"] or
                    "남" in name or "남" in id_attr or "남" in parent_text or
                    "male" in name.lower() or "male" in id_attr.lower()):
                    gender_elements["male"] = radio
                    print(f"    남성 라디오 발견: value={value}, name={name}")

                # 여성 판단
                elif (value in ["2", "F", "FEMALE", "여자", "여성"] or
                      "여" in name or "여" in id_attr or "여" in parent_text or
                      "female" in name.lower() or "female" in id_attr.lower()):
                    gender_elements["female"] = radio
                    print(f"    여성 라디오 발견: value={value}, name={name}")

        except Exception as e:
            print(f"  성별 선택자 탐색 실패: {e}")

        if gender_elements["male"] and gender_elements["female"]:
            print("  성별 선택자 탐지 성공")
            return gender_elements
        else:
            print("  성별 선택자 탐지 실패")
            return None

    def find_calculate_button_advanced(self):
        """고급 계산 버튼 탐지"""
        print("  고급 계산 버튼 탐색...")

        selectors = [
            'button:has-text("계산")',
            'button:has-text("조회")',
            'button:has-text("확인")',
            'button:has-text("보험료")',
            'input[type="submit"]',
            'input[value*="계산"]',
            'button[onclick*="calc"]',
            'button[onclick*="calculate"]',
            '.calc-btn',
            '.calculate-btn',
            '#calcBtn',
            '#calculateBtn'
        ]

        for selector in selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"  계산 버튼 발견: {selector}")
                    return element
            except Exception:
                continue

        print("  계산 버튼 탐지 실패")
        return None

    def safe_click_advanced(self, element, description="요소"):
        """고급 안전 클릭"""
        max_attempts = 5

        for attempt in range(max_attempts):
            try:
                print(f"  {description} 클릭 시도 {attempt + 1}/{max_attempts}")

                # 모달 제거
                self.dismiss_all_modals()
                time.sleep(1)

                # 스크롤해서 요소 보이게
                try:
                    element.scroll_into_view_if_needed()
                    time.sleep(0.5)
                except Exception:
                    pass

                # 다양한 클릭 방법 시도
                click_methods = [
                    lambda: element.click(timeout=5000, force=True),
                    lambda: self.page.evaluate("(element) => element.click()", element),
                    lambda: element.click(timeout=5000, force=False),
                ]

                for method in click_methods:
                    try:
                        method()
                        print(f"  {description} 클릭 성공")
                        time.sleep(2)
                        return True
                    except Exception as e:
                        print(f"    클릭 방법 실패: {e}")
                        time.sleep(1)
                        continue

            except Exception as e:
                print(f"  {description} 클릭 시도 실패: {e}")
                time.sleep(2)

        print(f"  {description} 클릭 완전 실패")
        return False

    def extract_premium_advanced(self):
        """고급 보험료 추출"""
        try:
            print("  고급 보험료 추출...")
            time.sleep(3)

            # 결과 영역으로 스크롤
            try:
                self.page.mouse.wheel(0, 500)
                time.sleep(2)
            except Exception:
                pass

            # 페이지 텍스트 수집
            body_text = ""
            try:
                body_text = self.page.locator("body").inner_text(timeout=20000)
            except Exception:
                try:
                    body_text = self.page.content()
                except Exception:
                    body_text = ""

            # 다양한 보험료 패턴
            premium_patterns = [
                r"월\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"월\s*납입보험료\s*[:：]\s*([\d,]+)\s*원",
                r"보험료\s*\(\s*월\s*\)\s*([\d,]+)\s*원",
                r"월\s*([\d,]{3,})\s*원",
                r"보험료\s*합계\s*[:：]\s*([\d,]+)\s*원",
                r"총\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"([\d,]{4,})\s*원/월",
                r"월\s*보험료\s*([\d,]+)\s*원",
            ]

            monthly_premium = 0
            found_pattern = ""

            for pattern in premium_patterns:
                matches = re.finditer(pattern, body_text)
                for match in matches:
                    try:
                        amount = int(match.group(1).replace(",", ""))
                        # 합리적인 보험료 범위 확인 (100원 ~ 100만원)
                        if 100 <= amount <= 1000000:
                            monthly_premium = amount
                            found_pattern = pattern
                            print(f"  보험료 발견: {monthly_premium:,}원 (패턴: {found_pattern[:30]})")
                            break
                    except (ValueError, IndexError):
                        continue
                if monthly_premium > 0:
                    break

            return {
                "monthly_premium": monthly_premium,
                "found_pattern": found_pattern,
                "raw_text": body_text[:2000]  # 처음 2000자만
            }

        except Exception as e:
            print(f"  보험료 추출 실패: {e}")
            return {"monthly_premium": 0, "error": str(e)}

    def collect_single_case_advanced(self, target_age, gender):
        """고급 단일 케이스 수집"""
        try:
            print(f"\n=== {target_age}세 {self.gender_korean[gender]} 수집 시작 ===")

            # 페이지 요소들 찾기
            birthdate_input = self.find_birthdate_input_advanced()
            if not birthdate_input:
                print("생년월일 입력 필드 없음")
                return None

            gender_selector = self.find_gender_selector_advanced()
            calc_button = self.find_calculate_button_advanced()

            if not calc_button:
                print("계산 버튼 없음")
                return None

            # 1. 생년월일 입력 (다양한 형식 시도)
            successful_birthdate = self.try_multiple_birthdate_formats(birthdate_input, target_age)
            if not successful_birthdate:
                print("모든 생년월일 형식 실패")
                return None

            # 2. 성별 선택
            if gender_selector and gender in gender_selector:
                if not self.safe_click_advanced(gender_selector[gender], f"성별({self.gender_korean[gender]})"):
                    print("성별 선택 실패")
                    # 계속 진행 (성별 선택이 없어도 될 수 있음)

            # 3. 계산 실행
            if not self.safe_click_advanced(calc_button, "계산 버튼"):
                print("계산 버튼 클릭 실패")
                return None

            # 4. 결과 추출
            result = self.extract_premium_advanced()

            if result and result["monthly_premium"] > 0:
                data = {
                    "age": target_age,
                    "gender": gender,
                    "gender_korean": self.gender_korean[gender],
                    "successful_birthdate": successful_birthdate,
                    "monthly_premium": result["monthly_premium"],
                    "found_pattern": result.get("found_pattern", ""),
                    "collected_at": datetime.now().isoformat()
                }

                print(f"=== 수집 성공: {result['monthly_premium']:,}원 ===")
                return data
            else:
                print("=== 수집 실패: 보험료 추출 안됨 ===")
                return None

        except Exception as e:
            print(f"=== 케이스 수집 오류: {e} ===")
            return None

    def run_advanced_collection(self):
        """고급 수집 실행"""
        print("KB생명 생년월일 오류 해결 전문 수집기 시작")
        print("="*70)

        try:
            # 브라우저 설정
            self.setup_browser()

            # 페이지 이동
            if not self.navigate_to_page():
                return False

            # 각 나이별로 수집 시도
            for age in self.test_ages:
                for gender in self.genders:
                    print(f"\n{'='*50}")
                    print(f"진행률: {len(self.collected_data)+1}/{len(self.test_ages)*len(self.genders)}")

                    data = self.collect_single_case_advanced(age, gender)

                    if data:
                        self.collected_data.append(data)
                        print(f"현재까지 수집: {len(self.collected_data)}건")

                    # 케이스 간 대기
                    print("케이스 간 대기...")
                    time.sleep(random.randint(15, 25))

                    # 페이지 새로고침 (안정성)
                    if len(self.collected_data) % 3 == 0 and len(self.collected_data) > 0:
                        print("안정성을 위한 페이지 새로고침...")
                        self.navigate_to_page()
                        time.sleep(5)

            # 결과 저장
            if self.collected_data:
                saved_file = self.save_advanced_data()
                self.print_advanced_summary()
                print(f"\n고급 수집 완료! 파일: {saved_file}")
                return True
            else:
                print("수집된 데이터 없음")
                return False

        except Exception as e:
            print(f"고급 수집기 실행 오류: {e}")
            return False

        finally:
            try:
                if hasattr(self, 'context'):
                    self.context.close()
                if hasattr(self, 'browser'):
                    self.browser.close()
                if hasattr(self, 'playwright'):
                    self.playwright.stop()
                print("브라우저 종료 완료")
            except Exception:
                pass

    def save_advanced_data(self):
        """고급 데이터 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        json_file = self.output_dir / f'kb_birthdate_fixed_data_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "birthdate_fixed_data": self.collected_data,
                "collection_info": {
                    "total_records": len(self.collected_data),
                    "method": "advanced_birthdate_fix",
                    "valid_birthdates_used": self.valid_birthdates,
                    "collected_at": timestamp
                }
            }, f, ensure_ascii=False, indent=2)

        csv_file = self.output_dir / f'kb_birthdate_fixed_data_{timestamp}.csv'
        if self.collected_data:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.collected_data[0].keys())
                writer.writeheader()
                writer.writerows(self.collected_data)

        print(f"\n고급 데이터 저장 완료:")
        print(f"  JSON: {json_file}")
        print(f"  CSV: {csv_file}")
        return json_file

    def print_advanced_summary(self):
        """고급 결과 요약"""
        print("\n" + "="*70)
        print("KB생명 생년월일 오류 해결 결과")
        print("="*70)

        if not self.collected_data:
            print("수집된 데이터가 없습니다.")
            return

        print(f"총 수집 건수: {len(self.collected_data)}건")

        # 사용된 생년월일별 통계
        birthdate_stats = {}
        for data in self.collected_data:
            bd = data["successful_birthdate"]
            if bd not in birthdate_stats:
                birthdate_stats[bd] = []
            birthdate_stats[bd].append(data["monthly_premium"])

        print(f"\n성공한 생년월일 형식:")
        for bd, premiums in birthdate_stats.items():
            valid_premiums = [p for p in premiums if p > 0]
            if valid_premiums:
                avg = sum(valid_premiums) / len(valid_premiums)
                print(f"  {bd}: {len(valid_premiums)}건, 평균 {avg:,.0f}원")

        # 데이터 샘플
        print(f"\n수집 성공 사례:")
        for i, data in enumerate(self.collected_data[:5], 1):
            print(f"  {i}. {data['age']}세 {data['gender_korean']} ({data['successful_birthdate']}): {data['monthly_premium']:,}원")

def main():
    """메인 함수"""
    collector = KBBirthdateFixCollector()
    collector.run_advanced_collection()

if __name__ == "__main__":
    main()