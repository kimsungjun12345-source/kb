"""
KB 딱좋은 e-건강보험 나이/성별별 보험료 테이블 스크래퍼
보험가격공시실에서 20-64세 남녀 보험료를 체계적으로 수집
"""

import sys
import json
import time
import random
import re
from pathlib import Path
from playwright.sync_api import sync_playwright
from datetime import datetime
from datetime import date

class KBHealthInsurancePriceScraper:
    """KB 딱좋은 e-건강보험 보험료 테이블 스크래퍼"""

    def __init__(self):
        # Windows 콘솔(cp949)에서 NBSP(\\xa0) 등 출력 시 깨지는 문제 방지
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

        self.price_office_url = "https://www.kblife.co.kr/customer-common/insurancePricePublicNoticeOffice.do"
        self.output_dir = Path("./outputs")
        self.output_dir.mkdir(exist_ok=True)
        self.debug_dir = self.output_dir / "debug"
        self.debug_dir.mkdir(exist_ok=True)

        # 수집할 조건
        self.age_range = range(20, 65)  # 20세 ~ 64세
        self.genders = ["male", "female"]  # 남자, 여자
        self.gender_korean = {"male": "남자", "female": "여자"}
        self.birth_mmdd = "0101"  # yyyymmdd 입력이 필요할 때 사용할 기본 월/일

        # 결과 저장
        self.price_data = []

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
        # JS dialog(alert/confirm/prompt) 자동 수락
        try:
            self.page.on("dialog", lambda d: d.accept())
        except Exception:
            pass
        print("브라우저 설정 완료")

    def human_pause(self, a: int = 250, b: int = 650):
        """사람처럼 짧게 멈춤(ms)"""
        try:
            self.page.wait_for_timeout(random.randint(a, b))
        except Exception:
            pass

    def human_click(self, locator, label: str = "", timeout: int = 8000) -> bool:
        """스크롤/호버/클릭을 사람처럼 수행 + 팝업 정리"""
        try:
            self.dismiss_blocking_modal()
            locator.scroll_into_view_if_needed(timeout=timeout)
            self.human_pause()
            try:
                locator.hover(timeout=timeout)
            except Exception:
                pass
            self.human_pause(120, 350)
            locator.click(timeout=timeout, force=True)
            if label:
                print(f"  -> 클릭: {label}")
            self.human_pause(350, 900)
            self.dismiss_blocking_modal()
            return True
        except Exception as e:
            if label:
                print(f"  -> 클릭 실패({label}): {e}")
            return False

    def save_debug_snapshot(self, tag: str):
        """현재 페이지 상태를 스크린샷/HTML로 저장"""
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            png = self.debug_dir / f"{tag}_{ts}.png"
            html = self.debug_dir / f"{tag}_{ts}.html"
            self.page.screenshot(path=str(png), full_page=True)
            html.write_text(self.page.content(), encoding="utf-8")
            print(f"디버그 스냅샷 저장: {png.name}")
        except Exception:
            pass

    def navigate_to_price_office(self):
        """보험가격공시실로 이동"""
        print(f"보험가격공시실 이동: {self.price_office_url}")

        try:
            self.page.goto(self.price_office_url, wait_until='networkidle', timeout=30000)
            self.page.wait_for_timeout(3000)

            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def find_health_insurance_calculator(self):
        """KB 딱좋은 e-건강보험 보험료 계산기 찾기"""
        print("\n보험료 계산기 탐색 중...")

        try:
            # 목표 상품 행에서 "보험료 계산" 버튼을 우선 탐색
            target_keywords = [
                "KB 딱좋은 e-건강보험",
                "딱좋은 e-건강보험",
            ]
            for keyword in target_keywords:
                row = self.page.locator("tr", has_text=keyword).first
                if row.count() > 0:
                    calc_in_row = row.locator("a, button", has_text="보험료 계산").first
                    if calc_in_row.count() > 0:
                        print(f"목표 상품 계산 버튼 발견: {keyword}")
                        return calc_in_row
                # 표 구조가 아닐 때: 키워드 근처의 "보험료 계산" 링크를 XPath로 탐색
                near_calc = self.page.locator(
                    f"xpath=//*[contains(normalize-space(.), '{keyword}')]/following::a[contains(., '보험료 계산')][1]"
                ).first
                if near_calc.count() > 0:
                    print(f"키워드 근처 계산 링크 발견: {keyword}")
                    return near_calc

            # 다양한 방법으로 건강보험 계산 버튼 찾기
            calculator_selectors = [
                'button:has-text("딱좋은")',
                'a:has-text("딱좋은")',
                'button:has-text("건강보험")',
                'a:has-text("건강보험")',
                'button:has-text("e-건강")',
                'a:has-text("e-건강")',
                '[onclick*="건강"]',
                '[onclick*="딱좋은"]',
                '.calculator-btn',
                '.price-calc-btn'
            ]

            for selector in calculator_selectors:
                try:
                    elements = self.page.query_selector_all(selector)
                    for element in elements:
                        if element.is_visible():
                            text = element.inner_text().strip()
                            if any(keyword in text for keyword in ['딱좋은', 'e-건강', '건강보험']):
                                print(f"계산기 버튼 발견: {text}")
                                return element
                except:
                    continue

            # 페이지에서 관련 링크 직접 찾기
            print("직접 탐색으로 전환...")
            self.explore_page_for_calculator()

            return None

        except Exception as e:
            print(f"계산기 탐색 실패: {e}")
            return None

    def explore_page_for_calculator(self):
        """페이지 전체 탐색하여 계산기 찾기"""
        try:
            # 페이지의 모든 버튼/링크 텍스트 확인
            all_buttons = self.page.query_selector_all('button, a, span, div')

            health_related = []
            for element in all_buttons[:100]:  # 처음 100개만 확인
                try:
                    text = element.inner_text().strip()
                    if any(keyword in text for keyword in ['건강', '보험료', '계산', '딱좋은', 'e-건강']):
                        health_related.append(text)
                except:
                    continue

            if health_related:
                print("건강보험 관련 요소들:")
                for i, text in enumerate(health_related[:10], 1):
                    compact = " ".join(text.split())
                    if len(compact) > 120:
                        compact = compact[:120] + "..."
                    print(f"  {i}. {compact}")

        except Exception as e:
            print(f"페이지 탐색 중 오류: {e}")

    def access_calculator_directly(self):
        """계산기에 직접 접근하는 대안 방법"""
        print("\n대안 방법: 직접 계산기 접근...")

        try:
            # KB라이프 건강보험 상품 페이지로 이동 후 계산기 찾기
            product_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

            print(f"상품 페이지로 이동: {product_url}")
            moved = False
            for _ in range(3):
                try:
                    self.page.goto(product_url, wait_until='domcontentloaded', timeout=30000)
                    self.page.wait_for_load_state("networkidle", timeout=20000)
                    self.page.wait_for_timeout(1500)
                    self.dismiss_blocking_modal()
                    moved = True
                    break
                except Exception:
                    self.page.wait_for_timeout(1200)
                    continue
            if not moved:
                print("상품 페이지 이동 재시도 실패")
                return None
            self.save_debug_snapshot("product_page")

            # 사람처럼 스크롤하면서 "예상보험료 계산" 계열 버튼 찾기/클릭
            candidates = [
                ('button:has-text("예상보험료")', "예상보험료 버튼(button)"),
                ('a:has-text("예상보험료")', "예상보험료 버튼(a)"),
                ('text=/예상\\s*보험료\\s*계산/i', "예상보험료 계산 텍스트"),
                ('button:has-text("보험료 계산")', "보험료 계산(button)"),
                ('a:has-text("보험료 계산")', "보험료 계산(a)"),
                ('button:has-text("계산")', "계산(button)"),
                ('a:has-text("계산")', "계산(a)"),
            ]

            # 최대 3번: 스크롤 다운 -> 후보 클릭 시도
            for attempt in range(3):
                self.dismiss_blocking_modal()
                for selector, label in candidates:
                    try:
                        loc = self.page.locator(selector).first
                        if loc.count() > 0 and loc.is_visible():
                            if self.human_click(loc, label=label):
                                return loc
                    except Exception:
                        continue

                # 더 아래로 내려서 로딩/지연요소 노출
                try:
                    self.page.mouse.wheel(0, 900)
                except Exception:
                    pass
                self.human_pause(600, 1200)
                if attempt == 1:
                    self.save_debug_snapshot("product_scroll")

            return None

        except Exception as e:
            print(f"직접 접근 실패: {e}")
            return None

    def interact_with_calculator(self, calculator_element):
        """계산기와 상호작용하여 보험료 수집"""
        print("\n보험료 계산기와 상호작용 시작...")

        try:
            # 계산기 버튼 클릭
            current_pages = list(self.context.pages)
            clicked = False
            try:
                # locator/elementhandle 공통 처리
                clicked = self.human_click(calculator_element, label="계산기 진입 버튼")
            except Exception:
                try:
                    calculator_element.click(timeout=8000, force=True)
                    clicked = True
                except Exception:
                    clicked = False
            if not clicked:
                print("계산기 진입 버튼 클릭 실패")
                self.save_debug_snapshot("enter_calc_fail")
                return False
            self.page.wait_for_timeout(3000)
            # 새 탭/팝업이 열렸다면 해당 페이지로 전환
            if len(self.context.pages) > len(current_pages):
                self.page = self.context.pages[-1]
                self.page.wait_for_timeout(2000)
                print("새 탭으로 전환 완료")

            print("계산기 모달/페이지 로딩 중...")

            # 생년월일(yyyymmdd) 또는 나이 입력 필드 찾기
            age_input = None
            birthdate_input = self.find_birthdate_input()
            if not birthdate_input:
                age_input = self.find_age_input()
            gender_selector = self.find_gender_selector()

            if not birthdate_input and not age_input:
                print("생년월일/나이 입력 필드를 찾을 수 없습니다.")
                return False

            return self.collect_premium_data(age_input, gender_selector, birthdate_input=birthdate_input)

        except Exception as e:
            print(f"계산기 상호작용 실패: {e}")
            return False

    def yyyymmdd_for_age(self, age: int) -> str:
        """나이에 맞는 yyyymmdd 문자열 생성(월/일은 고정)"""
        year = date.today().year - age
        return f"{year:04d}{self.birth_mmdd}"

    def yyyymmdd_for_age_variant(self, age: int, year_delta: int) -> str:
        """보험나이/만나이 차이 등을 고려해 출생년도 ± 보정"""
        year = date.today().year - age + year_delta
        return f"{year:04d}{self.birth_mmdd}"

    def get_system_alert_text(self) -> str:
        """열려있는 시스템 알림 모달 텍스트(있으면)"""
        try:
            modal = self.page.locator("section.modal.alert.open").first
            if modal.count() > 0 and modal.is_visible():
                return " ".join(modal.inner_text().split())
        except Exception:
            pass
        return ""

    def fill_birthdate_humanlike(self, birthdate_input, birthdate: str) -> None:
        """마스킹 입력 대응: 타이핑 + blur로 이벤트 확실히 발생"""
        self.dismiss_blocking_modal()
        birthdate_input.click(timeout=5000, force=True)
        try:
            birthdate_input.press("Control+A", timeout=1000)
        except Exception:
            pass
        try:
            birthdate_input.press("Backspace", timeout=1000)
        except Exception:
            pass
        # type()가 마스킹/검증에 더 잘 걸리는 경우가 많음
        birthdate_input.type(birthdate, delay=30, timeout=8000)
        try:
            birthdate_input.press("Tab", timeout=1000)
        except Exception:
            pass

    def find_birthdate_input(self):
        """생년월일(yyyymmdd) 입력 필드 찾기"""
        birth_selectors = [
            'input[placeholder*="yyyymmdd"]',
            'input[placeholder*="YYYYMMDD"]',
            'input[placeholder*="생년월일"]',
            'input[aria-label*="생년월일"]',
            'input[name*="birth" i]',
            'input[id*="birth" i]',
            'input[name*="brth" i]',
            'input[id*="brth" i]',
            'input[name*="jumin" i]',
            'input[id*="jumin" i]',
            'input[maxlength="8"]',
        ]

        for selector in birth_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"생년월일 입력 필드 발견: {selector}")
                    return element
            except Exception:
                continue

        return None

    def find_age_input(self):
        """나이 입력 필드 찾기"""
        age_selectors = [
            'input[placeholder*="나이"]',
            'input[placeholder*="연령"]',
            'input[name*="age"]',
            'input[id*="age"]',
            'input[type="number"]',
            '.age-input',
            '#age'
        ]

        for selector in age_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    print(f"나이 입력 필드 발견: {selector}")
                    return element
            except:
                continue

        return None

    def find_gender_selector(self):
        """성별 선택 요소 찾기"""
        gender_selectors = [
            'select[name*="gender"]',
            'input[name*="gender"]',
            'button:has-text("남자")',
            'button:has-text("여자")',
            'label:has-text("남자")',
            'label:has-text("여자")',
            '.gender-select',
            '#gender'
        ]

        gender_elements = {}
        for selector in gender_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        text = element.inner_text().strip()
                        if "남자" in text or "남성" in text:
                            gender_elements["male"] = element
                        elif "여자" in text or "여성" in text:
                            gender_elements["female"] = element
            except:
                continue

        if gender_elements:
            print(f"성별 선택 요소 발견: {len(gender_elements)}개")
            return gender_elements

        return None

    def collect_premium_data(self, age_input, gender_selector, birthdate_input=None):
        """실제 보험료 데이터 수집"""
        print(f"\n보험료 데이터 수집 시작 (총 {len(self.age_range) * len(self.genders)}개 조합)")

        collected_count = 0

        for age in self.age_range:
            for gender in self.genders:
                try:
                    self.dismiss_blocking_modal()
                    print(f"수집 중: {age}세 {self.gender_korean[gender]} ({collected_count + 1}/{len(self.age_range) * len(self.genders)})")

                    # 생년월일 또는 나이 입력 (Playwright는 fill()이 기존 값을 지우고 입력함)
                    if birthdate_input:
                        # 기본(만나이 가정) -> 실패 시 ±1년 보정 재시도
                        birthdate_candidates = [
                            self.yyyymmdd_for_age(age),
                            self.yyyymmdd_for_age_variant(age, 1),
                            self.yyyymmdd_for_age_variant(age, -1),
                        ]
                        for idx, birthdate in enumerate(birthdate_candidates):
                            self.fill_birthdate_humanlike(birthdate_input, birthdate)
                            print(f"  -> 생년월일 입력: {birthdate}" + (" (재시도)" if idx > 0 else ""))
                            self.page.wait_for_timeout(600)
                            alert_text = self.get_system_alert_text()
                            if alert_text and ("생년월일" in alert_text) and ("올바르지" in alert_text or "유효" in alert_text):
                                # 입력 직후 검증 팝업이 뜨면 닫고 다음 후보로
                                self.dismiss_blocking_modal()
                                continue
                            break
                    elif age_input:
                        self.dismiss_blocking_modal()
                        age_input.fill(str(age), timeout=5000)
                        print(f"  -> 나이 입력: {age}")
                    else:
                        raise RuntimeError("입력 필드 핸들이 없습니다.")
                    self.page.wait_for_timeout(1000)

                    # 성별 선택
                    if gender_selector and isinstance(gender_selector, dict):
                        if gender in gender_selector:
                            self.dismiss_blocking_modal()
                            gender_selector[gender].click(timeout=5000, force=True)
                            print(f"  -> 성별 선택: {self.gender_korean[gender]}")
                            self.page.wait_for_timeout(1000)

                    # 계산 버튼 클릭
                    calc_button = self.find_calculate_button()
                    if calc_button:
                        self.dismiss_blocking_modal()
                        calc_button.click(timeout=5000, force=True)
                        print("  -> 계산 버튼 클릭")
                        self.page.wait_for_timeout(3000)  # 계산 결과 대기
                        self.dismiss_blocking_modal()
                        # 계산 후 "생년월일 올바르지 않음" 알림이 뜨면 이번 케이스는 실패 처리
                        post_alert = self.get_system_alert_text()
                        if post_alert and ("생년월일" in post_alert) and ("올바르지" in post_alert or "유효" in post_alert):
                            print(f"  -> 경고: {post_alert}")
                            self.dismiss_blocking_modal()
                            continue

                        # 보험료 결과 추출
                        premium_result = self.extract_premium_result()

                        if premium_result:
                            structured = premium_result.get("structured") or {}
                            premium_data = {
                                "age": age,
                                "birthdate": self.yyyymmdd_for_age(age) if birthdate_input else "",
                                "gender": gender,
                                "gender_korean": self.gender_korean[gender],
                                "amount": premium_result.get("amount", ""),
                                "monthly_premium": premium_result.get("monthly_premium", 0),
                                "calculation": structured,
                                "additional_info": premium_result.get("additional_info", ""),
                                "collected_at": datetime.now().isoformat()
                            }

                            self.price_data.append(premium_data)
                            collected_count += 1
                            print(f"  -> 월 보험료: {premium_result.get('monthly_premium', 0)}원")

                    # 다음 계산을 위한 대기
                    self.page.wait_for_timeout(1000)

                except Exception as e:
                    print(f"  -> 데이터 수집 실패: {e}")
                    continue

        print(f"보험료 데이터 수집 완료: {collected_count}건")
        return collected_count > 0

    def find_calculate_button(self):
        """계산 실행 버튼 찾기"""
        calc_selectors = [
            'button:has-text("계산")',
            'button:has-text("조회")',
            'button:has-text("확인")',
            'input[type="submit"]',
            '.calc-button',
            '.btn-calc',
            '#btnCalc'
        ]

        for selector in calc_selectors:
            try:
                element = self.page.query_selector(selector)
                if element and element.is_visible():
                    return element
            except:
                continue

        return None

    def dismiss_blocking_modal(self):
        """클릭을 막는 시스템 모달/오버레이 정리"""
        try:
            modal = self.page.locator("section.modal.alert.open").first
            if modal.count() > 0 and modal.is_visible():
                close_candidates = [
                    # 긍정/진행 계열 버튼도 우선 클릭(닫기만 하면 진행이 막히는 경우가 있음)
                    modal.locator('button:has-text("동의")').first,
                    modal.locator('button:has-text("확인")').first,
                    modal.locator('button:has-text("계속")').first,
                    modal.locator('button:has-text("예")').first,
                    modal.locator('button:has-text("확인")').first,
                    modal.locator('button:has-text("닫기")').first,
                    modal.locator('a:has-text("확인")').first,
                    modal.locator('a:has-text("동의")').first,
                    modal.locator('a:has-text("계속")').first,
                    modal.locator('a:has-text("닫기")').first,
                    modal.locator(".btn, .close").first,
                ]
                for btn in close_candidates:
                    try:
                        if btn.count() > 0 and btn.is_visible():
                            btn.click(timeout=1000)
                            self.page.wait_for_timeout(300)
                            break
                    except Exception:
                        continue
                if modal.is_visible():
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(300)
        except Exception:
            pass

        # 모달 외 전역 팝업(동의/확인/계속) 버튼이 떠있는 케이스도 처리
        try:
            global_btns = [
                self.page.locator('button:has-text("동의")').first,
                self.page.locator('button:has-text("확인")').first,
                self.page.locator('button:has-text("계속")').first,
                self.page.locator('button:has-text("닫기")').first,
            ]
            for b in global_btns:
                try:
                    if b.count() > 0 and b.is_visible():
                        b.click(timeout=700, force=True)
                        self.page.wait_for_timeout(200)
                except Exception:
                    continue
        except Exception:
            pass

    def scroll_result_into_view(self):
        """계산 결과 영역이 길 때 스크롤로 로드 유도"""
        try:
            for _ in range(4):
                self.page.mouse.wheel(0, 700)
                self.human_pause(200, 400)
        except Exception:
            pass

    def expand_rider_sections_if_needed(self):
        """특약 영역이 접혀 있으면 펼치기 시도"""
        labels = ["펼치기", "더보기", "전체보기", "열기"]
        for lab in labels:
            try:
                btns = self.page.locator(f'button:has-text("{lab}")').all()
                for b in btns[:15]:
                    try:
                        if b.is_visible():
                            b.click(timeout=800, force=True)
                            self.page.wait_for_timeout(200)
                    except Exception:
                        continue
            except Exception:
                continue

    def extract_dom_tables(self):
        """테이블/행 단위 텍스트 수집 (특약명·가입금액·월보험료)"""
        try:
            return self.page.evaluate(
                """() => {
                    const rows = [];
                    document.querySelectorAll('table tr, [role="row"]').forEach(tr => {
                        const cells = [...tr.querySelectorAll('td, th')]
                            .map(c => (c.innerText || '').replace(/\\s+/g, ' ').trim())
                            .filter(Boolean);
                        if (cells.length >= 2) rows.push(cells);
                    });
                    return rows;
                }"""
            )
        except Exception:
            return []

    def parse_calculation_from_page_text(self, text: str) -> dict:
        """
        KB 온라인 보험료 계산 결과 화면 텍스트에서 구조화 추출.
        플랜 요약 / 주계약 / 합계 / (가능하면) 특약 행
        """
        out = {
            "summary_title": None,
            "plans": [],
            "main_contract": {},
            "totals": {},
            "rider_categories": [],
            "riders": [],
            "parse_notes": [],
        }
        compact = " ".join(text.split())

        # 상단 요약: "보험료 계산 결과38세 남자" 등
        m = re.search(r"보험료\s*계산\s*결과\s*([0-9]+세\s*[남여]자)", text)
        if m:
            out["summary_title"] = m.group(1).strip()

        # 플랜 블록: 종합플랜(든든/실속), 뇌심플랜, 입원간병플랜 + 보험료(월납) + 보장 N개
        plan_keywords = r"(종합플랜\([^)]+\)|뇌심플랜|입원간병플랜)"
        for m in re.finditer(
            plan_keywords + r"[\s\S]{0,800}?보험료\s*\(\s*월납\s*\)\s*([\d,]+)\s*원[\s\S]{0,200}?보장\s*(\d+)\s*개",
            text,
            re.DOTALL,
        ):
            name = re.sub(r"\s+", " ", m.group(1).strip())
            try:
                prem = int(m.group(2).replace(",", ""))
                cnt = int(m.group(3))
                out["plans"].append(
                    {"plan_name": name, "monthly_premium": prem, "coverage_count": cnt}
                )
            except (ValueError, IndexError):
                continue

        # 합계: "월 보험료 : 57,148원" / "(주계약 320원 + 특약 56,828원)"
        m = re.search(r"월\s*보험료\s*[:：]\s*([\d,]+)\s*원", text)
        if m:
            out["totals"]["monthly_total"] = int(m.group(1).replace(",", ""))
        m = re.search(
            r"\(\s*주계약\s*([\d,]+)\s*원\s*\+\s*특약\s*([\d,]+)\s*원\s*\)", text
        )
        if m:
            out["totals"]["main_contract_monthly"] = int(m.group(1).replace(",", ""))
            out["totals"]["riders_monthly_sum"] = int(m.group(2).replace(",", ""))

        # 주계약: 납입주기, 보험기간, 납입기간, 일반사망보험금, 월보험료(주계약)
        m = re.search(r"납입주기[^\n]*?([^\n]+)", text)
        if m:
            out["main_contract"]["payment_cycle_hint"] = m.group(1).strip()[:80]
        m = re.search(r"보험기간[^\n]*?([^\n]+)", text)
        if m:
            out["main_contract"]["insurance_period_hint"] = m.group(1).strip()[:120]
        m = re.search(r"납입기간[^\n]*?([^\n]+)", text)
        if m:
            out["main_contract"]["payment_period_hint"] = m.group(1).strip()[:80]
        m = re.search(
            r"일반사망보험금\s*([\d,]+)\s*만\s*원", text.replace("\u00a0", " ")
        )
        if m:
            out["main_contract"]["general_death_benefit_manwon"] = int(
                m.group(1).replace(",", "")
            )
        m = re.search(
            r"월보험료\s*\(\s*주계약\s*\)\s*([\d,]+)\s*원", text.replace("\u00a0", " ")
        )
        if m:
            out["main_contract"]["main_monthly_premium"] = int(
                m.group(1).replace(",", "")
            )

        # 특약 카테고리 헤더 (뇌/심장 … 8/8 개 … 13,565 원)
        for m in re.finditer(
            r"([뇌/심장입원간병암진단비수술후유장해0-9/,\s]+)\s*(\d+)\s*/\s*(\d+)\s*개\s*([\d,]+)\s*원",
            text,
        ):
            out["rider_categories"].append(
                {
                    "category_label": m.group(1).strip()[:80],
                    "selected": int(m.group(2)),
                    "total_slots": int(m.group(3)),
                    "category_monthly_premium": int(m.group(4).replace(",", "")),
                }
            )

        return out

    def parse_riders_from_table_rows(self, rows: list) -> list:
        """DOM 테이블에서 특약명 / 가입금액 / 월보험료 3열 패턴 추출"""
        riders = []
        for cells in rows:
            if len(cells) < 3:
                continue
            joined = " ".join(cells)
            if "특약명" in joined and "가입금액" in joined:
                continue
            name = cells[0].strip()
            amt = cells[1].strip()
            prem = cells[2].strip()
            if "원" not in prem:
                continue
            if "특약" not in name and "미가입" not in amt:
                continue
            prem_num = None
            pm = re.search(r"([\d,]+)\s*원", prem)
            if pm:
                prem_num = int(pm.group(1).replace(",", ""))
            riders.append(
                {
                    "rider_name": name[:200],
                    "coverage_amount_text": amt[:80],
                    "monthly_premium": prem_num,
                    "monthly_premium_raw": prem[:40],
                }
            )
        return riders

    def extract_premium_result(self):
        """보험료 계산 결과 — 구조화(플랜/주계약/특약/합계) 우선, 실패 시 숫자만"""
        try:
            self.dismiss_blocking_modal()
            self.scroll_result_into_view()
            self.expand_rider_sections_if_needed()
            self.page.wait_for_timeout(800)

            body_text = ""
            try:
                body_text = self.page.locator("body").inner_text(timeout=15000)
            except Exception:
                body_text = self.page.content()

            structured = self.parse_calculation_from_page_text(body_text)
            table_rows = self.extract_dom_tables()
            riders_dom = self.parse_riders_from_table_rows(table_rows)
            if riders_dom:
                structured["riders"] = riders_dom

            # 대표 월 보험료: 합계 > 종합플랜(든든) 첫 플랜 > 레거시
            monthly = None
            if structured.get("totals", {}).get("monthly_total"):
                monthly = structured["totals"]["monthly_total"]
            elif structured.get("plans"):
                # "든든" 우선
                for p in structured["plans"]:
                    if "든든" in p.get("plan_name", ""):
                        monthly = p.get("monthly_premium")
                        break
                if monthly is None:
                    monthly = structured["plans"][0].get("monthly_premium")

            additional = body_text[:12000] if len(body_text) > 12000 else body_text

            if monthly is not None:
                return {
                    "monthly_premium": monthly,
                    "amount": structured.get("main_contract", {}).get(
                        "general_death_benefit_manwon", ""
                    ),
                    "structured": structured,
                    "additional_info": additional,
                }

            # 폴백: 큰 금액 후보(합계/플랜) — 주계약 소액(수백 원) 오인 방지
            candidates = []
            for m in re.finditer(r"([\d,]{2,})\s*원", body_text):
                val = int(m.group(1).replace(",", ""))
                if val >= 1000:
                    candidates.append(val)
            if candidates:
                return {
                    "monthly_premium": max(candidates),
                    "amount": "",
                    "structured": structured,
                    "additional_info": body_text[:8000],
                }

            return None

        except Exception as e:
            print(f"보험료 결과 추출 실패: {e}")
            return None

    def save_price_data(self):
        """보험료 데이터 JSON 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.output_dir / f'price_table_{timestamp}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.price_data, f, ensure_ascii=False, indent=2)

        print(f"\n보험료 테이블 저장: {filename}")
        return filename

    def print_price_summary(self):
        """보험료 수집 결과 요약"""
        print("\n" + "="*60)
        print("KB 딱좋은 e-건강보험 보험료 테이블 수집 결과")
        print("="*60)

        if not self.price_data:
            print("수집된 보험료 데이터가 없습니다.")
            return

        total_records = len(self.price_data)
        male_records = len([d for d in self.price_data if d['gender'] == 'male'])
        female_records = len([d for d in self.price_data if d['gender'] == 'female'])

        print(f"총 수집 건수: {total_records}건")
        print(f"남성: {male_records}건, 여성: {female_records}건")

        # 연령대별 평균 보험료
        if self.price_data:
            age_groups = {}
            for data in self.price_data:
                age_group = f"{data['age']//10*10}대"
                if age_group not in age_groups:
                    age_groups[age_group] = []
                age_groups[age_group].append(data['monthly_premium'])

            print("\n연령대별 평균 월 보험료:")
            for age_group, premiums in sorted(age_groups.items()):
                if premiums:
                    avg_premium = sum(premiums) / len(premiums)
                    print(f"  {age_group}: {avg_premium:,.0f}원")

        # 샘플 데이터 출력
        print(f"\n샘플 데이터 (처음 5건):")
        for i, data in enumerate(self.price_data[:5], 1):
            calc = data.get("calculation") or {}
            plans_n = len(calc.get("plans") or [])
            riders_n = len(calc.get("riders") or [])
            extra = f" [플랜요약 {plans_n}개, 특약행 {riders_n}개]" if (plans_n or riders_n) else ""
            print(f"  {i}. {data['age']}세 {data['gender_korean']}: {data['monthly_premium']:,}원{extra}")

    def run_scraper(self):
        """메인 스크래핑 실행"""
        print("KB 딱좋은 e-건강보험 보험료 테이블 스크래퍼 시작")
        print("="*60)

        try:
            # 1. 브라우저 설정
            self.setup_browser()

            # 2. 보험가격공시실 이동
            if not self.navigate_to_price_office():
                # 직접 상품 페이지 접근
                calculator_element = self.access_calculator_directly()
            else:
                # 계산기 찾기
                calculator_element = self.find_health_insurance_calculator()
                if not calculator_element:
                    calculator_element = self.access_calculator_directly()

            if calculator_element:
                # 3. 계산기와 상호작용하여 데이터 수집
                success = self.interact_with_calculator(calculator_element)

                if success:
                    # 4. 데이터 저장
                    saved_file = self.save_price_data()

                    # 5. 결과 요약
                    self.print_price_summary()

                    print(f"\n상세 데이터: {saved_file}")
                else:
                    print("보험료 데이터 수집 실패")
            else:
                print("보험료 계산기를 찾을 수 없습니다.")

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
    scraper = KBHealthInsurancePriceScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()