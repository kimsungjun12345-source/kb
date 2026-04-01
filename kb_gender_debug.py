import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBGenderDebugger:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        return browser, context

    async def debug_gender_selection(self):
        """성별 선택 디버깅"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info("🔍 KB생명 성별 선택 디버깅 시작")

                # 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle")
                await asyncio.sleep(3)

                logger.info("📋 1단계: 모든 라디오 버튼 분석")
                all_radios = await page.evaluate("""
                    () => {
                        const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                        return radios.map((radio, index) => ({
                            index: index,
                            name: radio.name,
                            value: radio.value,
                            id: radio.id,
                            checked: radio.checked,
                            disabled: radio.disabled,
                            visible: radio.offsetParent !== null,
                            className: radio.className,
                            outerHTML: radio.outerHTML.substring(0, 200)
                        }));
                    }
                """)

                logger.info(f"발견된 라디오 버튼: {len(all_radios)}개")
                for radio in all_radios:
                    logger.info(f"  [{radio['index']}] name={radio['name']}, value={radio['value']}, "
                              f"visible={radio['visible']}, disabled={radio['disabled']}")

                logger.info("\n📋 2단계: 성별 관련 라디오 버튼 상세 분석")
                gender_analysis = await page.evaluate("""
                    () => {
                        const genderRadios = document.querySelectorAll('input[name="genderCode"]');
                        const analysis = [];

                        genderRadios.forEach((radio, index) => {
                            const parent = radio.closest('div, label, span, td');
                            const parentText = parent ? parent.textContent?.trim() : '';

                            analysis.push({
                                index: index,
                                value: radio.value,
                                checked: radio.checked,
                                disabled: radio.disabled,
                                visible: radio.offsetParent !== null,
                                offsetWidth: radio.offsetWidth,
                                offsetHeight: radio.offsetHeight,
                                parentTagName: parent ? parent.tagName : null,
                                parentText: parentText.substring(0, 50),
                                outerHTML: radio.outerHTML,
                                computedStyle: window.getComputedStyle(radio).display
                            });
                        });

                        return analysis;
                    }
                """)

                logger.info(f"성별 라디오 버튼: {len(gender_analysis)}개")
                for i, radio in enumerate(gender_analysis):
                    logger.info(f"  성별 {i+1}: value={radio['value']}, visible={radio['visible']}, "
                              f"display={radio['computedStyle']}, size={radio['offsetWidth']}x{radio['offsetHeight']}")
                    logger.info(f"    부모: {radio['parentTagName']} - {radio['parentText']}")
                    logger.info(f"    HTML: {radio['outerHTML']}")

                logger.info("\n📋 3단계: 다양한 선택 방법 테스트")

                # 방법 1: JavaScript에서 직접 클릭 시뮬레이션
                logger.info("테스트 1: JavaScript 직접 클릭")
                result1 = await page.evaluate("""
                    () => {
                        const radios = document.querySelectorAll('input[name="genderCode"]');
                        let results = [];

                        for (let radio of radios) {
                            try {
                                if (radio.value === 'M') {
                                    // 다양한 클릭 시도
                                    radio.focus();
                                    radio.checked = true;
                                    radio.click();

                                    results.push({
                                        method: 'direct_click',
                                        success: radio.checked,
                                        value: radio.value
                                    });
                                }
                            } catch (e) {
                                results.push({
                                    method: 'direct_click',
                                    success: false,
                                    error: e.message
                                });
                            }
                        }

                        return results;
                    }
                """)

                for result in result1:
                    logger.info(f"  결과: {result}")

                # 방법 2: 부모 요소 클릭
                logger.info("테스트 2: 부모 요소 클릭")
                result2 = await page.evaluate("""
                    () => {
                        const radios = document.querySelectorAll('input[name="genderCode"]');
                        let results = [];

                        for (let radio of radios) {
                            if (radio.value === 'M') {
                                const parent = radio.closest('div, label, span');
                                if (parent) {
                                    try {
                                        parent.click();
                                        results.push({
                                            method: 'parent_click',
                                            success: radio.checked,
                                            parentTag: parent.tagName
                                        });
                                    } catch (e) {
                                        results.push({
                                            method: 'parent_click',
                                            success: false,
                                            error: e.message
                                        });
                                    }
                                }
                            }
                        }

                        return results;
                    }
                """)

                for result in result2:
                    logger.info(f"  결과: {result}")

                # 방법 3: 이벤트 디스패치
                logger.info("테스트 3: 이벤트 디스패치")
                result3 = await page.evaluate("""
                    () => {
                        const radios = document.querySelectorAll('input[name="genderCode"]');
                        let results = [];

                        for (let radio of radios) {
                            if (radio.value === 'M') {
                                try {
                                    radio.checked = true;

                                    // 다양한 이벤트 발생
                                    const events = ['mousedown', 'mouseup', 'click', 'change', 'input'];
                                    for (let eventType of events) {
                                        const event = new Event(eventType, { bubbles: true, cancelable: true });
                                        radio.dispatchEvent(event);
                                    }

                                    results.push({
                                        method: 'event_dispatch',
                                        success: radio.checked,
                                        value: radio.value
                                    });
                                } catch (e) {
                                    results.push({
                                        method: 'event_dispatch',
                                        success: false,
                                        error: e.message
                                    });
                                }
                            }
                        }

                        return results;
                    }
                """)

                for result in result3:
                    logger.info(f"  결과: {result}")

                # 최종 상태 확인
                logger.info("\n📋 4단계: 최종 성별 선택 상태 확인")
                final_state = await page.evaluate("""
                    () => {
                        const radios = document.querySelectorAll('input[name="genderCode"]');
                        return Array.from(radios).map(radio => ({
                            value: radio.value,
                            checked: radio.checked
                        }));
                    }
                """)

                for state in final_state:
                    logger.info(f"  성별 {state['value']}: {'선택됨' if state['checked'] else '선택안됨'}")

                input("분석 완료. 엔터를 눌러 종료하세요...")

            finally:
                await browser.close()

async def main():
    debugger = KBGenderDebugger()
    await debugger.debug_gender_selection()

if __name__ == "__main__":
    asyncio.run(main())