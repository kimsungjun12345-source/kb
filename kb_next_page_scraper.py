import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBNextPageScraper:
    """
    KB생명 보험 다음 페이지 완전 스크래퍼
    1. 첫 페이지: 생년월일/성별 입력 → 보험료 계산하기 클릭
    2. 다음 페이지: 특약 활성화, 4개 플랜, 물음표 툴팁 수집
    """
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.data = []

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,  # 페이지 이동 확인을 위해 화면 표시
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

    async def handle_modal_dialogs(self, page):
        """모달 대화상자 처리"""
        try:
            # 여러 번 시도하여 모달 처리
            for attempt in range(3):
                await asyncio.sleep(1)

                modal_handled = await page.evaluate("""
                    () => {
                        // 다양한 방법으로 확인 버튼 찾기
                        const buttons = document.querySelectorAll('button');

                        for (let btn of buttons) {
                            const text = btn.textContent.trim();
                            const isVisible = btn.offsetParent !== null;

                            if (isVisible && (text === '확인' || text.includes('확인') ||
                                text === 'OK' || text === '다음' || text === '계속')) {
                                btn.click();
                                return `clicked: ${text}`;
                            }
                        }

                        // 모달 닫기 X 버튼 찾기
                        const closeButtons = document.querySelectorAll('.close, .btn-close, [data-dismiss="modal"], .modal-close');
                        for (let btn of closeButtons) {
                            if (btn.offsetParent !== null) {
                                btn.click();
                                return 'clicked close button';
                            }
                        }

                        return null;
                    }
                """)

                if modal_handled:
                    logger.info(f"✅ 모달 처리 성공 (시도 {attempt + 1}): {modal_handled}")
                    await self.wait_random(2, 4)
                    break
                else:
                    logger.info(f"📄 모달 찾을 수 없음 (시도 {attempt + 1})")

        except Exception as e:
            logger.warning(f"모달 처리 중 오류: {str(e)}")

    async def scrape_complete_with_next_page(self, age, gender):
        """페이지 이동을 포함한 완전한 데이터 수집"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info(f"🎯 페이지 이동 포함 완전 수집: {age}세 {gender}")

                # === 1단계: 첫 페이지에서 기본 정보 입력 ===
                logger.info("📝 1단계: 첫 페이지에서 기본 정보 입력")
                success = await self.fill_first_page(page, age, gender)
                if not success:
                    logger.error("첫 페이지 입력 실패")
                    return None

                # === 2단계: 다음 페이지로 이동 대기 ===
                logger.info("🔄 2단계: 다음 페이지로 이동 대기")
                next_page_ready = await self.wait_for_next_page(page, age, gender)
                if not next_page_ready:
                    logger.error("다음 페이지 로드 실패")
                    return None

                # === 3단계: 다음 페이지에서 완전한 데이터 수집 ===
                logger.info("💎 3단계: 다음 페이지에서 완전한 데이터 수집")
                complete_data = await self.collect_from_next_page(page, age, gender)

                return complete_data

            except Exception as e:
                logger.error(f"전체 수집 중 오류: {str(e)}")
                return None
            finally:
                await browser.close()

    async def fill_first_page(self, page, age, gender):
        """첫 페이지에서 생년월일/성별 입력 및 계산 버튼 클릭"""
        try:
            # 페이지 로드
            await page.goto(self.base_url, wait_until="networkidle")
            await self.wait_random(3, 5)

            # 생년월일 입력
            birthdate = self.generate_birthdate(age)
            logger.info(f"생년월일 입력: {birthdate}")

            await page.fill("#birthday", birthdate)
            await self.wait_random(1, 2)

            # 성별 선택
            gender_value = "M" if gender == "남성" else "F"
            await page.evaluate(f"""
                const radios = document.querySelectorAll('input[name="genderCode"]');
                for (let radio of radios) {{
                    if (radio.value === '{gender_value}') {{
                        radio.checked = true;
                        radio.click();
                        radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        break;
                    }}
                }}
            """)

            logger.info(f"성별 선택 완료: {gender}")
            await self.wait_random(2, 3)

            # 현재 URL 저장
            current_url = page.url
            logger.info(f"현재 URL: {current_url}")

            # 보험료 계산하기 버튼 클릭
            button_clicked = await page.evaluate("""
                () => {
                    const buttons = document.querySelectorAll('button');
                    for (let button of buttons) {
                        const text = button.textContent || button.innerText;
                        if (text.includes('설계') || text.includes('견적') || text.includes('계산')) {
                            button.click();
                            return text;
                        }
                    }
                    return null;
                }
            """)

            if button_clicked:
                logger.info(f"✅ 버튼 클릭 성공: {button_clicked}")
                await self.wait_random(2, 3)

                # 모달 대화상자 처리
                await self.handle_modal_dialogs(page)

                return True
            else:
                logger.error("❌ 계산 버튼을 찾을 수 없음")
                return False

        except Exception as e:
            logger.error(f"첫 페이지 입력 중 오류: {str(e)}")
            return False

    async def wait_for_next_page(self, page, age=30, gender="테스트"):
        """다음 페이지 로딩 완료까지 대기"""
        try:
            original_url = page.url
            logger.info(f"원래 URL: {original_url}")

            # 페이지 변경 감지를 위한 다양한 방법 시도
            max_wait_time = 30  # 최대 30초 대기
            check_interval = 1  # 1초마다 확인

            for i in range(max_wait_time):
                await asyncio.sleep(check_interval)
                current_url = page.url

                # URL 변경 확인
                if current_url != original_url:
                    logger.info(f"🔄 URL 변경 감지: {current_url}")
                    break

                # 페이지 내용 변경 확인 (특약 관련 요소가 나타났는지)
                special_elements_exist = await page.evaluate("""
                    () => {
                        // 특약 관련 체크박스나 플랜 선택 요소가 있는지 확인
                        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                        const planElements = document.querySelectorAll('[class*="plan"], [id*="plan"]');
                        const premiumElements = Array.from(document.querySelectorAll('*')).filter(el =>
                            el.textContent && el.textContent.includes('보험료') && el.offsetParent !== null
                        );

                        return {
                            checkboxes: checkboxes.length,
                            plans: planElements.length,
                            premiums: premiumElements.length,
                            total_score: checkboxes.length + planElements.length + premiumElements.length
                        };
                    }
                """)

                if special_elements_exist['total_score'] > 10:  # 충분한 요소가 로드됨
                    logger.info(f"📊 다음 페이지 콘텐츠 로드 완료: 체크박스 {special_elements_exist['checkboxes']}개, 플랜 {special_elements_exist['plans']}개")
                    break

                if i % 5 == 0:  # 5초마다 진행상황 로그
                    logger.info(f"⏳ 다음 페이지 대기 중... ({i}/{max_wait_time}초)")

            # 최종 확인
            await page.wait_for_load_state("networkidle", timeout=10000)
            await self.wait_random(3, 5)

            # 페이지 스크린샷 (디버깅용)
            await page.screenshot(path=f"next_page_{age}_{gender}.png")
            logger.info("📸 다음 페이지 스크린샷 저장")

            return True

        except Exception as e:
            logger.error(f"다음 페이지 대기 중 오류: {str(e)}")
            return False

    async def collect_from_next_page(self, page, age, gender):
        """다음 페이지에서 완전한 데이터 수집"""
        try:
            birthdate = self.generate_birthdate(age)

            complete_data = {
                "basic_info": {
                    "age": age,
                    "gender": gender,
                    "birthdate": birthdate,
                    "scraped_at": datetime.now().isoformat(),
                    "page_url": page.url
                },
                "plans": {
                    "plan_1": {},
                    "plan_2": {},
                    "plan_3": {},
                    "plan_4": {}
                },
                "special_clauses": [],
                "tooltips": {},
                "premiums": {
                    "base_premium": None,
                    "clause_premiums": {}
                }
            }

            # 🏷️ 1단계: 기본 보험료 수집
            logger.info("💰 기본 보험료 수집 중...")
            base_premium = await self.get_current_premium(page)
            complete_data["premiums"]["base_premium"] = base_premium
            logger.info(f"기본 보험료: {base_premium}")

            # 📋 2단계: 4개 플랜 데이터 수집
            logger.info("📋 4개 플랜 데이터 수집 중...")
            await self.collect_plan_data_next_page(page, complete_data)

            # ✅ 3단계: 특약 하나씩 활성화하여 보험료 확인
            logger.info("✅ 특약별 보험료 수집 중...")
            await self.collect_clauses_next_page(page, complete_data)

            # ❓ 4단계: 물음표 툴팁 수집
            logger.info("❓ 물음표 툴팁 수집 중...")
            await self.collect_tooltips_next_page(page, complete_data)

            # 📊 5단계: 데이터 검증
            logger.info("📊 데이터 검증 중...")
            self.validate_next_page_data(complete_data)

            return complete_data

        except Exception as e:
            logger.error(f"다음 페이지 데이터 수집 중 오류: {str(e)}")
            return None

    async def get_current_premium(self, page):
        """현재 페이지의 보험료 추출"""
        try:
            premium_data = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const candidates = [];

                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && text.includes('원') &&
                            /\\d{1,3}(,\\d{3})*/.test(text) &&
                            el.offsetParent !== null) {

                            const parent = el.closest('tr, div, .premium-area, .calc-result');
                            const context = parent ? parent.textContent : text;

                            // 보험료 관련 키워드 우선순위
                            let priority = 0;
                            if (context.includes('총보험료')) priority += 10;
                            if (context.includes('월납보험료')) priority += 8;
                            if (context.includes('납입보험료')) priority += 6;
                            if (context.includes('보험료계')) priority += 5;
                            if (context.includes('보험료')) priority += 3;

                            if (priority > 0) {
                                const match = text.match(/\\d{1,3}(,\\d{3})*원/);
                                if (match) {
                                    candidates.push({
                                        amount: match[0],
                                        priority: priority,
                                        context: context.substring(0, 100)
                                    });
                                }
                            }
                        }
                    }

                    // 우선순위 순으로 정렬
                    candidates.sort((a, b) => b.priority - a.priority);

                    return candidates.length > 0 ? candidates[0].amount : null;
                }
            """)

            return premium_data

        except Exception as e:
            logger.error(f"보험료 추출 중 오류: {str(e)}")
            return None

    async def collect_plan_data_next_page(self, page, complete_data):
        """다음 페이지에서 4개 플랜 데이터 수집"""
        try:
            # 플랜 선택 라디오 버튼 찾기
            plan_options = await page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const planRadios = radios.filter(radio => {
                        const parent = radio.closest('tr, div, li, .plan-item');
                        const text = parent ? parent.textContent : '';
                        return text.includes('플랜') || text.includes('형') ||
                               text.includes('Plan') || text.includes('타입');
                    });

                    return planRadios.map((radio, index) => ({
                        index: index,
                        name: radio.name,
                        value: radio.value,
                        text: radio.closest('tr, div, li')?.textContent?.trim().substring(0, 50) || `플랜_${index+1}`
                    })).slice(0, 4);
                }
            """)

            logger.info(f"발견된 플랜: {len(plan_options)}개")

            # 각 플랜 데이터 수집
            for i, plan_info in enumerate(plan_options):
                try:
                    plan_key = f"plan_{i+1}"
                    logger.info(f"플랜 {i+1} 수집: {plan_info['text']}")

                    # 플랜 선택
                    await page.evaluate(f"""
                        const radios = document.querySelectorAll('input[type="radio"]');
                        const targetRadio = Array.from(radios).find(r =>
                            r.name === '{plan_info["name"]}' && r.value === '{plan_info["value"]}'
                        );
                        if (targetRadio) {{
                            targetRadio.checked = true;
                            targetRadio.click();
                            targetRadio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    """)

                    await self.wait_random(2, 3)

                    # 해당 플랜의 보험료 및 보장내용 수집
                    plan_premium = await self.get_current_premium(page)
                    plan_coverage = await self.get_plan_coverage(page)

                    complete_data["plans"][plan_key] = {
                        "plan_number": i+1,
                        "plan_name": plan_info['text'],
                        "premium": plan_premium,
                        "coverage": plan_coverage,
                        "collected_at": datetime.now().isoformat()
                    }

                    logger.info(f"플랜 {i+1} 완료: {plan_premium}")

                except Exception as e:
                    logger.error(f"플랜 {i+1} 수집 중 오류: {str(e)}")
                    complete_data["plans"][plan_key] = {"error": str(e)}

        except Exception as e:
            logger.error(f"플랜 데이터 수집 중 오류: {str(e)}")

    async def get_plan_coverage(self, page):
        """현재 선택된 플랜의 보장내용 수집"""
        try:
            coverage_data = await page.evaluate("""
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

            return coverage_data

        except Exception as e:
            logger.error(f"보장내용 수집 중 오류: {str(e)}")
            return []

    async def collect_clauses_next_page(self, page, complete_data):
        """다음 페이지에서 특약 하나씩 활성화하여 보험료 확인"""
        try:
            # 모든 체크박스(특약) 찾기
            checkboxes_info = await page.evaluate("""
                () => {
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    return checkboxes.map((cb, index) => {
                        const parent = cb.closest('tr, div, li, .clause-item, label');
                        const text = parent ? parent.textContent.trim() : '';
                        const lines = text.split('\\n').filter(line => line.trim());

                        return {
                            index: index,
                            name: lines[0] ? lines[0].trim().substring(0, 100) : `특약_${index+1}`,
                            description: lines.length > 1 ? lines.slice(1).join(' ').trim().substring(0, 200) : null,
                            is_visible: cb.offsetParent !== null
                        };
                    }).filter(info => info.is_visible);  // 보이는 체크박스만
                }
            """)

            logger.info(f"발견된 특약 체크박스: {len(checkboxes_info)}개")

            base_premium = complete_data["premiums"]["base_premium"]

            # 각 특약별로 테스트
            for i, clause_info in enumerate(checkboxes_info[:20]):  # 최대 20개만
                try:
                    logger.info(f"특약 {i+1}/{len(checkboxes_info)} 테스트: {clause_info['name']}")

                    # 모든 체크박스 해제
                    await page.evaluate("""
                        () => {
                            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                            checkboxes.forEach(cb => {
                                if (cb.checked && cb.offsetParent !== null) {
                                    cb.checked = false;
                                    cb.dispatchEvent(new Event('change', { bubbles: true }));
                                }
                            });
                        }
                    """)
                    await self.wait_random(1, 2)

                    # 해당 특약만 활성화
                    await page.evaluate(f"""
                        () => {{
                            const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                            const visibleCheckboxes = checkboxes.filter(cb => cb.offsetParent !== null);
                            const targetCheckbox = visibleCheckboxes[{i}];
                            if (targetCheckbox) {{
                                targetCheckbox.checked = true;
                                targetCheckbox.click();
                                targetCheckbox.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                        }}
                    """)

                    await self.wait_random(3, 5)  # 보험료 재계산 대기

                    # 활성화된 보험료 확인
                    activated_premium = await self.get_current_premium(page)
                    premium_diff = self.calculate_premium_difference(base_premium, activated_premium)

                    # 툴팁 정보 수집
                    tooltip_info = await self.get_clause_tooltip(page, i)

                    clause_data = {
                        "index": i,
                        "name": clause_info['name'],
                        "description": clause_info['description'],
                        "base_premium": base_premium,
                        "with_clause_premium": activated_premium,
                        "premium_difference": premium_diff,
                        "tooltip": tooltip_info,
                        "is_tested": True
                    }

                    complete_data["special_clauses"].append(clause_data)
                    complete_data["premiums"]["clause_premiums"][f"clause_{i+1}"] = activated_premium

                    logger.info(f"특약 {i+1} 완료: {activated_premium} (차이: {premium_diff})")

                except Exception as e:
                    logger.error(f"특약 {i+1} 처리 중 오류: {str(e)}")
                    complete_data["special_clauses"].append({
                        "index": i,
                        "name": clause_info.get('name', f'특약_{i+1}'),
                        "error": str(e),
                        "is_tested": False
                    })

        except Exception as e:
            logger.error(f"특약 수집 중 오류: {str(e)}")

    def calculate_premium_difference(self, base_premium, activated_premium):
        """보험료 차이 계산"""
        try:
            if not base_premium or not activated_premium:
                return None

            # 숫자만 추출
            base_nums = re.findall(r'\d+', base_premium.replace(',', ''))
            activated_nums = re.findall(r'\d+', activated_premium.replace(',', ''))

            if base_nums and activated_nums:
                base_val = int(base_nums[0])
                activated_val = int(activated_nums[0])
                difference = activated_val - base_val
                return f"{difference:,}원" if difference != 0 else "0원"

            return None

        except Exception as e:
            logger.error(f"보험료 차이 계산 중 오류: {str(e)}")
            return None

    async def get_clause_tooltip(self, page, clause_index):
        """특약의 물음표 툴팁 정보 가져오기"""
        try:
            tooltip_info = await page.evaluate(f"""
                (index) => {{
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    const visibleCheckboxes = checkboxes.filter(cb => cb.offsetParent !== null);
                    const checkbox = visibleCheckboxes[index];

                    if (!checkbox) return null;

                    const parent = checkbox.closest('tr, div, li');
                    if (!parent) return null;

                    const tooltips = [];

                    // title 속성 확인
                    const elementsWithTitle = parent.querySelectorAll('[title]');
                    for (let el of elementsWithTitle) {{
                        const title = el.getAttribute('title');
                        if (title && title.trim()) {{
                            tooltips.push({{ type: 'title', content: title.trim() }});
                        }}
                    }}

                    // 물음표 아이콘 찾기
                    const questionIcons = parent.querySelectorAll('[class*="help"], [class*="question"], img[src*="help"], img[src*="question"]');
                    for (let icon of questionIcons) {{
                        const title = icon.getAttribute('title') || icon.getAttribute('alt');
                        if (title) {{
                            tooltips.push({{ type: 'icon', content: title.trim() }});
                        }}
                    }}

                    return tooltips.length > 0 ? tooltips : null;
                }}
            """, clause_index)

            return tooltip_info

        except Exception as e:
            logger.error(f"툴팁 정보 수집 중 오류: {str(e)}")
            return None

    async def collect_tooltips_next_page(self, page, complete_data):
        """다음 페이지의 모든 물음표 툴팁 데이터 수집"""
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
                            if (el.offsetParent === null) continue;  // 보이지 않는 요소 제외

                            const title = el.getAttribute('title');
                            const dataTooltip = el.getAttribute('data-tooltip');
                            const ariaDesc = el.getAttribute('aria-describedby');

                            if (title && title.trim()) {
                                tooltips[`tooltip_${count++}`] = {
                                    selector: selector,
                                    type: 'title_attribute',
                                    content: title.trim(),
                                    element_tag: el.tagName
                                };
                            }

                            if (dataTooltip && dataTooltip.trim()) {
                                tooltips[`tooltip_${count++}`] = {
                                    selector: selector,
                                    type: 'data_tooltip',
                                    content: dataTooltip.trim(),
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

    def validate_next_page_data(self, complete_data):
        """다음 페이지에서 수집된 데이터 검증"""
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

            # 플랜 데이터 (40점)
            if validation["plans_count"] >= 4:
                score += 40
            elif validation["plans_count"] >= 2:
                score += 25
            elif validation["plans_count"] >= 1:
                score += 10
            else:
                validation["missing_items"].append("플랜 데이터 부족")

            # 특약 데이터 (30점)
            if validation["clauses_count"] >= 15:
                score += 30
            elif validation["clauses_count"] >= 10:
                score += 25
            elif validation["clauses_count"] >= 5:
                score += 15
            elif validation["clauses_count"] >= 1:
                score += 5
            else:
                validation["missing_items"].append("특약 데이터 부족")

            # 기본 보험료 (20점)
            if validation["base_premium_exists"]:
                score += 20
            else:
                validation["missing_items"].append("기본 보험료 없음")

            # 툴팁 데이터 (10점)
            if validation["tooltips_count"] >= 10:
                score += 10
            elif validation["tooltips_count"] >= 5:
                score += 7
            elif validation["tooltips_count"] >= 1:
                score += 3
            else:
                validation["missing_items"].append("툴팁 데이터 부족")

            validation["completion_score"] = score
            complete_data["validation"] = validation

            logger.info("=== 다음 페이지 데이터 검증 결과 ===")
            logger.info(f"완성도 점수: {score}/100점")
            logger.info(f"수집된 플랜: {validation['plans_count']}/4개")
            logger.info(f"수집된 특약: {validation['clauses_count']}개")
            logger.info(f"수집된 툴팁: {validation['tooltips_count']}개")
            logger.info(f"기본 보험료: {'있음' if validation['base_premium_exists'] else '없음'}")

            if validation["missing_items"]:
                logger.warning(f"부족한 항목: {', '.join(validation['missing_items'])}")

        except Exception as e:
            logger.error(f"데이터 검증 중 오류: {str(e)}")

    async def save_next_page_data(self, data, age, gender):
        """다음 페이지에서 수집한 데이터 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"kb_next_page_{age}_{gender}_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"다음 페이지 데이터 저장 완료: {filename}")

            # 결과 요약 출력
            self.print_next_page_summary(data, age, gender)

            return filename

        except Exception as e:
            logger.error(f"데이터 저장 중 오류: {str(e)}")
            return None

    def print_next_page_summary(self, data, age, gender):
        """다음 페이지 수집 결과 요약 출력"""
        print("\n" + "="*80)
        print(f"🎯 KB생명 다음 페이지 완전 데이터 수집 결과 - {age}세 {gender}")
        print("="*80)

        validation = data.get("validation", {})
        print(f"📊 완성도 점수: {validation.get('completion_score', 0)}/100점")

        print(f"\n💰 기본 보험료: {data.get('premiums', {}).get('base_premium', 'N/A')}")

        print(f"\n📋 수집된 플랜: {validation.get('plans_count', 0)}/4개")
        for plan_name, plan_data in data.get("plans", {}).items():
            if not plan_data.get("error"):
                premium = plan_data.get("premium", "N/A")
                name = plan_data.get("plan_name", plan_name)
                print(f"   • {name}: {premium}")

        print(f"\n✅ 수집된 특약: {len(data.get('special_clauses', []))}개")
        clauses = data.get("special_clauses", [])
        for i, clause in enumerate(clauses[:5]):  # 처음 5개만
            name = clause.get("name", f"특약_{i+1}")
            premium = clause.get("with_clause_premium", "N/A")
            diff = clause.get("premium_difference", "N/A")
            print(f"   • {name}: {premium} (차이: {diff})")

        if len(clauses) > 5:
            print(f"   • ... 그 외 {len(clauses) - 5}개 특약")

        print(f"\n❓ 수집된 툴팁: {len(data.get('tooltips', {}))}개")

        missing = validation.get('missing_items', [])
        if missing:
            print(f"\n⚠️  부족한 데이터: {', '.join(missing)}")

        print("="*80)

    async def run_next_page_test(self, age=30, gender="남성"):
        """다음 페이지 완전 수집 테스트 실행"""
        logger.info("🚀 KB생명 다음 페이지 완전 데이터 수집 테스트 시작")

        result = await self.scrape_complete_with_next_page(age, gender)

        if result:
            filename = await self.save_next_page_data(result, age, gender)
            logger.info(f"✅ 다음 페이지 완전 데이터 수집 성공! 파일: {filename}")
            return result
        else:
            logger.error("❌ 다음 페이지 완전 데이터 수집 실패!")
            return None

async def main():
    scraper = KBNextPageScraper()
    await scraper.run_next_page_test(30, "남성")

if __name__ == "__main__":
    asyncio.run(main())