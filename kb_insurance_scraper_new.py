"""
KB생명 보험 상품 스크래퍼 (HTTP + Playwright 하이브리드)
"""

import asyncio
import json
import time
import aiohttp
from pathlib import Path
from bs4 import BeautifulSoup

URL = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

async def scrape_with_http():
    """HTTP 직접 요청으로 스크래핑"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

    print("[*] HTTP 요청으로 KB생명 페이지 접근 중...")

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    html_content = await response.text()
                    print(f"[+] 페이지 로드 성공 (크기: {len(html_content)} bytes)")
                    return html_content
                else:
                    print(f"[!] HTTP 요청 실패: {response.status}")
                    return None
        except Exception as e:
            print(f"[!] HTTP 요청 오류: {e}")
            return None

def parse_html_content(html_content):
    """BeautifulSoup으로 HTML 파싱하여 정보 추출"""
    print("[*] HTML 파싱 중...")

    soup = BeautifulSoup(html_content, 'html.parser')

    # 페이지 제목 추출
    title = soup.title.get_text() if soup.title else "제목 없음"

    # 상품명 추출 시도
    product_name = ""
    title_selectors = ['h1', 'h2', 'h3', '.product-title', '.title', '.product-name']

    for selector in title_selectors:
        elements = soup.select(selector)
        for element in elements:
            text = element.get_text(strip=True)
            if text and len(text) > 3:
                product_name = text
                break
        if product_name:
            break

    # 메타 태그에서 상품명 찾기
    if not product_name:
        og_title = soup.find('meta', property='og:title')
        if og_title:
            product_name = og_title.get('content', '')

    # 전체 텍스트 추출 (스크립트, 스타일 제거)
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    full_text = soup.get_text(separator='\n', strip=True)

    # 테이블 데이터 추출
    tables_data = []
    tables = soup.find_all('table')
    for table in tables:
        table_data = []
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if any(cell for cell in row_data):  # 빈 행이 아닌 경우만
                table_data.append(row_data)
        if table_data:
            tables_data.append(table_data)

    # 리스트 데이터 추출
    lists_data = []
    lists = soup.find_all(['ul', 'ol'])
    for ul in lists:
        list_items = [li.get_text(strip=True) for li in ul.find_all('li')]
        if list_items:
            lists_data.append(list_items)

    # 보험 관련 특정 정보 추출
    insurance_selectors = [
        '[class*="insurance"]', '[class*="product"]', '[class*="premium"]',
        '[class*="coverage"]', '[class*="benefit"]', '[class*="condition"]',
        '.info-box', '.detail-info', '.product-info'
    ]

    insurance_info = []
    for selector in insurance_selectors:
        elements = soup.select(selector)
        for element in elements:
            text = element.get_text(strip=True)
            if text and 10 < len(text) < 1000:
                insurance_info.append(text)

    # 중복 제거
    insurance_info = list(set(insurance_info))

    # 링크 정보 추출
    links = []
    for link in soup.find_all('a', href=True):
        link_text = link.get_text(strip=True)
        if link_text:
            links.append({
                'text': link_text,
                'href': link.get('href', '')
            })

    # 이미지 정보 추출
    images = []
    for img in soup.find_all('img', src=True):
        images.append({
            'src': img.get('src', ''),
            'alt': img.get('alt', ''),
            'title': img.get('title', '')
        })

    return {
        'url': URL,
        'title': title,
        'product_name': product_name,
        'full_text': full_text,
        'tables': tables_data,
        'lists': lists_data,
        'insurance_info': insurance_info,
        'links': links,
        'images': images,
        'scraping_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }

async def main():
    print("KB생명 보험 상품 스크래핑 시작...")

    # HTTP 요청으로 페이지 가져오기
    html_content = await scrape_with_http()

    if html_content:
        # HTML 파싱하여 데이터 추출
        data = parse_html_content(html_content)

        # JSON 파일로 저장
        output_file = 'kb_insurance_http_scraped.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[+] 데이터 저장: {output_file}")
        print(f"[+] 페이지 제목: {data.get('title', '정보 없음')}")
        print(f"[+] 상품명: {data.get('product_name', '정보 없음')}")
        print(f"[+] 테이블 수: {len(data.get('tables', []))}")
        print(f"[+] 리스트 수: {len(data.get('lists', []))}")
        print(f"[+] 보험 정보 항목 수: {len(data.get('insurance_info', []))}")
        print(f"[+] 링크 수: {len(data.get('links', []))}")

        # 주요 정보 미리보기
        if data.get('product_name'):
            print(f"\n=== {data['product_name']} ===")

        if data.get('insurance_info'):
            print(f"\n보험 관련 정보 (처음 3개):")
            for i, info in enumerate(data['insurance_info'][:3]):
                print(f"{i+1}. {info[:100]}...")

        if data.get('tables'):
            print(f"\n테이블 정보 (처음 2개):")
            for i, table in enumerate(data['tables'][:2]):
                print(f"\n테이블 {i+1}:")
                for row in table[:3]:
                    if row:
                        print(f"  {' | '.join(row)}")
                if len(table) > 3:
                    print(f"  ... (총 {len(table)}행)")

        print(f"\n[+] 스크래핑 완료! 결과는 {output_file}에 저장되었습니다.")
    else:
        print("[!] 페이지 로드에 실패했습니다.")

if __name__ == "__main__":
    asyncio.run(main())
