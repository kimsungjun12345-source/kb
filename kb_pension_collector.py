"""
KB생명 연금보험(ON_PD_YG_01) 전체 데이터 수집기
만 19-65세 연령별 4개 플랜 특약 가격, 물음표 도움말, 보험기간/납입기간 데이터 수집
"""

import sys
import json
import time
import random
import re
import csv
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime
from datetime import date

class KBPensionDataCollector:
    """KB생명 연금보험 전체 데이터 수집기"""

    def __init__(self):
        # Windows 콘솔 인코딩 설정
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

        # 타겟 URL
        self.target_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

        # 출력 디렉토리 설정
        self.output_dir = Path("./outputs")
        self.output_dir.mkdir(exist_ok=True)
        self.debug_dir = self.output_dir / "debug"
        self.debug_dir.mkdir(exist_ok=True)

        # 수집 범위
        self.age_range = range(19, 66)  # 19세 ~ 65세
        self.genders = ["male", "female"]  # 남자, 여자
        self.gender_korean = {"male": "남자", "female": "여자"}

        # 4개 플랜 (실제 페이지에서 확인 필요)
        self.plans = [
            {"id": "plan1", "name": "종합플랜(든든)", "selector": None},
            {"id": "plan2", "name": "종합플랜(실속)", "selector": None},
            {"id": "plan3", "name": "뇌심플랜", "selector": None},
            {"id": "plan4", "name": "입원간병플랜", "selector": None}
        ]

        # 결과 저장
        self.collected_data = []
        self.help_text_data = []
        self.period_data = []

    def setup_browser(self):
        """브라우저 설정"""
        self.playwright = sync_playwright().start()

        self.browser = self.playwright.chromium.launch(
            headless=False,
            slow_mo=200,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        self.context = self.browser.new_context()
        self.page = self.context.new_page()

        # JS dialog 자동 수락
        try:
            self.page.on("dialog", lambda d: d.accept())
        except Exception:
            pass

        print("브라우저 설정 완료")

    def human_pause(self, a: int = 200, b: int = 500):
        """사람처럼 대기"""
        try:
            self.page.wait_for_timeout(random.randint(a, b))
        except Exception:
            pass

    def human_click(self, locator, label: str = "", timeout: int = 8000) -> bool:
        """사람처럼 클릭"""
        try:
            self.dismiss_blocking_modal()
            locator.scroll_into_view_if_needed(timeout=timeout)
            self.human_pause()
            try:
                locator.hover(timeout=timeout)
            except Exception:
                pass
            self.human_pause(100, 300)
            locator.click(timeout=timeout, force=True)
            if label:
                print(f"  -> 클릭: {label}")
            self.human_pause(300, 700)
            self.dismiss_blocking_modal()
            return True
        except Exception as e:
            if label:
                print(f"  -> 클릭 실패({label}): {e}")
            return False

    def save_debug_snapshot(self, tag: str):
        """디버그 스냅샷 저장"""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            png = self.debug_dir / f"{tag}_{ts}.png"
            html = self.debug_dir / f"{tag}_{ts}.html"
            self.page.screenshot(path=str(png), full_page=True)
            html.write_text(self.page.content(), encoding="utf-8")
            print(f"디버그 스냅샷 저장: {png.name}")
        except Exception:
            pass

    def navigate_to_pension_page(self):
        """연금보험 상품 페이지로 이동"""
        print(f"KB생명 연금보험 페이지 이동: {self.target_url}")

        try:
            self.page.goto(self.target_url, wait_until='networkidle', timeout=30000)
            self.page.wait_for_timeout(3000)

            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            self.dismiss_blocking_modal()
            self.save_debug_snapshot("pension_page_loaded")
            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def dismiss_blocking_modal(self):
        """블로킹 모달 제거"""
        try:
            # 일반적인 모달 닫기
            modal_selectors = [
                "section.modal.alert.open",
                ".modal.open",
                ".popup.open",
                ".alert.open"
            ]

            for selector in modal_selectors:
                modals = self.page.locator(selector)
                if modals.count() > 0:
                    close_buttons = [
                        modals.locator('button:has-text("확인")'),
                        modals.locator('button:has-text("동의")'),
                        modals.locator('button:has-text("닫기")'),
                        modals.locator('button:has-text("계속")'),
                        modals.locator('.close, .btn-close')
                    ]

                    for btn in close_buttons:
                        try:
                            if btn.count() > 0 and btn.is_visible():
                                btn.click(timeout=1000)
                                self.page.wait_for_timeout(200)
                                break
                        except Exception:
                            continue

            # 전역 확인/동의 버튼
            global_buttons = [
                'button:has-text("확인")',
                'button:has-text("동의")',
                'button:has-text("계속")',
                'button:has-text("닫기")'
            ]

            for selector in global_buttons:
                try:
                    btn = self.page.locator(selector).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=500, force=True)
                        self.page.wait_for_timeout(200)
                except Exception:
                    continue

        except Exception:
            pass

    def find_age_birth_input(self):
        """나이 또는 생년월일 입력 필드 찾기"""
        # 생년월일 입력 필드 우선 탐색
        birth_selectors = [
            'input[placeholder*="생년월일"]',
            'input[placeholder*="yyyymmdd"]',
            'input[placeholder*="YYYYMMDD"]',
            'input[name*="birth"]',
            'input[id*="birth"]',
            'input[name*="brth"]',
            'input[maxlength="8"]'
        ]

        for selector in birth_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"생년월일 입력 필드 발견: {selector}")
                    return element, "birth"
            except Exception:
                continue

        # 나이 입력 필드 탐색
        age_selectors = [
            'input[placeholder*="나이"]',
            'input[placeholder*="연령"]',
            'input[name*="age"]',
            'input[id*="age"]',
            'input[type="number"]'
        ]

        for selector in age_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"나이 입력 필드 발견: {selector}")
                    return element, "age"
            except Exception:
                continue

        return None, None

    def find_gender_selector(self):
        """성별 선택 요소 찾기"""
        gender_elements = {}

        # 다양한 성별 선택 방식 탐색
        gender_selectors = [
            'input[name*="gender"]',
            'button:has-text("남자")',
            'button:has-text("여자")',
            'label:has-text("남자")',
            'label:has-text("여자")',
            'input[value*="M"]',
            'input[value*="F"]'
        ]

        for selector in gender_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        text = element.inner_text().strip()
                        value = element.get_attribute("value") or ""

                        if "남자" in text or "남성" in text or "M" in value:
                            gender_elements["male"] = element
                        elif "여자" in text or "여성" in text or "F" in value:
                            gender_elements["female"] = element
            except Exception:
                continue

        if gender_elements:
            print(f"성별 선택 요소 발견: {len(gender_elements)}개")
            return gender_elements

        return None

    def find_plan_selectors(self):
        """4개 플랜 선택 요소 찾기"""
        plan_elements = {}

        # 플랜 선택 방법 탐색 (라디오버튼, 탭, 드롭다운 등)
        plan_keywords = ["종합플랜", "뇌심플랜", "입원간병플랜", "든든", "실속"]

        for keyword in plan_keywords:
            try:
                # 라디오버튼 형태
                radio_elements = self.page.query_selector_all(f'input[type="radio"]:near(text="{keyword}")')
                for element in radio_elements:
                    if element.is_visible():
                        plan_elements[keyword] = element

                # 버튼/탭 형태
                button_elements = self.page.query_selector_all(f'button:has-text("{keyword}"), a:has-text("{keyword}")')
                for element in button_elements:
                    if element.is_visible():
                        plan_elements[keyword] = element

            except Exception:
                continue

        if plan_elements:
            print(f"플랜 선택 요소 발견: {list(plan_elements.keys())}")

        return plan_elements

    def find_rider_checkboxes(self):
        """특약 체크박스들 찾기"""
        rider_elements = []

        try:
            # 특약 관련 체크박스 탐색
            checkbox_selectors = [
                'input[type="checkbox"]',
                'input[name*="rider"]',
                'input[name*="특약"]'
            ]

            for selector in checkbox_selectors:
                checkboxes = self.page.query_selector_all(selector)
                for checkbox in checkboxes:
                    if checkbox.is_visible():
                        # 특약명 찾기 (근처 label이나 텍스트)
                        try:
                            label_element = checkbox.locator('xpath=./following-sibling::label[1] | ./preceding-sibling::label[1] | ./parent::label')
                            if label_element.count() > 0:
                                rider_name = label_element.inner_text().strip()
                            else:
                                # 근처 텍스트 노드에서 특약명 추출
                                parent = checkbox.locator('xpath=./..')
                                rider_name = parent.inner_text().strip()[:100]

                            if rider_name and ("특약" in rider_name or "보장" in rider_name):
                                rider_elements.append({
                                    "name": rider_name,
                                    "checkbox": checkbox,
                                    "checked": checkbox.is_checked()
                                })

                        except Exception:
                            continue

            print(f"특약 체크박스 발견: {len(rider_elements)}개")

        except Exception as e:
            print(f"특약 체크박스 탐색 실패: {e}")

        return rider_elements

    def find_help_buttons(self):
        """물음표(?) 도움말 버튼들 찾기"""
        help_buttons = []

        try:
            # 도움말 버튼 선택자들
            help_selectors = [
                'button:has-text("?")',
                'a:has-text("?")',
                'span:has-text("?")',
                '.help-btn',
                '.question-btn',
                'button[title*="도움말"]',
                'a[title*="도움말"]'
            ]

            for selector in help_selectors:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        # 근처 텍스트로 어떤 항목의 도움말인지 파악
                        try:
                            context_text = ""
                            parent = element.locator('xpath=./..')
                            if parent.count() > 0:
                                context_text = parent.inner_text().strip()[:200]

                            help_buttons.append({
                                "element": element,
                                "context": context_text,
                                "selector": selector
                            })

                        except Exception:
                            help_buttons.append({
                                "element": element,
                                "context": "Unknown",
                                "selector": selector
                            })

            print(f"도움말 버튼 발견: {len(help_buttons)}개")

        except Exception as e:
            print(f"도움말 버튼 탐색 실패: {e}")

        return help_buttons

    def find_period_selectors(self):
        """보험기간/납입기간 선택 요소 찾기"""
        period_elements = {}

        try:
            # 보험기간 관련
            insurance_period_selectors = [
                'select[name*="보험기간"]',
                'select[name*="insurance"]',
                'select[name*="period"]',
                'select:near(text="보험기간")'
            ]

            for selector in insurance_period_selectors:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        period_elements["insurance_period"] = element
                        break

            # 납입기간 관련
            payment_period_selectors = [
                'select[name*="납입기간"]',
                'select[name*="payment"]',
                'select[name*="premium"]',
                'select:near(text="납입기간")'
            ]

            for selector in payment_period_selectors:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        period_elements["payment_period"] = element
                        break

            print(f"기간 선택 요소 발견: {list(period_elements.keys())}")

        except Exception as e:
            print(f"기간 선택 요소 탐색 실패: {e}")

        return period_elements

    def find_calculate_button(self):
        """계산 버튼 찾기"""
        calc_selectors = [
            'button:has-text("계산")',
            'button:has-text("조회")',
            'button:has-text("확인")',
            'button:has-text("보험료")',
            'input[type="submit"]',
            'input[value*="계산"]'
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

    def collect_help_text(self, help_buttons):
        """도움말 텍스트 수집"""
        print("도움말 텍스트 수집 중...")

        for i, help_info in enumerate(help_buttons):
            try:
                print(f"  도움말 {i+1}/{len(help_buttons)} 수집 중...")

                # 도움말 버튼 클릭
                help_element = help_info["element"]
                if self.human_click(help_element, f"도움말 버튼 {i+1}"):
                    self.page.wait_for_timeout(1000)

                    # 도움말 모달/팝업 텍스트 수집
                    help_text = ""
                    try:
                        # 모달 창에서 텍스트 추출
                        modal_selectors = [
                            ".modal.open",
                            ".popup.open",
                            ".tooltip.open",
                            ".help-content"
                        ]

                        for selector in modal_selectors:
                            modal = self.page.locator(selector)
                            if modal.count() > 0 and modal.is_visible():
                                help_text = modal.inner_text()
                                break

                        if not help_text:
                            # 페이지 전체에서 새로 나타난 텍스트 찾기
                            self.page.wait_for_timeout(500)
                            help_text = "도움말 텍스트 추출 실패"

                    except Exception:
                        help_text = "도움말 텍스트 추출 오류"

                    self.help_text_data.append({
                        "context": help_info["context"],
                        "help_text": help_text.strip(),
                        "collected_at": datetime.now().isoformat()
                    })

                    # 도움말 창 닫기
                    self.dismiss_blocking_modal()
                    self.page.wait_for_timeout(500)

            except Exception as e:
                print(f"  도움말 {i+1} 수집 실패: {e}")
                continue

    def collect_single_case_data(self, age, gender, plan_name, age_input, input_type, gender_selector, plan_selector, rider_checkboxes):
        """단일 케이스 데이터 수집 (나이+성별+플랜+특약조합)"""
        try:
            print(f"    수집 중: {age}세 {self.gender_korean[gender]} {plan_name}")

            # 1. 나이/생년월일 입력
            self.dismiss_blocking_modal()
            if input_type == "birth":
                birthdate = self.yyyymmdd_for_age(age)
                age_input.fill(birthdate)
                print(f"      생년월일 입력: {birthdate}")
            else:
                age_input.fill(str(age))
                print(f"      나이 입력: {age}")

            self.page.wait_for_timeout(500)

            # 2. 성별 선택
            if gender_selector and gender in gender_selector:
                self.dismiss_blocking_modal()
                gender_selector[gender].click()
                print(f"      성별 선택: {self.gender_korean[gender]}")
                self.page.wait_for_timeout(500)

            # 3. 플랜 선택
            if plan_selector:
                self.dismiss_blocking_modal()
                plan_selector.click()
                print(f"      플랜 선택: {plan_name}")
                self.page.wait_for_timeout(1000)

            # 4. 특약 조합별 데이터 수집
            # 일단 모든 특약 OFF 상태에서 기본 가격 수집
            for rider in rider_checkboxes:
                if rider["checkbox"].is_checked():
                    rider["checkbox"].uncheck()

            self.page.wait_for_timeout(500)

            # 기본 계산 (특약 없음)
            base_result = self.calculate_and_extract_result("기본")

            if base_result:
                base_data = {
                    "age": age,
                    "gender": gender,
                    "gender_korean": self.gender_korean[gender],
                    "plan": plan_name,
                    "rider_combination": "기본",
                    "monthly_premium": base_result.get("monthly_premium", 0),
                    "calculation_details": base_result.get("details", {}),
                    "collected_at": datetime.now().isoformat()
                }
                self.collected_data.append(base_data)

            # 특약별 개별 추가 계산 (주요 특약들만)
            important_riders = [r for r in rider_checkboxes[:10]]  # 처음 10개만

            for rider in important_riders:
                try:
                    # 해당 특약만 체크
                    for r in rider_checkboxes:
                        if r["checkbox"].is_checked():
                            r["checkbox"].uncheck()

                    rider["checkbox"].check()
                    self.page.wait_for_timeout(300)

                    # 계산
                    rider_result = self.calculate_and_extract_result(rider["name"])

                    if rider_result:
                        rider_data = {
                            "age": age,
                            "gender": gender,
                            "gender_korean": self.gender_korean[gender],
                            "plan": plan_name,
                            "rider_combination": rider["name"],
                            "monthly_premium": rider_result.get("monthly_premium", 0),
                            "calculation_details": rider_result.get("details", {}),
                            "collected_at": datetime.now().isoformat()
                        }
                        self.collected_data.append(rider_data)

                    # 특약 다시 해제
                    rider["checkbox"].uncheck()

                except Exception as e:
                    print(f"      특약 {rider['name']} 처리 실패: {e}")
                    continue

            return True

        except Exception as e:
            print(f"    데이터 수집 실패: {e}")
            return False

    def calculate_and_extract_result(self, combination_name):
        """계산 실행 및 결과 추출"""
        try:
            # 계산 버튼 클릭
            calc_button = self.find_calculate_button()
            if not calc_button:
                print("      계산 버튼을 찾을 수 없음")
                return None

            self.dismiss_blocking_modal()
            calc_button.click()
            self.page.wait_for_timeout(2000)
            self.dismiss_blocking_modal()

            # 결과 추출
            result = self.extract_premium_result()

            if result:
                print(f"      {combination_name}: {result.get('monthly_premium', 0)}원")
                return result
            else:
                print(f"      {combination_name}: 결과 추출 실패")
                return None

        except Exception as e:
            print(f"      계산 실행 실패: {e}")
            return None

    def extract_premium_result(self):
        """보험료 계산 결과 추출"""
        try:
            self.page.wait_for_timeout(1000)

            # 결과 영역 스크롤
            try:
                self.page.mouse.wheel(0, 500)
            except Exception:
                pass

            # 페이지 텍스트 수집
            body_text = ""
            try:
                body_text = self.page.locator("body").inner_text(timeout=10000)
            except Exception:
                body_text = self.page.content()

            # 보험료 금액 추출
            premium_patterns = [
                r"월\s*보험료\s*[:：]\s*([\d,]+)\s*원",
                r"월\s*납입보험료\s*[:：]\s*([\d,]+)\s*원",
                r"보험료\s*\(\s*월\s*\)\s*([\d,]+)\s*원",
                r"월\s*([\d,]{3,})\s*원"
            ]

            monthly_premium = 0
            for pattern in premium_patterns:
                match = re.search(pattern, body_text)
                if match:
                    try:
                        monthly_premium = int(match.group(1).replace(",", ""))
                        break
                    except ValueError:
                        continue

            # 추가 상세 정보 추출
            details = {
                "raw_text": body_text[:5000],  # 처음 5000자만
                "extraction_patterns_found": []
            }

            # 보험기간, 납입기간 정보
            period_patterns = {
                "insurance_period": r"보험기간\s*[:：]\s*([^\n]+)",
                "payment_period": r"납입기간\s*[:：]\s*([^\n]+)",
                "payment_cycle": r"납입주기\s*[:：]\s*([^\n]+)"
            }

            for key, pattern in period_patterns.items():
                match = re.search(pattern, body_text)
                if match:
                    details[key] = match.group(1).strip()[:100]
                    details["extraction_patterns_found"].append(key)

            if monthly_premium > 0:
                return {
                    "monthly_premium": monthly_premium,
                    "details": details
                }

            return None

        except Exception as e:
            print(f"결과 추출 오류: {e}")
            return None

    def collect_all_data(self):
        """전체 데이터 수집 실행"""
        print(f"\n전체 데이터 수집 시작")
        print(f"대상: {len(self.age_range)}개 연령 × {len(self.genders)}개 성별 × 4개 플랜")

        try:
            # 페이지 요소들 찾기
            age_input, input_type = self.find_age_birth_input()
            gender_selector = self.find_gender_selector()
            plan_selectors = self.find_plan_selectors()
            rider_checkboxes = self.find_rider_checkboxes()
            help_buttons = self.find_help_buttons()

            if not age_input:
                print("나이/생년월일 입력 필드를 찾을 수 없습니다.")
                return False

            # 도움말 텍스트 수집
            if help_buttons:
                self.collect_help_text(help_buttons)

            # 연령별/성별/플랜별 데이터 수집
            total_cases = len(self.age_range) * len(self.genders) * len(plan_selectors)
            current_case = 0

            for age in self.age_range:
                for gender in self.genders:
                    for plan_name, plan_selector in plan_selectors.items():
                        current_case += 1
                        print(f"\n진행률: {current_case}/{total_cases}")

                        success = self.collect_single_case_data(
                            age, gender, plan_name,
                            age_input, input_type,
                            gender_selector, plan_selector,
                            rider_checkboxes
                        )

                        if not success:
                            print(f"    케이스 수집 실패, 다음으로 진행")

                        # 페이지 리로드 (안정성을 위해)
                        if current_case % 20 == 0:  # 20케이스마다
                            print("    페이지 리로드 중...")
                            self.navigate_to_pension_page()
                            age_input, input_type = self.find_age_birth_input()
                            gender_selector = self.find_gender_selector()
                            plan_selectors = self.find_plan_selectors()
                            rider_checkboxes = self.find_rider_checkboxes()

            print(f"\n전체 데이터 수집 완료: {len(self.collected_data)}건")
            return True

        except Exception as e:
            print(f"전체 데이터 수집 실패: {e}")
            return False

    def save_collected_data(self):
        """수집된 데이터 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # JSON 저장
        json_file = self.output_dir / f'kb_pension_data_{timestamp}.json'
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump({
                "main_data": self.collected_data,
                "help_text": self.help_text_data,
                "collection_summary": {
                    "total_records": len(self.collected_data),
                    "age_range": f"{min(self.age_range)}-{max(self.age_range)}",
                    "genders": self.genders,
                    "collected_at": timestamp
                }
            }, f, ensure_ascii=False, indent=2)

        # CSV 저장 (메인 데이터)
        csv_file = self.output_dir / f'kb_pension_data_{timestamp}.csv'
        if self.collected_data:
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.collected_data[0].keys())
                writer.writeheader()
                writer.writerows(self.collected_data)

        # 도움말 CSV 저장
        help_csv_file = self.output_dir / f'kb_pension_help_{timestamp}.csv'
        if self.help_text_data:
            with open(help_csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.help_text_data[0].keys())
                writer.writeheader()
                writer.writerows(self.help_text_data)

        print(f"\n데이터 저장 완료:")
        print(f"  JSON: {json_file}")
        print(f"  CSV: {csv_file}")
        print(f"  도움말: {help_csv_file}")

        return json_file

    def run_collection(self):
        """메인 수집 실행"""
        print("KB생명 연금보험 전체 데이터 수집기 시작")
        print("="*60)

        try:
            # 1. 브라우저 설정
            self.setup_browser()

            # 2. 페이지 이동
            if not self.navigate_to_pension_page():
                print("페이지 이동 실패")
                return False

            # 3. 전체 데이터 수집
            success = self.collect_all_data()

            if success:
                # 4. 데이터 저장
                saved_file = self.save_collected_data()

                # 5. 요약 출력
                self.print_collection_summary()

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

    def print_collection_summary(self):
        """수집 결과 요약 출력"""
        print("\n" + "="*60)
        print("KB생명 연금보험 데이터 수집 결과 요약")
        print("="*60)

        print(f"메인 데이터: {len(self.collected_data)}건")
        print(f"도움말 데이터: {len(self.help_text_data)}건")

        if self.collected_data:
            # 연령별 통계
            age_stats = {}
            for data in self.collected_data:
                age = data["age"]
                if age not in age_stats:
                    age_stats[age] = 0
                age_stats[age] += 1

            print(f"\n연령별 수집 건수:")
            for age in sorted(age_stats.keys())[:10]:  # 처음 10개 연령만
                print(f"  {age}세: {age_stats[age]}건")

            if len(age_stats) > 10:
                print(f"  ... 외 {len(age_stats)-10}개 연령")

            # 플랜별 통계
            plan_stats = {}
            for data in self.collected_data:
                plan = data["plan"]
                if plan not in plan_stats:
                    plan_stats[plan] = 0
                plan_stats[plan] += 1

            print(f"\n플랜별 수집 건수:")
            for plan, count in plan_stats.items():
                print(f"  {plan}: {count}건")

def main():
    """메인 함수"""
    collector = KBPensionDataCollector()
    collector.run_collection()

if __name__ == "__main__":
    main()