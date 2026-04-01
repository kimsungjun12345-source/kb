"""
KB Life 상품명 확인
페이지에서 실제 상품명과 상품 상세 정보를 추출
"""

import asyncio
from playwright.async_api import async_playwright

async def check_product_name():
    """상품명 확인"""
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={"width": 1400, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        # webdriver 감지 우회
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        page = await context.new_page()

        try:
            url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
            print(f"페이지 접속: {url}")

            await page.goto(url, wait_until="networkidle")
            await asyncio.sleep(5)

            # 페이지 제목 추출
            title = await page.title()
            print(f"페이지 제목: {title}")

            # 상품명 추출 (다양한 셀렉터 시도)
            product_info = await page.evaluate("""
                () => {
                    const info = {};

                    // 상품명 추출 시도
                    const titleSelectors = [
                        'h1', 'h2', 'h3',
                        '.product-title', '.prod-title', '.title',
                        '.product-name', '.prod-name',
                        '.insurance-title', '.ins-title',
                        '[class*="title"]', '[class*="name"]'
                    ];

                    for (let selector of titleSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (let el of elements) {
                            const text = el.textContent?.trim();
                            if (text && text.length > 5 && text.length < 100) {
                                if (text.includes('보험') || text.includes('건강') || text.includes('KB')) {
                                    info.productName = text;
                                    info.selector = selector;
                                    break;
                                }
                            }
                        }
                        if (info.productName) break;
                    }

                    // 메타 정보 추출
                    const metaDescription = document.querySelector('meta[name="description"]');
                    if (metaDescription) {
                        info.metaDescription = metaDescription.content;
                    }

                    // 페이지 내 텍스트에서 상품 정보 추출
                    const allText = document.body.textContent || '';

                    // e-건강보험 관련 텍스트 찾기
                    const healthInsPatterns = [
                        /KB.*?e[-\s]*건강보험.*?무배당/gi,
                        /딱좋은.*?e[-\s]*건강보험.*?무배당/gi,
                        /e[-\s]*건강보험.*?갱신형/gi,
                        /e[-\s]*건강보험.*?일반심사형/gi,
                        /e[-\s]*건강보험.*?해약환급금.*?미지급형/gi
                    ];

                    info.foundPatterns = [];
                    for (let pattern of healthInsPatterns) {
                        const matches = allText.match(pattern);
                        if (matches) {
                            info.foundPatterns.push(...matches);
                        }
                    }

                    // 상품 코드 추출 시도
                    const codePatterns = [
                        /productCode["\s]*[:=]["\s]*([A-Z0-9]+)/gi,
                        /prodCd["\s]*[:=]["\s]*["']?([A-Z0-9]+)/gi,
                        /code["\s]*[:=]["\s]*["']?([A-Z0-9]+)/gi
                    ];

                    info.foundCodes = [];
                    const scripts = document.querySelectorAll('script');
                    for (let script of scripts) {
                        const scriptText = script.textContent || '';
                        for (let pattern of codePatterns) {
                            const matches = scriptText.match(pattern);
                            if (matches) {
                                info.foundCodes.push(...matches);
                            }
                        }
                    }

                    return info;
                }
            """)

            print(f"\n=== 상품 정보 분석 결과 ===")
            print(f"추출된 상품명: {product_info.get('productName', 'N/A')}")
            print(f"사용된 셀렉터: {product_info.get('selector', 'N/A')}")
            print(f"메타 설명: {product_info.get('metaDescription', 'N/A')}")

            if product_info.get('foundPatterns'):
                print(f"\n발견된 e-건강보험 패턴:")
                for pattern in product_info['foundPatterns']:
                    print(f"  - {pattern}")

            if product_info.get('foundCodes'):
                print(f"\n발견된 상품 코드:")
                for code in product_info['foundCodes']:
                    print(f"  - {code}")

            # 추가: 페이지의 모든 텍스트에서 '딱좋은', 'e-건강보험' 관련 내용 검색
            specific_search = await page.evaluate("""
                () => {
                    const fullText = document.body.textContent || '';
                    const results = {};

                    // '딱좋은' 포함 문장
                    const sentences = fullText.split(/[.!?]/).map(s => s.trim());
                    results.exactMatches = [];

                    for (let sentence of sentences) {
                        if (sentence.includes('딱좋은') || sentence.includes('e-건강보험') || sentence.includes('e건강보험')) {
                            results.exactMatches.push(sentence);
                        }
                    }

                    // 상품명 후보 추출 (제목 태그들)
                    results.titleCandidates = [];
                    const headers = document.querySelectorAll('h1, h2, h3, .title, .name, [class*="title"], [class*="name"]');
                    for (let header of headers) {
                        const text = header.textContent?.trim();
                        if (text && text.length > 3 && text.length < 150) {
                            results.titleCandidates.push(text);
                        }
                    }

                    return results;
                }
            """)

            print(f"\n=== 정확한 매치 검색 ===")
            if specific_search.get('exactMatches'):
                print(f"'딱좋은' 또는 'e-건강보험' 포함 문장:")
                for match in specific_search['exactMatches'][:10]:  # 최대 10개만 표시
                    print(f"  - {match[:100]}")

            print(f"\n제목 후보들:")
            if specific_search.get('titleCandidates'):
                for candidate in specific_search['titleCandidates'][:15]:  # 최대 15개만 표시
                    print(f"  - {candidate}")

            print(f"\n브라우저를 열어둡니다. 직접 확인 후 Enter를 눌러주세요...")
            input()

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(check_product_name())