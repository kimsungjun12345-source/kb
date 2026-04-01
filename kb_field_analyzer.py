#!/usr/bin/env python3
"""
KB생명 사이트 실제 필드 분석기
"""

import asyncio
import json
from datetime import datetime
from playwright.async_api import async_playwright

class KBFieldAnalyzer:
    def __init__(self):
        self.browser = None
        self.page = None

    async def setup_browser(self):
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=False)
        context = await self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.page = await context.new_page()

    async def analyze_page(self, url):
        print(f"페이지 분석 중: {url}")
        await self.page.goto(url)
        await asyncio.sleep(5)

        # 모든 input 필드 분석
        inputs = await self.page.query_selector_all('input')
        print(f"\n=== INPUT 필드들 ({len(inputs)}개) ===")

        for i, inp in enumerate(inputs):
            try:
                tag_name = await inp.evaluate('el => el.tagName')
                input_type = await inp.get_attribute('type') or 'text'
                name = await inp.get_attribute('name') or ''
                id_attr = await inp.get_attribute('id') or ''
                class_attr = await inp.get_attribute('class') or ''
                placeholder = await inp.get_attribute('placeholder') or ''

                print(f"{i+1:2d}. type='{input_type}' name='{name}' id='{id_attr}' class='{class_attr}' placeholder='{placeholder}'")
            except:
                print(f"{i+1:2d}. (분석 실패)")

        # 모든 select 필드 분석
        selects = await self.page.query_selector_all('select')
        print(f"\n=== SELECT 필드들 ({len(selects)}개) ===")

        for i, sel in enumerate(selects):
            try:
                name = await sel.get_attribute('name') or ''
                id_attr = await sel.get_attribute('id') or ''
                class_attr = await sel.get_attribute('class') or ''

                print(f"{i+1:2d}. name='{name}' id='{id_attr}' class='{class_attr}'")
            except:
                print(f"{i+1:2d}. (분석 실패)")

        # 모든 button 분석
        buttons = await self.page.query_selector_all('button')
        print(f"\n=== BUTTON 요소들 ({len(buttons)}개) ===")

        for i, btn in enumerate(buttons):
            try:
                text = await btn.inner_text()
                id_attr = await btn.get_attribute('id') or ''
                class_attr = await btn.get_attribute('class') or ''
                onclick = await btn.get_attribute('onclick') or ''

                print(f"{i+1:2d}. text='{text.strip()[:30]}' id='{id_attr}' class='{class_attr}' onclick='{onclick[:50]}'")
            except:
                print(f"{i+1:2d}. (분석 실패)")

        # 페이지 전체 HTML도 출력 (일부만)
        print("\n=== 페이지 HTML 일부 ===")
        body_html = await self.page.inner_html('body')

        # 생년월일, 성별 관련 부분만 추출
        lines = body_html.split('\n')
        relevant_lines = []

        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['birth', '생년', '출생', 'gender', '성별', 'male', 'female', '남성', '여성']):
                relevant_lines.append(line.strip())

        print("관련 HTML 라인들:")
        for line in relevant_lines[:20]:  # 처음 20개만
            if line:
                print(f"  {line}")

        print("\n분석 완료!")

    async def run(self):
        try:
            await self.setup_browser()

            # KB생명 착한암보험 페이지 분석
            url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5"
            await self.analyze_page(url)

            print("\n엔터를 누르면 브라우저가 닫힙니다...")
            input()

        finally:
            if self.browser:
                await self.browser.close()

async def main():
    analyzer = KBFieldAnalyzer()
    await analyzer.run()

if __name__ == "__main__":
    print("KB생명 사이트 필드 분석기")
    print("실제 HTML 구조를 파악하여 정확한 필드명을 찾습니다.")
    print("=" * 50)

    asyncio.run(main())