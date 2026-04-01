#!/usr/bin/env python3
"""
KB Life 건강보험 스크래퍼 자동 실행 스크립트
Playwright를 사용하여 자동화된 스크래핑 실행
"""

import asyncio
import os
from playwright.async_api import async_playwright

async def run_health_scraper():
    """건강보험 스크래퍼 자동 실행"""

    # 스크래퍼 파일 경로
    scraper_path = "sanhak-hyeopryuk/chrome_extension/scraper_health.js"

    if not os.path.exists(scraper_path):
        print(f"❌ 스크래퍼 파일을 찾을 수 없습니다: {scraper_path}")
        return

    # 스크래퍼 스크립트 로드
    with open(scraper_path, 'r', encoding='utf-8') as f:
        scraper_script = f.read()

    async with async_playwright() as p:
        print("🚀 KB Life 건강보험 스크래퍼 시작...")

        # 브라우저 실행 (헤드리스 모드 비활성화)
        browser = await p.chromium.launch(
            headless=False,  # 브라우저 창 표시
            args=['--disable-web-security', '--disable-features=VizDisplayCompositor']
        )

        # 모바일 디바이스 에뮬레이션
        context = await browser.new_context(
            **p.devices['iPhone 12'],
            locale='ko-KR'
        )

        page = await context.new_page()

        try:
            print("📱 KB Life 모바일 사이트 접속...")
            await page.goto('https://m.kblife.co.kr', timeout=30000)

            print("⏳ 페이지 로딩 대기...")
            await page.wait_for_load_state('networkidle')

            print("🔧 스크래퍼 스크립트 주입...")
            await page.evaluate(scraper_script)

            print("✅ 스크래퍼 준비 완료!")
            print("\n📋 다음 단계를 수동으로 진행해주세요:")
            print("1. e-건강보험 상품 페이지로 이동")
            print("2. 보험료 계산을 1회 실행 (ajax 객체 활성화)")
            print("3. 개발자도구(F12) → 콘솔에서 다음 명령어 실행:")
            print("   window.__scrapeHealth('337600104', 'e건강보험_일반심사')")
            print("   window.__scrapeHealth('331600104', 'e건강보험_간편심사355')")

            print("\n⌨️  브라우저를 닫으려면 Enter 키를 누르세요...")
            input()

        except Exception as e:
            print(f"❌ 오류 발생: {e}")

        finally:
            await browser.close()
            print("🏁 스크래퍼 종료")

if __name__ == "__main__":
    print("=" * 50)
    print("KB Life 건강보험 스크래퍼 자동화 도구")
    print("=" * 50)

    # Playwright 설치 확인
    try:
        import playwright
        print("✅ Playwright 설치 확인됨")
    except ImportError:
        print("❌ Playwright가 설치되지 않았습니다.")
        print("설치 명령어: pip install playwright && playwright install")
        exit(1)

    asyncio.run(run_health_scraper())