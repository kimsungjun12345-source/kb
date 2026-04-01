import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
import re
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBUltimateScraper:
    """완전히 재설계된 KB생명 스크래퍼 - 플랜별 특약 처리"""

    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        return browser, context

    def generate_birthdate(self, age):
        current_year = datetime.now().year
        birth_year = current_year - age
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return f"{birth_year}{month:02d}{day:02d}"

    async def wait_random(self, min_seconds=2, max_seconds=4):
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def select_gender_enhanced(self, page, gender):
        """강화된 성별 선택 로직 - 다중 시도"""
        gender_value = "1" if gender == "남성" else "2"  # KB생명은 1=남성, 2=여성
        logger.info(f"성별 선택 시작: {gender} ({gender_value})")

        # 먼저 페이지에 라디오 버튼이 있는지 확인
        try:
            await page.wait_for_selector("input[name='genderCode']", timeout=5000)
        except:
            logger.warning("성별 선택 라디오 버튼을 찾을 수 없음")
            return False

        # 방법 1: 더 안전한 직접 선택
        try:
            success = await page.evaluate(f"""
                () => {{
                    const radios = document.querySelectorAll('input[name="genderCode"]');
                    console.log('Found radios:', radios.length);

                    for (let radio of radios) {{
                        console.log('Radio value:', radio.value, 'Target:', '{gender_value}');
                        if (radio.value === '{gender_value}') {{
                            // 체크 상태 확인
                            if (!radio.checked) {{
                                radio.checked = true;

                                // 다양한 이벤트 발생
                                radio.dispatchEvent(new Event('click', {{ bubbles: true }}));
                                radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                radio.dispatchEvent(new Event('input', {{ bubbles: true }}));

                                // 부모 요소도 클릭
                                const parent = radio.closest('label, div');
                                if (parent) {{
                                    parent.click();
                                }}
                            }}

                            return radio.checked;
                        }}
                    }}
                    return false;
                }}
            """)

            if success:
                logger.info("✅ 방법 1: 안전한 직접 선택 성공")
                await asyncio.sleep(1)  # 선택 완료 대기
                return True
        except Exception as e:
            logger.warning(f"방법 1 실패: {str(e)}")

        # 방법 2: CSS 선택자로 직접 클릭
        try:
            gender_radio = await page.query_selector(f"input[name='genderCode'][value='{gender_value}']")
            if gender_radio:
                await gender_radio.click()
                logger.info("✅ 방법 2: CSS 선택자 클릭 성공")
                await asyncio.sleep(1)
                return True
        except Exception as e:
            logger.warning(f"방법 2 실패: {str(e)}")

        # 방법 3: 라벨 클릭 (라디오 버튼이 라벨 안에 있는 경우)
        try:
            label_element = await page.evaluate(f"""
                () => {{
                    const radios = document.querySelectorAll('input[name="genderCode"][value="{gender_value}"]');
                    for (let radio of radios) {{
                        const label = radio.closest('label') || document.querySelector('label[for="' + radio.id + '"]');
                        if (label) {{
                            label.click();
                            return true;
                        }}
                    }}
                    return false;
                }}
            """)

            if label_element:
                logger.info("✅ 방법 3: 라벨 클릭 성공")
                await asyncio.sleep(1)
                return True
        except Exception as e:
            logger.warning(f"방법 3 실패: {str(e)}")

        # 방법 4: Force 클릭
        try:
            radio_selector = f"input[name='genderCode'][value='{gender_value}']"
            await page.click(radio_selector, force=True)
            logger.info("✅ 방법 4: Force 클릭 성공")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.warning(f"방법 4 실패: {str(e)}")

        logger.error("❌ 모든 성별 선택 방법 실패")
        return False

    async def wait_for_page_stable(self, page, timeout=15000):
        """페이지 안정화 대기 - 강화된 버전"""
        try:
            # 네트워크 활동 완료 대기
            await page.wait_for_load_state("networkidle", timeout=timeout)

            # 동적 콘텐츠 로딩 대기
            await asyncio.sleep(3)

            # 중요 요소들이 실제로 보일 때까지 대기
            try:
                # 체크박스들이 로드될 때까지 대기
                await page.wait_for_selector('input[type="checkbox"]', timeout=8000)
                # 보험료 표시 영역이 로드될 때까지 대기
                await page.wait_for_function('''
                    () => {
                        const elements = document.querySelectorAll('*');
                        for (let el of elements) {
                            const text = el.textContent || '';
                            if (text.includes('원') && /\\d{1,3}(,\\d{3})*/.test(text)) {
                                return true;
                            }
                        }
                        return false;
                    }
                ''', timeout=5000)
            except:
                logger.warning("중요 요소 대기 실패, 계속 진행")

            # DOM 변화 완료 확인
            await page.evaluate("""
                () => {
                    return new Promise(resolve => {
                        if (document.readyState === 'complete') {
                            setTimeout(resolve, 2000);
                        } else {
                            window.addEventListener('load', () => {
                                setTimeout(resolve, 2000);
                            });
                        }
                    });
                }
            """)

            # 최종 안정성 체크
            checkbox_count = await page.locator('input[type="checkbox"]').count()
            logger.info(f"✅ 페이지 안정화 완료 - 체크박스 {checkbox_count}개 감지")
            return True

        except Exception as e:
            logger.warning(f"페이지 안정화 대기 중 오류: {str(e)}")
            return False

    async def handle_modal_dialogs(self, page):
        """모달 다이얼로그 처리"""
        try:
            # 일반적인 모달 버튼들 찾기
            modal_buttons = await page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    const modalButtons = buttons.filter(btn => {
                        const text = btn.textContent?.trim().toLowerCase();
                        return text.includes('확인') || text.includes('닫기') ||
                               text.includes('ok') || text.includes('close') ||
                               text.includes('선택');
                    });
                    return modalButtons.map(btn => btn.textContent?.trim());
                }
            """)

            if modal_buttons.length > 0:
                logger.info(f"모달 다이얼로그 발견: {modal_buttons}")

                # 첫 번째 모달 버튼 클릭
                await page.evaluate("""
                    () => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        const modalBtn = buttons.find(btn => {
                            const text = btn.textContent?.trim().toLowerCase();
                            return text.includes('확인') || text.includes('선택');
                        });
                        if (modalBtn) {
                            modalBtn.click();
                            return true;
                        }
                        return false;
                    }
                """)

                await asyncio.sleep(1)
                logger.info("✅ 모달 다이얼로그 처리 완료")
                return True

        except Exception as e:
            logger.warning(f"모달 처리 중 오류: {str(e)}")

        return False

    async def safely_uncheck_all_clauses(self, page):
        """모든 특약 체크박스를 안전하게 해제"""
        try:
            unchecked_count = await page.evaluate("""
                () => {
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    let count = 0;

                    checkboxes.forEach(cb => {
                        // 약관/동의 관련은 건드리지 않음
                        const parent = cb.closest('tr, div, li, label');
                        const text = parent ? parent.textContent : '';

                        if (!text.includes('동의') && !text.includes('약관') &&
                            !text.includes('개인정보') && cb.checked &&
                            cb.offsetParent !== null) {

                            cb.checked = false;
                            cb.click();
                            cb.dispatchEvent(new Event('change', { bubbles: true }));
                            count++;
                        }
                    });

                    return count;
                }
            """)

            logger.debug(f"특약 체크박스 {unchecked_count}개 해제")
            return True

        except Exception as e:
            logger.warning(f"체크박스 해제 중 오류: {str(e)}")
            return False

    async def safely_activate_clause(self, page, checkbox, clause_index):
        """체크박스를 안전하게 활성화"""
        try:
            # 방법 1: Playwright 내장 메서드
            try:
                is_visible = await checkbox.is_visible()
                is_enabled = await checkbox.is_enabled()

                if is_visible and is_enabled:
                    await checkbox.check(force=False)
                    logger.debug(f"특약 {clause_index+1} - 방법 1 성공")
                    return True
            except Exception as e:
                logger.debug(f"특약 {clause_index+1} - 방법 1 실패: {str(e)}")

            # 방법 2: JavaScript 직접 실행
            try:
                success = await page.evaluate(f"""
                    (index) => {{
                        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                        const target = checkboxes[index];

                        if (target && target.offsetParent !== null &&
                            target.offsetWidth > 0 && !target.disabled) {{

                            target.checked = true;
                            target.click();
                            target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            target.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            return true;
                        }}
                        return false;
                    }}
                """, clause_index)

                if success:
                    logger.debug(f"특약 {clause_index+1} - 방법 2 성공")
                    return True
            except Exception as e:
                logger.debug(f"특약 {clause_index+1} - 방법 2 실패: {str(e)}")

            # 방법 3: Force 클릭
            try:
                await checkbox.click(force=True)
                logger.debug(f"특약 {clause_index+1} - 방법 3 성공")
                return True
            except Exception as e:
                logger.debug(f"특약 {clause_index+1} - 방법 3 실패: {str(e)}")

            logger.warning(f"특약 {clause_index+1} - 모든 활성화 방법 실패")
            return False

        except Exception as e:
            logger.error(f"특약 {clause_index+1} 활성화 중 오류: {str(e)}")
            return False

    async def scrape_ultimate_data(self, age, gender):
        """완전한 데이터 수집 - 플랜 우선 로직"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info(f"🚀 플랜 우선 데이터 수집 시작: {age}세 {gender}")

                # 기본 페이지 접근
                await page.goto(self.base_url, wait_until="networkidle")
                await self.wait_random(3, 5)

                # 생년월일/성별 입력
                birthdate = self.generate_birthdate(age)
                await page.fill("#birthday", birthdate)
                await self.wait_random(1, 2)

                # 강화된 성별 선택 로직
                await self.select_gender_enhanced(page, gender)
                await self.wait_random(1, 2)

                # 설계견적하기 버튼 클릭 및 페이지 안정화
                button_clicked = await page.evaluate("""
                    () => {
                        const button = document.querySelector('#calculateResult');
                        if (button) {
                            button.click();
                            return button.textContent || button.innerText;
                        }
                        return null;
                    }
                """)

                if button_clicked:
                    logger.info(f"✅ 버튼 클릭: {button_clicked}")
                else:
                    logger.error("❌ 설계견적 버튼을 찾을 수 없음")

                # 페이지 로딩 완료 대기
                await self.wait_for_page_stable(page)
                await self.wait_random(3, 5)

                # 모달 다이얼로그 처리
                await self.handle_modal_dialogs(page)

                # 🆕 플랜 우선 수집 로직
                complete_data = {
                    "basic_info": {
                        "age": age,
                        "gender": gender,
                        "birthdate": birthdate,
                        "scraped_at": datetime.now().isoformat()
                    },
                    "plans": {},
                    "special_clauses": [],
                    "tooltips": [],
                    "premiums": {}
                }

                # 1단계: 플랜별 데이터 수집
                await self.collect_plan_based_data(page, complete_data)

                # 2단계: 도움말 수집
                logger.info("❓ 3단계: 도움말 정보 수집")
                await self.collect_question_tooltips(page, complete_data)

                # 3단계: 데이터 검증
                logger.info("📊 4단계: 데이터 검증")
                validation_result = self.validate_ultimate_data(complete_data)

                # 4단계: 결과 저장
                await self.save_ultimate_data(complete_data, age, gender)

                return complete_data

            finally:
                await browser.close()

    async def collect_plan_based_data(self, page, complete_data):
        """플랜 기반 데이터 수집 - 종합플랜 우선"""
        try:
            logger.info("🎯 1단계: 플랜별 특약 데이터 수집")

            # 모든 플랜 라디오 버튼 탐색
            plan_radios = await page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const plans = [];

                    radios.forEach((radio, index) => {
                        if (radio.name !== 'genderCode') {
                            const parent = radio.closest('tr, div, li, label');
                            const text = parent ? parent.textContent?.trim() : '';

                            if (text.includes('플랜') || text.includes('형') ||
                                text.includes('타입') || text.includes('종합') ||
                                text.includes('든든') || text.includes('실속')) {

                                plans.push({
                                    index: index,
                                    name: radio.name,
                                    value: radio.value,
                                    id: radio.id,
                                    text: text.substring(0, 100),
                                    checked: radio.checked,
                                    visible: radio.offsetParent !== null
                                });
                            }
                        }
                    });

                    return plans;
                }
            """)

            logger.info(f"🔍 발견된 플랜: {len(plan_radios)}개")

            # 종합플랜 우선 처리
            comprehensive_plans = []
            other_plans = []

            for plan in plan_radios:
                plan_text = plan['text'].lower()
                if ('종합' in plan_text and ('든든' in plan_text or '실속' in plan_text)) or \
                   ('comprehensive' in plan_text):
                    comprehensive_plans.append(plan)
                    logger.info(f"📋 종합플랜 발견: {plan['text'][:50]}")
                else:
                    other_plans.append(plan)

            # 1. 종합플랜들 처리 (특약 활성화 가능)
            for plan in comprehensive_plans:
                await self.process_comprehensive_plan(page, plan, complete_data)

            # 2. 일반플랜들 처리 (고정 특약만)
            for plan in other_plans:
                await self.process_fixed_plan(page, plan, complete_data)

        except Exception as e:
            logger.error(f"플랜별 데이터 수집 중 오류: {str(e)}")

    async def process_comprehensive_plan(self, page, plan, complete_data):
        """종합플랜 처리 - 특약 활성화 가능"""
        try:
            plan_name = f"comprehensive_{plan['value']}_{plan.get('id', 'unknown')}"
            logger.info(f"🔧 종합플랜 처리 시작: {plan['text'][:50]}")

            # 플랜 선택
            success = await page.evaluate(f"""
                (index) => {{
                    const radios = document.querySelectorAll('input[type="radio"]');
                    const target = radios[index];
                    if (target && target.offsetParent !== null) {{
                        target.checked = true;
                        target.click();
                        target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}
            """, plan['index'])

            if not success:
                logger.warning(f"❌ 플랜 선택 실패: {plan_name}")
                return

            await self.wait_random(3, 5)  # 플랜 변경 후 페이지 업데이트 대기
            logger.info(f"✅ 플랜 선택 완료: {plan_name}")

            # 기본 보험료 확인
            base_premium = await self.get_current_premium(page)

            plan_data = {
                "plan_info": plan,
                "base_premium": base_premium,
                "special_clauses": [],
                "activated_clauses": 0,
                "failed_clauses": 0
            }

            # 이 플랜에서 특약들 활성화 테스트
            await self.test_plan_clauses(page, plan_data)

            complete_data["plans"][plan_name] = plan_data
            logger.info(f"📊 {plan_name}: 기본보험료={base_premium}, 테스트된특약={plan_data['activated_clauses']}개")

        except Exception as e:
            logger.error(f"종합플랜 {plan.get('text', 'Unknown')} 처리 중 오류: {str(e)}")

    async def process_fixed_plan(self, page, plan, complete_data):
        """일반플랜 처리 - 고정 특약만"""
        try:
            plan_name = f"fixed_{plan['value']}_{plan.get('id', 'unknown')}"
            logger.info(f"📋 일반플랜 처리: {plan['text'][:50]}")

            # 플랜 선택
            success = await page.evaluate(f"""
                (index) => {{
                    const radios = document.querySelectorAll('input[type="radio"]');
                    const target = radios[index];
                    if (target && target.offsetParent !== null) {{
                        target.checked = true;
                        target.click();
                        target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                    return false;
                }}
            """, plan['index'])

            if not success:
                logger.warning(f"❌ 플랜 선택 실패: {plan_name}")
                return

            await self.wait_random(2, 3)

            # 현재 상태의 보험료와 특약 구성만 수집
            current_premium = await self.get_current_premium(page)
            current_clauses = await self.collect_visible_clauses_only(page, plan['index'])

            plan_data = {
                "plan_info": plan,
                "current_premium": current_premium,
                "fixed_clauses": current_clauses,
                "clause_count": len(current_clauses) if current_clauses else 0
            }

            complete_data["plans"][plan_name] = plan_data
            logger.info(f"📊 {plan_name}: 현재보험료={current_premium}, 고정특약={plan_data['clause_count']}개")

        except Exception as e:
            logger.error(f"일반플랜 {plan.get('text', 'Unknown')} 처리 중 오류: {str(e)}")

    async def test_plan_clauses(self, page, plan_data):
        """플랜별 특약 테스트"""
        try:
            # 현재 플랜에서 활성화 가능한 체크박스들 찾기
            checkboxes = await page.query_selector_all("input[type='checkbox']")

            for i, checkbox in enumerate(checkboxes):
                try:
                    # 특약 정보 추출
                    clause_info = await self.extract_clause_info(checkbox)
                    parent_text = clause_info.get("full_text", "").lower()

                    # 보험 관련 특약만 테스트
                    if (not any(keyword in parent_text for keyword in ['동의', '약관', '개인정보']) and
                        any(keyword in parent_text for keyword in ['특약', '보장', '급여', '질환', '암', '뇌', '심장'])):

                        is_enabled = await checkbox.is_enabled()

                        if is_enabled:
                            # 특약 활성화 시도
                            success = await self.safely_activate_clause(page, checkbox, i)

                            if success:
                                await self.wait_random(2, 3)  # 보험료 재계산 대기
                                new_premium = await self.get_current_premium(page)

                                clause_data = {
                                    "index": i,
                                    "name": clause_info.get("name", f"특약_{i+1}"),
                                    "with_clause_premium": new_premium,
                                    "base_premium": plan_data["base_premium"],
                                    "premium_difference": self.calculate_premium_difference(
                                        plan_data["base_premium"], new_premium),
                                    "test_successful": True
                                }

                                plan_data["special_clauses"].append(clause_data)
                                plan_data["activated_clauses"] += 1

                                logger.info(f"✅ 특약 {i+1} 성공: {new_premium}")

                                # 특약 비활성화
                                await checkbox.uncheck()
                                await self.wait_random(1, 2)
                            else:
                                plan_data["failed_clauses"] += 1
                                logger.debug(f"❌ 특약 {i+1} 활성화 실패")

                except Exception as e:
                    logger.debug(f"특약 {i+1} 테스트 중 오류: {str(e)}")
                    continue

        except Exception as e:
            logger.error(f"플랜 특약 테스트 중 오류: {str(e)}")
                    "premiums": {
                        "base_premium": None,
                        "plan_premiums": {},
                        "clause_premiums": {}
                    }
                }

                # 📋 1단계: 4개 플랜 각각 데이터 수집
                logger.info("📋 1단계: 4개 플랜 데이터 수집")
                await self.collect_four_plans(page, complete_data)

                # ✅ 2단계: 특약 각각 활성화하여 보험료 확인
                logger.info("✅ 2단계: 특약별 보험료 수집")
                await self.collect_clauses_with_activation(page, complete_data)

                # ❓ 3단계: 모든 물음표 툴팁 데이터 수집
                logger.info("❓ 3단계: 물음표 툴팁 수집")
                await self.collect_question_tooltips(page, complete_data)

                # 📊 4단계: 데이터 검증 및 완성도 확인
                logger.info("📊 4단계: 데이터 검증")
                self.validate_ultimate_data(complete_data)

                return complete_data

            except Exception as e:
                logger.error(f"완전한 데이터 수집 중 오류: {str(e)}")
                return None
            finally:
                await browser.close()

    async def collect_four_plans(self, page, complete_data):
        """4개 플랜 각각을 실제로 선택하여 플랜별 특약 수집"""
        try:
            # 모든 플랜 관련 라디오 버튼 식별 (더 정확한 필터링)
            plan_info = await page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const plans = [];

                    radios.forEach((radio, index) => {
                        // 성별 라디오는 제외
                        if (radio.name === 'genderCode') return;

                        const parent = radio.closest('tr, div, li, label');
                        if (parent) {
                            const text = parent.textContent?.trim();

                            // 플랜 관련 키워드 확인 (더 정확한 조건)
                            if ((text.includes('플랜') || text.includes('Plan') ||
                                text.includes('형') || text.includes('타입') ||
                                radio.name.includes('quest') || radio.name.includes('type')) &&
                                radio.offsetParent !== null) {

                                plans.push({
                                    index: index,
                                    name: radio.name,
                                    value: radio.value,
                                    text: text.substring(0, 100),
                                    checked: radio.checked,
                                    visible: radio.offsetParent !== null
                                });
                            }
                        }
                    });

                    return plans;
                }
            """)

            logger.info(f"🎯 발견된 플랜 옵션: {len(plan_info)}개")

            # 각 플랜별로 실제 선택 후 데이터 수집
            plan_counter = 1
            for i, plan in enumerate(plan_info[:8]):  # 최대 8개 플랜 테스트
                if not plan['visible']:
                    continue

                plan_key = f"plan_{plan_counter}"
                logger.info(f"📋 플랜 {plan_counter} 선택 및 수집: {plan['name']}={plan['value']}")
                logger.info(f"   설명: {plan['text'][:60]}")

                try:
                    # 플랜 선택
                    await page.evaluate(f"""
                        () => {{
                            const radios = document.querySelectorAll('input[type="radio"]');
                            const target = radios[{plan['index']}];
                            if (target && target.offsetParent !== null) {{
                                target.checked = true;
                                target.click();
                                target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }}
                    """)

                    await self.wait_random(3, 5)  # 플랜 변경 후 페이지 업데이트 대기

                    # 모달 처리
                    await self.handle_modal_dialogs(page)

                    # 플랜 선택 후 보이는 특약들만 수집
                    visible_clauses = await self.collect_visible_clauses_only(page, plan_counter)

                    # 플랜별 보험료 수집
                    plan_premium = await self.get_current_premium(page)

                    # 플랜 데이터 구성
                    plan_data = {
                        "plan_number": plan_counter,
                        "plan_info": plan,
                        "premium": plan_premium,
                        "visible_clauses": visible_clauses,
                        "visible_clause_count": len(visible_clauses),
                        "collected_at": datetime.now().isoformat()
                    }

                    complete_data["plans"][plan_key] = plan_data

                    # 로그 출력
                    visible_count = len([c for c in visible_clauses if c.get('visible', False)])
                    logger.info(f"   💰 보험료: {plan_premium}")
                    logger.info(f"   👁️  보이는 특약: {visible_count}개/{len(visible_clauses)}개")

                    if visible_count > 0:
                        logger.info(f"   📋 주요 보이는 특약:")
                        visible_clause_names = [c['text'][:40] for c in visible_clauses if c.get('visible', False)][:3]
                        for name in visible_clause_names:
                            logger.info(f"      - {name}")

                    plan_counter += 1

                    # 4개 플랜 수집 완료시 중단
                    if plan_counter > 4:
                        break

                except Exception as e:
                    logger.error(f"❌ 플랜 {plan_counter} 수집 오류: {str(e)}")
                    complete_data["plans"][plan_key] = {
                        "error": str(e),
                        "plan_number": plan_counter,
                        "plan_info": plan
                    }
                    plan_counter += 1

        except Exception as e:
            logger.error(f"플랜 수집 중 전체 오류: {str(e)}")

    async def collect_visible_clauses_only(self, page, plan_number):
        """현재 플랜에서 실제로 보이는 특약들만 수집"""
        try:
            logger.info(f"  🔍 플랜 {plan_number}의 보이는 특약 탐색...")

            # 보이는 체크박스만 필터링
            clause_info = await page.evaluate("""
                () => {
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    const clauses = [];

                    checkboxes.forEach((checkbox, index) => {
                        const parent = checkbox.closest('tr, div, li, label');
                        if (!parent) return;

                        const text = parent.textContent?.trim();

                        // 약관/동의 관련은 제외
                        if (text.includes('동의') || text.includes('약관') ||
                            text.includes('개인정보') || text.includes('통신사')) return;

                        // 보험 관련 특약만 포함
                        if (text.includes('특약') || text.includes('보장') ||
                            text.includes('급여') || text.includes('질환') ||
                            text.includes('상해') || text.includes('수술') ||
                            text.includes('암') || text.includes('뇌') ||
                            text.includes('심장') || text.includes('치료')) {

                            // 더 관대한 가시성 검사
                            const computedStyle = window.getComputedStyle(checkbox);
                            const parentStyle = checkbox.parentElement ? window.getComputedStyle(checkbox.parentElement) : null;

                            const isVisible = (
                                checkbox.offsetParent !== null ||  // 기본 조건
                                computedStyle.display !== 'none' ||  // CSS display 확인
                                (parentStyle && parentStyle.display !== 'none')  // 부모 요소 확인
                            ) && !checkbox.hidden;

                            clauses.push({
                                index: index,
                                text: text.substring(0, 150),
                                checked: checkbox.checked,
                                disabled: checkbox.disabled,
                                visible: isVisible,
                                enabled: !checkbox.disabled,
                                name: checkbox.name || '',
                                value: checkbox.value || '',
                                computed_display: window.getComputedStyle(checkbox).display
                            });
                        }
                    });

                    return clauses;
                }
            """)

            # 실제로 보이는 특약들만 필터링
            visible_clauses = [c for c in clause_info if c.get('visible', False) and c.get('computed_display') != 'none']
            all_clauses_count = len(clause_info)
            visible_count = len(visible_clauses)

            logger.info(f"  📊 플랜 {plan_number}: 전체 {all_clauses_count}개 중 {visible_count}개 특약이 보임")

            return clause_info  # 보이는 것과 숨겨진 것 모두 포함하되 visible 플래그로 구분

        except Exception as e:
            logger.error(f"플랜 {plan_number} 보이는 특약 수집 오류: {str(e)}")
            return []

    async def extract_plan_data(self, page, plan_number):
        """개별 플랜 데이터 추출"""
        try:
            plan_data = {
                "plan_number": plan_number,
                "premium": None,
                "coverage": [],
                "benefits": [],
                "period": None,
                "collected_at": datetime.now().isoformat()
            }

            # 현재 화면의 보험료 정보 수집
            premium_info = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const premiums = [];

                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && text.includes('원') &&
                            /\\d{1,3}(,\\d{3})*/.test(text) &&
                            el.offsetParent !== null) {

                            const parent = el.closest('tr, div, .premium-info');
                            const context = parent ? parent.textContent : text;

                            if (context.includes('보험료') || context.includes('월납') ||
                                context.includes('납입')) {
                                premiums.push({
                                    amount: text.trim(),
                                    context: context.substring(0, 100)
                                });
                            }
                        }
                    }

                    return premiums.slice(0, 3);  // 상위 3개
                }
            """)

            if premium_info:
                plan_data["premium"] = premium_info[0]["amount"]

            # 보장내용 수집
            coverage_info = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const coverages = [];

                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && (text.includes('보장') || text.includes('급여') ||
                            text.includes('지급') || text.includes('혜택')) &&
                            el.offsetParent !== null && text.length > 10) {
                            coverages.push(text.trim().substring(0, 150));
                        }
                    }

                    return [...new Set(coverages)].slice(0, 5);  // 중복 제거 후 5개
                }
            """)

            plan_data["coverage"] = coverage_info

            return plan_data

        except Exception as e:
            logger.error(f"플랜 데이터 추출 중 오류: {str(e)}")
            return {"error": str(e), "plan_number": plan_number}

    async def collect_clauses_with_activation(self, page, complete_data):
        """특약 데이터 수집 - 활성화 가능한 것만 테스트, 나머지는 현재 상태로 수집"""
        try:
            # 기본 보험료 저장
            base_premium = await self.get_current_premium(page)
            complete_data["premiums"]["base_premium"] = base_premium
            logger.info(f"기본 보험료: {base_premium}")

            # 모든 체크박스(특약) 찾기
            checkboxes = await page.query_selector_all("input[type='checkbox']")
            logger.info(f"발견된 특약 체크박스: {len(checkboxes)}개")

            # 보험관련 체크박스만 필터링
            insurance_checkboxes = []
            for i, checkbox in enumerate(checkboxes):
                try:
                    clause_info = await self.extract_clause_info(checkbox)
                    parent_text = clause_info.get("full_text", "").lower()

                    # 약관/동의 관련 제외, 보험 관련만 포함
                    if (not any(keyword in parent_text for keyword in ['동의', '약관', '개인정보', '통신사', '서비스']) and
                        any(keyword in parent_text for keyword in ['특약', '보장', '급여', '질환', '상해', '수술', '암', '뇌', '심장', '치료'])):

                        is_enabled = await checkbox.is_enabled()
                        is_visible = await checkbox.is_visible()

                        insurance_checkboxes.append({
                            'index': i,
                            'checkbox': checkbox,
                            'info': clause_info,
                            'is_enabled': is_enabled,
                            'is_visible': is_visible
                        })

                except Exception as e:
                    logger.debug(f"체크박스 {i} 분석 중 오류: {str(e)}")
                    continue

            logger.info(f"보험 관련 특약: {len(insurance_checkboxes)}개")

            # 각 특약 처리
            for item in insurance_checkboxes:
                i = item['index']
                checkbox = item['checkbox']
                clause_info = item['info']
                is_enabled = item['is_enabled']
                is_visible = item['is_visible']

                try:
                    logger.info(f"특약 {i+1} 처리: {clause_info.get('name', 'Unknown')[:40]}...")

                    clause_data = {
                        "index": i,
                        "name": clause_info.get("name", f"특약_{i+1}"),
                        "description": clause_info.get("description"),
                        "full_text": clause_info.get("full_text", ""),
                        "base_premium": base_premium,
                        "with_clause_premium": None,
                        "premium_difference": None,
                        "tooltip": None,
                        "is_enabled": is_enabled,
                        "is_visible": is_visible,
                        "is_tested": False,
                        "status": "disabled" if not is_enabled else "available"
                    }

                    # 활성화 가능한 특약은 모두 테스트 (숨겨진 것도 포함)
                    if is_enabled:  # is_visible 조건 제거
                        try:
                            # 모든 체크박스 해제
                            await self.safely_uncheck_all_clauses(page)
                            await self.wait_random(1, 2)

                            # 해당 특약 활성화 시도
                            success = await self.safely_activate_clause(page, checkbox, i)

                            if success:
                                await self.wait_random(2, 4)  # 보험료 재계산 대기

                                # 활성화된 보험료 확인
                                activated_premium = await self.get_current_premium(page)
                                if activated_premium and activated_premium != base_premium:
                                    premium_diff = self.calculate_premium_difference(base_premium, activated_premium)
                                    clause_data.update({
                                        "with_clause_premium": activated_premium,
                                        "premium_difference": premium_diff,
                                        "is_tested": True,
                                        "status": "tested_successfully"
                                    })
                                    logger.info(f"✅ 특약 {i+1} 활성화 성공: {premium_diff}")
                                else:
                                    clause_data.update({
                                        "status": "no_premium_change",
                                        "is_tested": True
                                    })
                                    logger.info(f"⚠️ 특약 {i+1} 보험료 변화 없음")

                                # 툴팁 정보 수집
                                tooltip_info = await self.get_clause_tooltip(checkbox, page)
                                clause_data["tooltip"] = tooltip_info

                            else:
                                clause_data.update({
                                    "status": "activation_failed",
                                    "is_tested": False
                                })
                                logger.warning(f"❌ 특약 {i+1} 활성화 실패")

                        except Exception as activation_error:
                            clause_data.update({
                                "status": "activation_error",
                                "error": str(activation_error),
                                "is_tested": False
                            })
                            logger.error(f"특약 {i+1} 활성화 중 오류: {str(activation_error)}")

                    else:
                        # 비활성화된 특약도 정보는 수집
                        tooltip_info = await self.get_clause_tooltip(checkbox, page)
                        clause_data["tooltip"] = tooltip_info

                        if not is_enabled:
                            logger.info(f"⏸️ 특약 {i+1} 비활성화 상태로 정보만 수집")
                        else:
                            logger.info(f"👻 특약 {i+1} 보이지 않음, 정보만 수집")

                    complete_data["special_clauses"].append(clause_data)

                except Exception as e:
                    logger.error(f"특약 {i+1} 처리 중 오류: {str(e)}")
                    complete_data["special_clauses"].append({
                        "index": i,
                        "name": f"특약_{i+1}",
                        "status": "processing_error",
                        "error": str(e),
                        "is_tested": False
                    })

        except Exception as e:
            logger.error(f"특약 수집 중 전체 오류: {str(e)}")

    async def extract_clause_info(self, checkbox):
        """특약 정보 추출"""
        try:
            clause_info = await checkbox.evaluate("""
                el => {
                    const parent = el.closest('tr, div, li, label, .clause-item');
                    if (parent) {
                        const text = parent.textContent.trim();
                        const lines = text.split('\\n').filter(line => line.trim());
                        return {
                            name: lines[0] ? lines[0].trim() : 'Unknown',
                            description: lines.length > 1 ? lines.slice(1).join(' ').trim() : null,
                            full_text: text
                        };
                    }
                    return { name: 'Unknown', description: null };
                }
            """)

            return clause_info

        except Exception as e:
            logger.error(f"특약 정보 추출 중 오류: {str(e)}")
            return {"name": "Unknown", "error": str(e)}

    async def get_current_premium(self, page):
        """현재 화면의 보험료 추출 - 정밀화된 로직"""
        try:
            premium_info = await page.evaluate("""
                () => {
                    // 우선순위별 보험료 선택자들
                    const selectors = [
                        // 가장 구체적인 보험료 선택자부터
                        '[class*="premium-amount"]',
                        '[class*="price-amount"]',
                        '[class*="total-price"]',
                        '[id*="premium"]',
                        '[id*="price"]',
                        '[id*="amount"]',
                        // 테이블 셀들
                        'td[class*="price"], td[class*="premium"], td[class*="amount"]',
                        // 일반적인 태그들
                        'strong, span, div, td'
                    ];

                    const priorityKeywords = [
                        '총보험료', '월납보험료', '보험료계', '납입보험료',
                        '총 보험료', '월 보험료', '보험료 총계'
                    ];

                    const fallbackKeywords = [
                        '보험료', '월납', '납입', '계산결과'
                    ];

                    // 우선순위 1: 가장 구체적인 키워드를 가진 요소
                    for (let selector of selectors) {
                        const elements = document.querySelectorAll(selector);

                        for (let el of elements) {
                            const text = el.textContent?.trim();
                            if (!text || !el.offsetParent) continue;

                            const parent = el.closest('tr, div, section');
                            const contextText = parent ? parent.textContent : text;

                            // 보험료 패턴 매칭
                            const premiumMatch = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                            if (!premiumMatch) continue;

                            // 우선순위 키워드 체크
                            for (let keyword of priorityKeywords) {
                                if (contextText.includes(keyword)) {
                                    return {
                                        amount: premiumMatch[1] + '원',
                                        context: keyword,
                                        fullText: text.substring(0, 100),
                                        priority: 1
                                    };
                                }
                            }
                        }
                    }

                    // 우선순위 2: 일반적인 보험료 키워드
                    for (let selector of selectors) {
                        const elements = document.querySelectorAll(selector);

                        for (let el of elements) {
                            const text = el.textContent?.trim();
                            if (!text || !el.offsetParent) continue;

                            const parent = el.closest('tr, div, section');
                            const contextText = parent ? parent.textContent : text;

                            const premiumMatch = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                            if (!premiumMatch) continue;

                            for (let keyword of fallbackKeywords) {
                                if (contextText.includes(keyword)) {
                                    return {
                                        amount: premiumMatch[1] + '원',
                                        context: keyword,
                                        fullText: text.substring(0, 100),
                                        priority: 2
                                    };
                                }
                            }
                        }
                    }

                    // 우선순위 3: 첫 번째로 발견되는 보험료 형태
                    const allElements = Array.from(document.querySelectorAll('*'));
                    for (let el of allElements) {
                        const text = el.textContent?.trim();
                        if (!text || !el.offsetParent) continue;

                        const premiumMatch = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                        if (premiumMatch && text.length < 50) {
                            return {
                                amount: premiumMatch[1] + '원',
                                context: 'fallback',
                                fullText: text,
                                priority: 3
                            };
                        }
                    }

                    return null;
                }
            """)

            if premium_info:
                logger.debug(f"보험료 추출 완료: {premium_info['amount']} (컨텍스트: {premium_info['context']}, 우선순위: {premium_info['priority']})")
                return premium_info['amount']

            return None

        except Exception as e:
            logger.error(f"보험료 추출 중 오류: {str(e)}")
            return None

    def calculate_premium_difference(self, base_premium, activated_premium):
        """보험료 차이 계산"""
        try:
            if not base_premium or not activated_premium:
                return None

            # 숫자만 추출하여 계산
            base_nums = re.findall(r'\d+', base_premium.replace(',', ''))
            activated_nums = re.findall(r'\d+', activated_premium.replace(',', ''))

            if base_nums and activated_nums:
                base_val = int(base_nums[0])
                activated_val = int(activated_nums[0])
                difference = activated_val - base_val
                return f"{difference:,}원" if difference > 0 else "0원"

            return None

        except Exception as e:
            logger.error(f"보험료 차이 계산 중 오류: {str(e)}")
            return None

    async def get_clause_tooltip(self, checkbox, page):
        """특약의 물음표 툴팁 정보 가져오기"""
        try:
            # 체크박스 주변에서 툴팁 요소 찾기
            tooltip_info = await checkbox.evaluate("""
                el => {
                    const parent = el.closest('tr, div, li');
                    if (!parent) return null;

                    const tooltipElements = parent.querySelectorAll(
                        '[title], [class*="tooltip"], [class*="help"], [class*="question"], img[src*="help"]'
                    );

                    const tooltips = [];
                    for (let tooltipEl of tooltipElements) {
                        const title = tooltipEl.getAttribute('title');
                        if (title) {
                            tooltips.push({
                                type: 'title',
                                content: title
                            });
                        }
                    }

                    return tooltips.length > 0 ? tooltips : null;
                }
            """)

            # 호버하여 추가 툴팁 확인 시도
            if not tooltip_info:
                try:
                    parent = await checkbox.evaluate("el => el.closest('tr, div, li')")
                    if parent:
                        await parent.hover()
                        await asyncio.sleep(1)

                        # 나타난 툴팁 확인
                        tooltip_content = await page.evaluate("""
                            () => {
                                const tooltips = document.querySelectorAll('[role="tooltip"], .tooltip-content, .tooltip-text');
                                for (let tooltip of tooltips) {
                                    if (tooltip.offsetParent !== null) {
                                        return tooltip.textContent.trim();
                                    }
                                }
                                return null;
                            }
                        """)

                        if tooltip_content:
                            tooltip_info = [{"type": "hover", "content": tooltip_content}]

                except:
                    pass

            return tooltip_info

        except Exception as e:
            logger.error(f"툴팁 정보 수집 중 오류: {str(e)}")
            return None

    async def collect_question_tooltips(self, page, complete_data):
        """페이지의 모든 물음표 툴팁 데이터 수집"""
        try:
            all_tooltips = await page.evaluate("""
                () => {
                    const tooltipSelectors = [
                        '[title]',
                        '[class*="tooltip"]',
                        '[class*="help"]',
                        '[class*="question"]',
                        'img[src*="help"]',
                        'img[src*="question"]',
                        '[data-tooltip]',
                        '[aria-describedby]'
                    ];

                    const tooltips = {};
                    let count = 0;

                    for (let selector of tooltipSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (let el of elements) {
                            const title = el.getAttribute('title');
                            const dataTooltip = el.getAttribute('data-tooltip');
                            const ariaDesc = el.getAttribute('aria-describedby');

                            if (title) {
                                tooltips[`tooltip_${count++}`] = {
                                    selector: selector,
                                    type: 'title_attribute',
                                    content: title,
                                    element_tag: el.tagName
                                };
                            }

                            if (dataTooltip) {
                                tooltips[`tooltip_${count++}`] = {
                                    selector: selector,
                                    type: 'data_tooltip',
                                    content: dataTooltip,
                                    element_tag: el.tagName
                                };
                            }
                        }
                    }

                    return tooltips;
                }
            """)

            complete_data["tooltips"] = all_tooltips
            logger.info(f"물음표 툴팁 수집 완료: {len(all_tooltips)}개")

        except Exception as e:
            logger.error(f"물음표 툴팁 수집 중 오류: {str(e)}")

    def validate_ultimate_data(self, complete_data):
        """수집된 데이터의 완성도 검증"""
        try:
            validation = {
                "plans_count": len([p for p in complete_data["plans"].values() if not p.get("error")]),
                "clauses_count": len(complete_data["special_clauses"]),
                "tooltips_count": len(complete_data["tooltips"]),
                "base_premium_exists": bool(complete_data["premiums"]["base_premium"]),
                "completion_score": 0,
                "missing_items": []
            }

            # 완성도 점수 계산
            score = 0
            max_score = 100

            # 플랜 데이터 (40점)
            if validation["plans_count"] >= 4:
                score += 40
            elif validation["plans_count"] >= 2:
                score += 20
            elif validation["plans_count"] >= 1:
                score += 10
            else:
                validation["missing_items"].append("플랜 데이터 부족")

            # 특약 데이터 (30점)
            if validation["clauses_count"] >= 10:
                score += 30
            elif validation["clauses_count"] >= 5:
                score += 20
            elif validation["clauses_count"] >= 1:
                score += 10
            else:
                validation["missing_items"].append("특약 데이터 부족")

            # 기본 보험료 (20점)
            if validation["base_premium_exists"]:
                score += 20
            else:
                validation["missing_items"].append("기본 보험료 없음")

            # 툴팁 데이터 (10점)
            if validation["tooltips_count"] >= 5:
                score += 10
            elif validation["tooltips_count"] >= 1:
                score += 5
            else:
                validation["missing_items"].append("툴팁 데이터 부족")

            validation["completion_score"] = score

            complete_data["validation"] = validation

            logger.info("=== 데이터 완성도 검증 결과 ===")
            logger.info(f"완성도 점수: {score}/{max_score}점")
            logger.info(f"수집된 플랜: {validation['plans_count']}개")
            logger.info(f"수집된 특약: {validation['clauses_count']}개")
            logger.info(f"수집된 툴팁: {validation['tooltips_count']}개")
            logger.info(f"기본 보험료: {'있음' if validation['base_premium_exists'] else '없음'}")

            if validation["missing_items"]:
                logger.warning(f"부족한 항목: {', '.join(validation['missing_items'])}")

        except Exception as e:
            logger.error(f"데이터 검증 중 오류: {str(e)}")

    async def save_ultimate_data(self, data, age, gender):
        """완전한 데이터 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"kb_ultimate_{age}_{gender}_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"완전한 데이터 저장 완료: {filename}")

            # 결과 요약 출력
            self.print_collection_summary(data, age, gender)

            return filename

        except Exception as e:
            logger.error(f"데이터 저장 중 오류: {str(e)}")
            return None

    def print_collection_summary(self, data, age, gender):
        """수집 결과 요약 출력"""
        print("\n" + "="*80)
        print(f"KB생명 완전한 보험료 데이터 수집 결과 - {age}세 {gender}")
        print("="*80)

        validation = data.get("validation", {})
        print(f"완성도 점수: {validation.get('completion_score', 0)}/100점")

        print(f"\n수집된 플랜: {validation.get('plans_count', 0)}개")
        for plan_name, plan_data in data.get("plans", {}).items():
            if not plan_data.get("error"):
                premium = plan_data.get("premium", "N/A")
                print(f"   - {plan_name}: {premium}")

        print(f"\n수집된 특약: {len(data.get('special_clauses', []))}개")
        base_premium = data.get("premiums", {}).get("base_premium", "N/A")
        print(f"   - 기본 보험료: {base_premium}")

        clauses = data.get("special_clauses", [])
        for i, clause in enumerate(clauses[:5]):  # 처음 5개만
            name = clause.get("name", f"특약_{i+1}")
            premium = clause.get("with_clause_premium", "N/A")
            diff = clause.get("premium_difference", "N/A")
            print(f"   - {name}: {premium} (차이: {diff})")

        if len(clauses) > 5:
            print(f"   - ... 그 외 {len(clauses) - 5}개 특약")

        print(f"\n수집된 툴팁: {len(data.get('tooltips', {}))}개")

        missing = validation.get('missing_items', [])
        if missing:
            print(f"\n부족한 데이터: {', '.join(missing)}")

        print("="*80)

    async def run_ultimate_test(self, age=30, gender="남성"):
        """완전한 수집 테스트 실행"""
        logger.info("🚀 KB생명 완전한 보험료 데이터 수집 테스트 시작")

        result = await self.scrape_ultimate_data(age, gender)

        if result:
            filename = await self.save_ultimate_data(result, age, gender)
            logger.info(f"✅ 완전한 데이터 수집 성공! 파일: {filename}")
            return result
        else:
            logger.error("❌ 완전한 데이터 수집 실패!")
            return None

async def main():
    scraper = KBUltimateScraper()
    await scraper.run_ultimate_test(30, "남성")

if __name__ == "__main__":
    asyncio.run(main())