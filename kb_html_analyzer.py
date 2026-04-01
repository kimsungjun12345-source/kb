import asyncio
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def analyze_kb_structure():
    """KB생명 페이지 구조 분석"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        try:
            page = await context.new_page()

            # 1단계: 기본 페이지 로드
            logger.info("🔍 KB생명 페이지 접속 중...")
            await page.goto("https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5",
                           wait_until="networkidle")
            await asyncio.sleep(3)

            # 2단계: 생년월일/성별 입력
            logger.info("📝 생년월일/성별 입력 중...")
            await page.fill("#birthday", "19961104")
            await asyncio.sleep(1)

            # 성별 선택 (남성)
            await page.click('input[name="genderCode"][value="1"]')
            await asyncio.sleep(1)

            # 계산하기 버튼 클릭
            logger.info("🔢 계산하기 버튼 클릭...")
            await page.click("#calculateResult")
            await page.wait_for_load_state("networkidle", timeout=15000)
            await asyncio.sleep(5)

            # 3단계: 결과 페이지에서 플랜/특약 구조 분석
            logger.info("📊 플랜 및 특약 구조 분석 중...")

            # 모든 라디오 버튼 찾기 (플랜 선택용)
            radio_buttons = await page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                    return radios.map((radio, index) => {
                        const parent = radio.closest('div, tr, label, li');
                        const text = parent ? parent.textContent.trim() : '';
                        return {
                            index: index,
                            name: radio.name,
                            value: radio.value,
                            id: radio.id || '',
                            className: radio.className,
                            text: text.substring(0, 100),
                            checked: radio.checked,
                            visible: radio.offsetParent !== null
                        };
                    });
                }
            """)

            # 모든 체크박스 찾기 (특약용)
            checkboxes = await page.evaluate("""
                () => {
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    return checkboxes.map((checkbox, index) => {
                        const parent = checkbox.closest('div, tr, label, li');
                        const text = parent ? parent.textContent.trim() : '';
                        return {
                            index: index,
                            name: checkbox.name || '',
                            value: checkbox.value || '',
                            id: checkbox.id || '',
                            className: checkbox.className,
                            text: text.substring(0, 150),
                            enabled: !checkbox.disabled,
                            visible: checkbox.offsetParent !== null
                        };
                    });
                }
            """)

            # 선택(select) 요소들 찾기 (기간 선택용)
            selects = await page.evaluate("""
                () => {
                    const selects = Array.from(document.querySelectorAll('select'));
                    return selects.map((select, index) => {
                        const parent = select.closest('div, tr, label');
                        const text = parent ? parent.textContent.trim() : '';
                        const options = Array.from(select.options).map(opt => ({
                            value: opt.value,
                            text: opt.textContent
                        }));
                        return {
                            index: index,
                            name: select.name || '',
                            id: select.id || '',
                            className: select.className,
                            text: text.substring(0, 100),
                            options: options
                        };
                    });
                }
            """)

            # 결과 출력
            print("\n" + "="*80)
            print("🎯 KB생명 페이지 구조 분석 결과")
            print("="*80)

            print(f"\n📻 라디오 버튼 ({len(radio_buttons)}개):")
            for i, radio in enumerate(radio_buttons):
                if radio['name'] != 'genderCode':  # 성별 제외
                    print(f"  {i+1}. name='{radio['name']}' value='{radio['value']}'")
                    print(f"      text: {radio['text'][:60]}")
                    print(f"      visible: {radio['visible']}, checked: {radio['checked']}")
                    print()

            print(f"\n☑️ 체크박스 ({len(checkboxes)}개):")
            for i, cb in enumerate(checkboxes):
                if any(keyword in cb['text'].lower() for keyword in ['특약', '보장', '질환', '암', '뇌', '심장']):
                    print(f"  {i+1}. name='{cb['name']}' value='{cb['value']}'")
                    print(f"      text: {cb['text'][:80]}")
                    print(f"      enabled: {cb['enabled']}, visible: {cb['visible']}")
                    print()

            print(f"\n📋 선택 요소 ({len(selects)}개):")
            for i, sel in enumerate(selects):
                print(f"  {i+1}. name='{sel['name']}' id='{sel['id']}'")
                print(f"      text: {sel['text'][:60]}")
                print(f"      options: {[opt['text'] for opt in sel['options'][:5]]}")
                print()

            input("분석 완료! 브라우저에서 수동으로 확인해보시고 엔터를 눌러주세요...")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(analyze_kb_structure())