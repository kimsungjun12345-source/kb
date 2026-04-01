import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBPlanAnalyzer:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,  # 분석용이니까 화면으로 보자
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        return browser, context

    def generate_birthdate(self, age=30):
        current_year = datetime.now().year
        birth_year = current_year - age
        return f"{birth_year}0315"  # 고정된 날짜로

    async def wait_random(self, min_seconds=2, max_seconds=4):
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def analyze_page_structure(self):
        """페이지 구조 상세 분석"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info("🔍 KB생명 페이지 구조 분석 시작")

                # 1. 초기 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle", timeout=60000)
                await self.wait_random(3, 5)

                logger.info("📄 1단계: 초기 페이지 분석")
                await self.analyze_initial_page(page)

                # 2. 기본 정보 입력
                logger.info("✏️ 2단계: 기본 정보 입력")
                await self.fill_basic_info(page)

                # 3. 계산 버튼 클릭 후 분석
                logger.info("🔄 3단계: 계산 후 페이지 분석")
                await self.analyze_after_calculation(page)

                # 4. 플랜별 상세 분석
                logger.info("📋 4단계: 플랜별 상세 분석")
                await self.analyze_plans(page)

                # 5. 특약 구조 분석
                logger.info("⚡ 5단계: 특약 구조 분석")
                await self.analyze_special_clauses(page)

                input("분석 완료. 엔터를 눌러 종료하세요...")

            finally:
                await browser.close()

    async def analyze_initial_page(self, page):
        """초기 페이지 구조 분석"""
        try:
            # 페이지 기본 정보
            title = await page.title()
            url = page.url
            logger.info(f"페이지 제목: {title}")
            logger.info(f"현재 URL: {url}")

            # 입력 필드 확인
            birthday_field = await page.query_selector("#birthday")
            if birthday_field:
                logger.info("✅ 생년월일 입력 필드 확인됨")

            # 성별 라디오 버튼 확인
            gender_radios = await page.query_selector_all("input[name='genderCode']")
            logger.info(f"✅ 성별 선택 옵션: {len(gender_radios)}개")

            # 계산 버튼 확인
            buttons = await page.evaluate("""
                () => {
                    const buttons = Array.from(document.querySelectorAll('button'));
                    return buttons.map(btn => ({
                        text: btn.textContent?.trim(),
                        visible: btn.offsetParent !== null
                    })).filter(btn => btn.text && btn.text.length > 0);
                }
            """)

            logger.info(f"📋 발견된 버튼들:")
            for btn in buttons:
                logger.info(f"  - {btn['text']} (보임: {btn['visible']})")

        except Exception as e:
            logger.error(f"초기 페이지 분석 오류: {str(e)}")

    async def fill_basic_info(self, page):
        """기본 정보 입력"""
        try:
            # 생년월일 입력
            birthdate = self.generate_birthdate(30)
            await page.fill("#birthday", birthdate)
            logger.info(f"생년월일 입력: {birthdate}")

            # 성별 선택 (남성)
            await page.evaluate("""
                const radios = document.querySelectorAll('input[name="genderCode"]');
                for (let radio of radios) {
                    if (radio.value === 'M') {
                        radio.checked = true;
                        radio.click();
                        radio.dispatchEvent(new Event('change', { bubbles: true }));
                        break;
                    }
                }
            """)
            logger.info("성별 선택: 남성")

            await self.wait_random(1, 2)

        except Exception as e:
            logger.error(f"기본 정보 입력 오류: {str(e)}")

    async def analyze_after_calculation(self, page):
        """계산 후 페이지 분석"""
        try:
            # 계산 버튼 클릭
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
                logger.info(f"✅ 버튼 클릭: {button_clicked}")
            else:
                logger.warning("❌ 계산 버튼을 찾을 수 없음")
                return

            # 페이지 변화 대기
            await self.wait_random(5, 8)

            # 현재 URL 확인
            current_url = page.url
            logger.info(f"변경된 URL: {current_url}")

            # 페이지 콘텐츠 분석
            await self.analyze_page_content(page)

        except Exception as e:
            logger.error(f"계산 후 분석 오류: {str(e)}")

    async def analyze_page_content(self, page):
        """페이지 콘텐츠 상세 분석"""
        try:
            # 보험료 관련 요소 찾기
            premium_elements = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const premiums = [];

                    elements.forEach((el, index) => {
                        const text = el.textContent?.trim();
                        if (text && text.includes('원') && /\\d{1,3}(,\\d{3})*/.test(text) &&
                            el.offsetParent !== null && text.length < 100) {
                            premiums.push({
                                index: index,
                                text: text.substring(0, 80),
                                tagName: el.tagName,
                                className: el.className,
                                id: el.id
                            });
                        }
                    });

                    return premiums.slice(0, 10); // 상위 10개만
                }
            """)

            logger.info(f"💰 발견된 보험료 관련 요소: {len(premium_elements)}개")
            for elem in premium_elements[:5]:  # 상위 5개만 출력
                logger.info(f"  - {elem['tagName']}: {elem['text']}")

        except Exception as e:
            logger.error(f"페이지 콘텐츠 분석 오류: {str(e)}")

    async def analyze_plans(self, page):
        """플랜별 상세 분석"""
        try:
            # 플랜 관련 라디오 버튼 찾기
            plan_radios = await page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    const planRadios = [];

                    radios.forEach((radio, index) => {
                        if (radio.name && radio.name !== 'genderCode') {
                            const parent = radio.closest('tr, div, li');
                            const text = parent ? parent.textContent?.trim().substring(0, 100) : '';

                            planRadios.push({
                                index: index,
                                name: radio.name,
                                value: radio.value,
                                checked: radio.checked,
                                text: text,
                                visible: radio.offsetParent !== null
                            });
                        }
                    });

                    return planRadios;
                }
            """)

            logger.info(f"📋 발견된 플랜 옵션: {len(plan_radios)}개")
            for plan in plan_radios:
                logger.info(f"  - [{plan['name']}={plan['value']}] {plan['text'][:50]} (체크: {plan['checked']}, 보임: {plan['visible']})")

            # 각 플랜 테스트 (처음 4개만)
            for i, plan in enumerate(plan_radios[:4]):
                if plan['visible']:
                    logger.info(f"🔄 플랜 {i+1} 테스트 중...")

                    # 플랜 선택
                    await page.evaluate(f"""
                        const radios = document.querySelectorAll('input[type="radio"]');
                        const targetRadio = Array.from(radios).find(r =>
                            r.name === '{plan["name"]}' && r.value === '{plan["value"]}'
                        );
                        if (targetRadio && targetRadio.offsetParent !== null) {{
                            targetRadio.checked = true;
                            targetRadio.click();
                            targetRadio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    """)

                    await self.wait_random(2, 3)

                    # 변경된 보험료 확인
                    await self.check_premium_change(page, f"플랜 {i+1}")

        except Exception as e:
            logger.error(f"플랜 분석 오류: {str(e)}")

    async def analyze_special_clauses(self, page):
        """특약 구조 상세 분석"""
        try:
            # 모든 체크박스 분석
            checkboxes_info = await page.evaluate("""
                () => {
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    const info = [];

                    checkboxes.forEach((checkbox, index) => {
                        const parent = checkbox.closest('tr, div, label');
                        const text = parent ? parent.textContent?.trim().substring(0, 150) : '';

                        info.push({
                            index: index,
                            text: text,
                            checked: checkbox.checked,
                            disabled: checkbox.disabled,
                            visible: checkbox.offsetParent !== null,
                            name: checkbox.name || '',
                            value: checkbox.value || '',
                            id: checkbox.id || '',
                            className: checkbox.className || ''
                        });
                    });

                    return info;
                }
            """)

            logger.info(f"☑️ 발견된 체크박스: {len(checkboxes_info)}개")

            # 카테고리별 분류
            insurance_related = []
            terms_related = []
            others = []

            for cb in checkboxes_info:
                text = cb['text'].lower()
                if any(keyword in text for keyword in ['특약', '보장', '급여', '질환', '상해', '수술', '암', '뇌']):
                    insurance_related.append(cb)
                elif any(keyword in text for keyword in ['동의', '약관', '개인정보', '통신사']):
                    terms_related.append(cb)
                else:
                    others.append(cb)

            logger.info(f"🏥 보험 관련: {len(insurance_related)}개")
            logger.info(f"📋 약관 관련: {len(terms_related)}개")
            logger.info(f"❓ 기타: {len(others)}개")

            # 보험 관련 체크박스 상세 분석
            logger.info("\n🏥 보험 관련 체크박스 상세:")
            for i, cb in enumerate(insurance_related[:10]):
                status = []
                if cb['checked']: status.append("체크됨")
                if cb['disabled']: status.append("비활성화")
                if not cb['visible']: status.append("보이지않음")

                status_str = f"({', '.join(status)})" if status else "(정상)"
                logger.info(f"  {i+1}. {cb['text'][:60]} {status_str}")

            # 실제 클릭 테스트 (처음 3개만)
            logger.info("\n🧪 클릭 테스트 시작:")
            for i, cb in enumerate(insurance_related[:3]):
                if cb['visible'] and not cb['disabled'] and not cb['checked']:
                    try:
                        logger.info(f"  테스트 {i+1}: {cb['text'][:40]}")

                        # 체크박스 클릭
                        await page.evaluate(f"""
                            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                            const target = checkboxes[{cb['index']}];
                            if (target && target.offsetParent !== null) {{
                                target.click();
                            }}
                        """)

                        await asyncio.sleep(2)

                        # 보험료 변화 확인
                        await self.check_premium_change(page, f"특약 {i+1}")

                        # 체크 해제
                        await page.evaluate(f"""
                            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                            const target = checkboxes[{cb['index']}];
                            if (target && target.checked) {{
                                target.click();
                            }}
                        """)

                        await asyncio.sleep(1)
                        logger.info(f"  ✅ 테스트 완료")

                    except Exception as e:
                        logger.warning(f"  ❌ 테스트 실패: {str(e)}")

        except Exception as e:
            logger.error(f"특약 분석 오류: {str(e)}")

    async def check_premium_change(self, page, context):
        """보험료 변화 확인"""
        try:
            premium_info = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));

                    for (let el of elements) {
                        const text = el.textContent?.trim();
                        if (text && text.includes('원') && /\\d{1,3}(,\\d{3})*/.test(text) &&
                            el.offsetParent !== null && text.length < 50) {
                            const match = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                            if (match) {
                                return {
                                    amount: match[1],
                                    fullText: text
                                };
                            }
                        }
                    }
                    return null;
                }
            """)

            if premium_info:
                logger.info(f"    💰 {context} 보험료: {premium_info['amount']}원")
            else:
                logger.info(f"    ❓ {context} 보험료를 찾을 수 없음")

        except Exception as e:
            logger.warning(f"보험료 확인 오류: {str(e)}")

async def main():
    analyzer = KBPlanAnalyzer()
    await analyzer.analyze_page_structure()

if __name__ == "__main__":
    asyncio.run(main())