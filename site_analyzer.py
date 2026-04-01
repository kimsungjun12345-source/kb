"""
웹사이트 구조 및 기능 분석기
https://ainos-creaiit-trackb.vercel.app/ 분석
"""

import json
from playwright.sync_api import sync_playwright
from datetime import datetime
from pathlib import Path

def analyze_website():
    """웹사이트 분석 및 스크린샷 저장"""

    url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        try:
            print(f"웹사이트 분석 중: {url}")
            page.goto(url, wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(3000)

            # 페이지 정보 수집
            title = page.title()
            print(f"페이지 제목: {title}")

            # 스크린샷 저장
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = f"website_analysis_{timestamp}.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"스크린샷 저장: {screenshot_path}")

            # HTML 저장
            html_path = f"website_content_{timestamp}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page.content())
            print(f"HTML 저장: {html_path}")

            # 페이지 텍스트 내용 추출
            body_text = page.locator('body').inner_text()

            # 주요 링크들 추출
            links = []
            link_elements = page.locator('a').all()
            for link in link_elements[:20]:  # 처음 20개만
                try:
                    href = link.get_attribute('href')
                    text = link.inner_text().strip()
                    if href and text:
                        links.append({'text': text, 'href': href})
                except:
                    continue

            # 버튼들 추출
            buttons = []
            button_elements = page.locator('button').all()
            for btn in button_elements[:10]:  # 처음 10개만
                try:
                    text = btn.inner_text().strip()
                    if text:
                        buttons.append(text)
                except:
                    continue

            # 주요 섹션/컴포넌트 찾기
            sections = []
            section_selectors = ['header', 'nav', 'main', 'section', 'aside', 'footer']
            for selector in section_selectors:
                elements = page.locator(selector).all()
                for element in elements:
                    try:
                        text = element.inner_text()[:200]  # 처음 200자만
                        if text.strip():
                            sections.append({'tag': selector, 'content': text.strip()})
                    except:
                        continue

            # 분석 결과
            analysis = {
                'url': url,
                'title': title,
                'analyzed_at': datetime.now().isoformat(),
                'links': links,
                'buttons': buttons,
                'sections': sections,
                'body_text_preview': body_text[:1000] if len(body_text) > 1000 else body_text
            }

            # JSON으로 저장
            analysis_path = f"website_analysis_{timestamp}.json"
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, ensure_ascii=False, indent=2)
            print(f"분석 결과 저장: {analysis_path}")

            # 콘솔 출력
            print("\n" + "="*60)
            print("웹사이트 분석 결과")
            print("="*60)
            print(f"제목: {title}")
            print(f"링크 개수: {len(links)}")
            print(f"버튼 개수: {len(buttons)}")
            print(f"섹션 개수: {len(sections)}")

            print(f"\n주요 링크:")
            for i, link in enumerate(links[:5], 1):
                print(f"  {i}. {link['text']} -> {link['href']}")

            print(f"\n주요 버튼:")
            for i, btn in enumerate(buttons[:5], 1):
                print(f"  {i}. {btn}")

            print(f"\n페이지 내용 미리보기:")
            print(body_text[:500] + "..." if len(body_text) > 500 else body_text)

        except Exception as e:
            print(f"분석 중 오류: {e}")

        finally:
            browser.close()

if __name__ == "__main__":
    analyze_website()