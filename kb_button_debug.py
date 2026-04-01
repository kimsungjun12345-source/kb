import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBButtonDebugger:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async def create_browser(self, playwright):
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        return browser, context

    def generate_birthdate(self, age=30):
        from datetime import datetime
        current_year = datetime.now().year
        birth_year = current_year - age
        return f"{birth_year}0315"

    async def debug_calculation_flow(self):
        """보험료 계산 흐름 디버깅"""
        async with async_playwright() as playwright:
            browser, context = await self.create_browser(playwright)

            try:
                page = await context.new_page()
                logger.info("🔍 보험료 계산 흐름 디버깅 시작")

                # 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle")
                await asyncio.sleep(3)

                logger.info("📋 1단계: 초기 페이지 상태 확인")
                current_url = page.url
                logger.info(f"현재 URL: {current_url}")

                # 모든 버튼 확인
                all_buttons = await page.evaluate("""
                    () => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        return buttons.map((btn, index) => ({
                            index: index,
                            text: btn.textContent?.trim(),
                            visible: btn.offsetParent !== null,
                            disabled: btn.disabled,
                            className: btn.className,
                            id: btn.id,
                            onclick: btn.getAttribute('onclick'),
                            type: btn.type
                        })).filter(btn => btn.text && btn.text.length > 0);
                    }
                """)

                logger.info(f"발견된 버튼: {len(all_buttons)}개")
                for btn in all_buttons:
                    if '계산' in btn['text'] or '설계' in btn['text'] or '견적' in btn['text']:
                        logger.info(f"  중요 버튼: {btn['text']} - 보임:{btn['visible']}, 활성:{not btn['disabled']}")
                        logger.info(f"    클래스: {btn['className']}, onclick: {btn['onclick']}")

                logger.info("📋 2단계: 생년월일 입력")
                birthdate = self.generate_birthdate(30)
                await page.fill("#birthday", birthdate)
                logger.info(f"생년월일 입력 완료: {birthdate}")
                await asyncio.sleep(1)

                # 생년월일 입력 후 버튼 상태 변화 확인
                buttons_after_birth = await page.evaluate("""
                    () => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        return buttons.filter(btn => {
                            const text = btn.textContent?.trim() || '';
                            return text.includes('계산') || text.includes('설계') || text.includes('견적');
                        }).map(btn => ({
                            text: btn.textContent?.trim(),
                            visible: btn.offsetParent !== null,
                            disabled: btn.disabled,
                            className: btn.className
                        }));
                    }
                """)

                logger.info("생년월일 입력 후 중요 버튼 상태:")
                for btn in buttons_after_birth:
                    logger.info(f"  {btn['text']}: 보임={btn['visible']}, 활성={not btn['disabled']}")

                logger.info("📋 3단계: 성별 선택")
                success = await page.evaluate("""
                    () => {
                        const radios = document.querySelectorAll('input[name="genderCode"]');
                        for (let radio of radios) {
                            if (radio.value === '1') {
                                radio.checked = true;
                                radio.click();
                                radio.dispatchEvent(new Event('change', { bubbles: true }));
                                return true;
                            }
                        }
                        return false;
                    }
                """)

                if success:
                    logger.info("✅ 성별 선택 성공")
                else:
                    logger.error("❌ 성별 선택 실패")

                await asyncio.sleep(2)

                # 성별 선택 후 버튼 상태 변화 확인
                buttons_after_gender = await page.evaluate("""
                    () => {
                        const buttons = Array.from(document.querySelectorAll('button'));
                        return buttons.filter(btn => {
                            const text = btn.textContent?.trim() || '';
                            return text.includes('계산') || text.includes('설계') || text.includes('견적');
                        }).map(btn => ({
                            text: btn.textContent?.trim(),
                            visible: btn.offsetParent !== null,
                            disabled: btn.disabled,
                            className: btn.className,
                            onclick: btn.getAttribute('onclick')
                        }));
                    }
                """)

                logger.info("성별 선택 후 중요 버튼 상태:")
                for btn in buttons_after_gender:
                    logger.info(f"  {btn['text']}: 보임={btn['visible']}, 활성={not btn['disabled']}")
                    if btn['onclick']:
                        logger.info(f"    onclick: {btn['onclick']}")

                logger.info("📋 4단계: 계산 버튼 클릭 시도")

                # 다양한 방법으로 버튼 클릭 시도
                click_results = []

                # 방법 1: 텍스트 기반 검색 후 클릭
                result1 = await page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (let button of buttons) {
                            const text = button.textContent || button.innerText;
                            if (text.includes('계산') || text.includes('설계') || text.includes('견적')) {
                                try {
                                    button.click();
                                    return { method: '텍스트검색클릭', success: true, text: text.trim() };
                                } catch (e) {
                                    return { method: '텍스트검색클릭', success: false, error: e.message };
                                }
                            }
                        }
                        return { method: '텍스트검색클릭', success: false, error: '버튼을 찾을 수 없음' };
                    }
                """)
                click_results.append(result1)
                logger.info(f"방법 1 결과: {result1}")

                await asyncio.sleep(2)

                # 방법 2: CSS 선택자로 클릭
                calc_buttons = [
                    ".button-cal",
                    "[class*='calc']",
                    "[class*='calculate']",
                    "[onclick*='calc']",
                    "button[type='button']"
                ]

                for selector in calc_buttons:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            if '계산' in text or '설계' in text or '견적' in text:
                                await element.click()
                                result = { 'method': f'CSS선택자:{selector}', 'success': True, 'text': text }
                                click_results.append(result)
                                logger.info(f"CSS 선택자 성공: {result}")
                                break
                    except Exception as e:
                        logger.debug(f"CSS 선택자 {selector} 실패: {str(e)}")

                await asyncio.sleep(3)

                # 클릭 후 페이지 상태 확인
                after_click_url = page.url
                logger.info(f"클릭 후 URL: {after_click_url}")

                if current_url != after_click_url:
                    logger.info("✅ 페이지 이동 성공!")
                else:
                    logger.warning("⚠️ 페이지 이동이 없음")

                # 새 페이지에서 특약 관련 요소 확인
                insurance_elements = await page.evaluate("""
                    () => {
                        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                        const radios = document.querySelectorAll('input[type="radio"]');
                        const premiums = [];

                        // 보험료 패턴 찾기
                        const allElements = Array.from(document.querySelectorAll('*'));
                        for (let el of allElements) {
                            const text = el.textContent?.trim();
                            if (text && text.includes('원') && /\\d{1,3}(,\\d{3})*/.test(text) &&
                                el.offsetParent !== null && text.length < 50) {
                                premiums.push(text.substring(0, 50));
                            }
                        }

                        return {
                            checkboxes: checkboxes.length,
                            radios: radios.length,
                            premiums: premiums.slice(0, 5)
                        };
                    }
                """)

                logger.info(f"새 페이지 상태:")
                logger.info(f"  체크박스: {insurance_elements['checkboxes']}개")
                logger.info(f"  라디오 버튼: {insurance_elements['radios']}개")
                logger.info(f"  발견된 보험료: {insurance_elements['premiums']}")

                input("디버깅 완료. 엔터를 눌러 종료하세요...")

            finally:
                await browser.close()

async def main():
    debugger = KBButtonDebugger()
    await debugger.debug_calculation_flow()

if __name__ == "__main__":
    asyncio.run(main())