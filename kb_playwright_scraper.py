import asyncio
from playwright.async_api import async_playwright
import json
import time

async def scrape_kb_insurance_with_playwright():
    url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async with async_playwright() as p:
        # 브라우저 실행
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        try:
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )

            page = await context.new_page()

            print("페이지 로딩 중...")
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # 페이지가 완전히 로드될 때까지 대기
            await page.wait_for_timeout(3000)

            # 페이지 제목 가져오기
            title = await page.title()
            print(f"페이지 제목: {title}")

            # 상품명 추출 시도
            product_name = ""
            product_selectors = [
                'h1', 'h2', 'h3',
                '.product-title', '.title', '.product-name',
                '.productName', '.product_name',
                '[class*="title"]', '[class*="product"]',
                '[class*="name"]'
            ]

            for selector in product_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text = await element.inner_text()
                        if text and text.strip():
                            product_name = text.strip()
                            print(f"상품명 발견: {product_name}")
                            break
                except:
                    continue

            # 전체 페이지 텍스트 가져오기
            full_text = await page.evaluate('''
                () => {
                    // 스크립트와 스타일 태그 제거
                    const scripts = document.querySelectorAll('script, style');
                    scripts.forEach(el => el.remove());

                    return document.body.innerText;
                }
            ''')

            # 테이블 데이터 추출
            tables_data = await page.evaluate('''
                () => {
                    const tables = document.querySelectorAll('table');
                    return Array.from(tables).map(table => {
                        const rows = table.querySelectorAll('tr');
                        return Array.from(rows).map(row => {
                            const cells = row.querySelectorAll('td, th');
                            return Array.from(cells).map(cell => cell.innerText.trim());
                        }).filter(row => row.length > 0);
                    }).filter(table => table.length > 0);
                }
            ''')

            # 리스트 데이터 추출
            lists_data = await page.evaluate('''
                () => {
                    const lists = document.querySelectorAll('ul, ol');
                    return Array.from(lists).map(list => {
                        const items = list.querySelectorAll('li');
                        return Array.from(items).map(item => item.innerText.trim());
                    }).filter(list => list.length > 0);
                }
            ''')

            # div 요소에서 중요한 정보 추출
            divs_data = await page.evaluate('''
                () => {
                    const divs = document.querySelectorAll('div[class*="content"], div[class*="info"], div[class*="detail"]');
                    return Array.from(divs).map(div => div.innerText.trim()).filter(text => text.length > 10);
                }
            ''')

            # 특정 클래스나 ID로 상품 정보 찾기
            product_info = await page.evaluate('''
                () => {
                    const selectors = [
                        '[class*="product"]',
                        '[class*="insurance"]',
                        '[class*="detail"]',
                        '[class*="info"]',
                        '[id*="product"]',
                        '[id*="detail"]'
                    ];

                    let info = [];
                    selectors.forEach(selector => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach(el => {
                            const text = el.innerText.trim();
                            if (text && text.length > 5) {
                                info.push(text);
                            }
                        });
                    });
                    return info;
                }
            ''')

            # 스크린샷 저장
            await page.screenshot(path='kb_insurance_page.png', full_page=True)

            # 결과 데이터 구성
            scraped_data = {
                'url': url,
                'title': title,
                'product_name': product_name,
                'full_text': full_text,
                'tables': tables_data,
                'lists': lists_data,
                'divs_content': divs_data,
                'product_info': product_info,
                'scraping_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }

            return scraped_data

        except Exception as e:
            print(f"스크래핑 중 오류 발생: {e}")
            return None

        finally:
            await browser.close()

async def main():
    print("KB생명 보험 상품 페이지 스크래핑 시작 (Playwright 사용)...")

    data = await scrape_kb_insurance_with_playwright()

    if data:
        # JSON 파일로 저장
        with open('kb_insurance_playwright.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("스크래핑 완료!")
        print(f"페이지 제목: {data.get('title', '정보 없음')}")
        print(f"상품명: {data.get('product_name', '정보 없음')}")
        print(f"테이블 수: {len(data.get('tables', []))}")
        print(f"리스트 수: {len(data.get('lists', []))}")
        print(f"상품 정보 항목 수: {len(data.get('product_info', []))}")
        print(f"\n결과가 'kb_insurance_playwright.json' 파일에 저장되었습니다.")
        print("스크린샷이 'kb_insurance_page.png'로 저장되었습니다.")

        # 주요 정보 미리보기
        if data.get('product_name'):
            print(f"\n=== {data['product_name']} ===")

        if data.get('tables'):
            print(f"\n테이블 정보 (총 {len(data['tables'])}개):")
            for i, table in enumerate(data['tables'][:3]):  # 처음 3개만 표시
                print(f"\n테이블 {i+1}:")
                for row in table[:5]:  # 각 테이블의 처음 5행만 표시
                    if row:
                        print(f"  {' | '.join(row)}")
                if len(table) > 5:
                    print(f"  ... (총 {len(table)}행)")
    else:
        print("스크래핑에 실패했습니다.")

if __name__ == "__main__":
    asyncio.run(main())