import requests
from bs4 import BeautifulSoup
import json
import time

def scrape_kb_insurance_product():
    url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        product_data = {}

        # 상품명 추출
        title_selectors = [
            'h1', 'h2', 'h3',
            '.product-title', '.title', '.product-name',
            '[class*="title"]', '[class*="product"]'
        ]

        for selector in title_selectors:
            title_element = soup.select_one(selector)
            if title_element and title_element.get_text(strip=True):
                product_data['product_name'] = title_element.get_text(strip=True)
                break

        # 메타 정보 추출
        meta_title = soup.find('meta', property='og:title')
        if meta_title and not product_data.get('product_name'):
            product_data['product_name'] = meta_title.get('content', '')

        # 모든 텍스트 내용 추출
        all_text = soup.get_text(separator='\n', strip=True)
        product_data['full_content'] = all_text

        # 테이블 데이터 추출
        tables = soup.find_all('table')
        table_data = []
        for table in tables:
            rows = []
            for row in table.find_all('tr'):
                cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)
            if rows:
                table_data.append(rows)

        product_data['tables'] = table_data

        # 리스트 항목 추출
        lists = soup.find_all(['ul', 'ol'])
        list_data = []
        for ul in lists:
            items = [li.get_text(strip=True) for li in ul.find_all('li')]
            if items:
                list_data.append(items)

        product_data['lists'] = list_data

        # 링크 추출
        links = []
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            if link_text:
                links.append({
                    'text': link_text,
                    'href': link['href']
                })

        product_data['links'] = links

        return product_data

    except requests.RequestException as e:
        print(f"요청 오류: {e}")
        return None
    except Exception as e:
        print(f"스크래핑 오류: {e}")
        return None

if __name__ == "__main__":
    print("KB생명 보험 상품 페이지 스크래핑 시작...")

    data = scrape_kb_insurance_product()

    if data:
        # JSON 파일로 저장
        with open('kb_insurance_product.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print("스크래핑 완료!")
        print(f"상품명: {data.get('product_name', '정보 없음')}")
        print(f"테이블 수: {len(data.get('tables', []))}")
        print(f"리스트 수: {len(data.get('lists', []))}")
        print(f"링크 수: {len(data.get('links', []))}")
        print("\n결과가 'kb_insurance_product.json' 파일에 저장되었습니다.")

        # 주요 정보 출력
        if data.get('product_name'):
            print(f"\n=== {data['product_name']} ===")

        if data.get('tables'):
            print(f"\n테이블 정보 ({len(data['tables'])}개):")
            for i, table in enumerate(data['tables'][:3]):  # 처음 3개 테이블만 표시
                print(f"테이블 {i+1}:")
                for row in table[:5]:  # 각 테이블의 처음 5행만 표시
                    print(f"  {' | '.join(row)}")
                if len(table) > 5:
                    print(f"  ... (총 {len(table)}행)")
                print()
    else:
        print("스크래핑에 실패했습니다.")