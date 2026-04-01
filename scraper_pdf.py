"""
KB 딱좋은 e-건강보험 PDF 자동 다운로드 스크래퍼
상품설명서, 약관, 상품요약서를 ./downloads/ 폴더에 자동 다운로드
"""

import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

class KBHealthInsurancePDFScraper:
    """KB 딱좋은 e-건강보험 PDF 다운로드 스크래퍼"""

    def __init__(self):
        self.target_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.download_dir = Path("./downloads")
        self.download_dir.mkdir(exist_ok=True)

        # PDF 다운로드 대상 파일명 패턴
        self.pdf_patterns = [
            "상품설명서", "약관", "상품요약서", "설명서", "약관서",
            "요약서", "PDF", "다운로드"
        ]

        print(f"다운로드 폴더: {self.download_dir.absolute()}")

    def setup_browser(self):
        """브라우저 설정"""
        self.playwright = sync_playwright().start()

        # 브라우저 실행 설정
        self.browser = self.playwright.chromium.launch(
            headless=False,  # 브라우저 창 보이게
            slow_mo=300,     # 각 동작 사이 300ms 대기
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security'
            ]
        )

        # 컨텍스트 설정 (다운로드 허용)
        self.context = self.browser.new_context(
            accept_downloads=True
        )

        self.page = self.context.new_page()
        print("브라우저 설정 완료")

    def navigate_to_product_page(self):
        """KB 딱좋은 e-건강보험 상품 페이지로 이동"""
        print(f"상품 페이지 이동 중: {self.target_url}")

        try:
            self.page.goto(self.target_url, wait_until='networkidle', timeout=30000)
            self.page.wait_for_timeout(3000)  # 페이지 완전 로딩 대기

            # 페이지 제목 확인
            title = self.page.title()
            print(f"페이지 로딩 완료: {title}")

            return True

        except Exception as e:
            print(f"페이지 이동 실패: {e}")
            return False

    def find_pdf_download_links(self):
        """PDF 다운로드 링크 찾기"""
        print("\nPDF 다운로드 링크 탐색 중...")

        download_links = []

        # 다양한 PDF 링크 패턴 시도
        pdf_selectors = [
            'a[href*=".pdf"]',
            'a[href*="pdf"]',
            'button:has-text("다운로드")',
            'a:has-text("다운로드")',
            'button:has-text("PDF")',
            'a:has-text("PDF")',
            'button:has-text("상품설명서")',
            'a:has-text("상품설명서")',
            'button:has-text("약관")',
            'a:has-text("약관")',
            'button:has-text("요약서")',
            'a:has-text("요약서")',
            '[class*="download"]',
            '[class*="pdf"]',
            '[onclick*="pdf"]',
            '[onclick*="download"]'
        ]

        for selector in pdf_selectors:
            try:
                elements = self.page.query_selector_all(selector)
                for element in elements:
                    try:
                        # 요소 텍스트 및 속성 확인
                        text = element.inner_text().strip()
                        href = element.get_attribute('href') or ''
                        onclick = element.get_attribute('onclick') or ''

                        # PDF 관련 요소 판별
                        is_pdf_link = (
                            (href and ('.pdf' in href.lower() or 'download' in href.lower())) or
                            (onclick and ('.pdf' in onclick.lower() or 'download' in onclick.lower())) or
                            any(pattern in text for pattern in self.pdf_patterns)
                        )

                        if is_pdf_link and element.is_visible():
                            download_links.append({
                                'element': element,
                                'text': text,
                                'href': href,
                                'onclick': onclick,
                                'selector': selector
                            })
                            print(f"PDF 링크 발견: {text} ({selector})")

                    except Exception as e:
                        continue

            except Exception as e:
                continue

        if not download_links:
            print("PDF 다운로드 링크를 찾을 수 없습니다. HTML 구조를 확인합니다...")
            self.debug_page_content()

        return download_links

    def debug_page_content(self):
        """페이지 HTML 구조 디버깅"""
        print("\n페이지 HTML 구조 분석:")

        try:
            # 페이지 전체 텍스트에서 PDF 관련 키워드 찾기
            page_text = self.page.content()

            # PDF 관련 키워드 검색
            pdf_keywords = ['pdf', 'PDF', '다운로드', '상품설명서', '약관', '요약서']
            found_keywords = []

            for keyword in pdf_keywords:
                if keyword in page_text:
                    found_keywords.append(keyword)

            if found_keywords:
                print(f"페이지에서 발견된 PDF 관련 키워드: {', '.join(found_keywords)}")
            else:
                print("PDF 관련 키워드를 찾을 수 없습니다.")

            # 다운로드 관련 버튼이나 링크 구조 출력
            download_elements = self.page.query_selector_all('button, a, span, div')
            pdf_related = []

            for element in download_elements[:50]:  # 처음 50개만 확인
                try:
                    text = element.inner_text().strip()
                    if any(keyword in text for keyword in pdf_keywords) and text:
                        pdf_related.append(text)
                except:
                    continue

            if pdf_related:
                print("PDF 관련 요소 텍스트:")
                for i, text in enumerate(pdf_related[:10], 1):
                    print(f"  {i}. {text}")

        except Exception as e:
            print(f"HTML 구조 분석 실패: {e}")

    def download_pdfs(self, download_links):
        """PDF 파일들 다운로드"""
        print(f"\n{len(download_links)}개 PDF 다운로드 시작...")

        downloaded_files = []

        for i, link_info in enumerate(download_links, 1):
            try:
                element = link_info['element']
                text = link_info['text']

                print(f"[{i}/{len(download_links)}] 다운로드 중: {text}")

                # 다운로드 시작 전 기존 파일 목록 확인
                before_files = set(os.listdir(self.download_dir))

                # 다운로드 이벤트 대기 설정
                with self.page.expect_download(timeout=30000) as download_info:
                    # 요소 클릭
                    element.click()

                # 다운로드 완료 대기
                download = download_info.value

                # 파일명 생성 (원본 파일명 또는 텍스트 기반)
                original_filename = download.suggested_filename
                if not original_filename or not original_filename.endswith('.pdf'):
                    safe_text = "".join(c for c in text if c.isalnum() or c in (' ', '-', '_')).strip()
                    original_filename = f"{safe_text}.pdf"

                # 파일 저장
                file_path = self.download_dir / original_filename
                download.save_as(file_path)

                downloaded_files.append(str(file_path))
                print(f"다운로드 완료: {original_filename}")

                # 다운로드 간격
                self.page.wait_for_timeout(2000)

            except Exception as e:
                print(f"다운로드 실패: {text} - {e}")
                continue

        return downloaded_files

    def alternative_download_method(self):
        """대안 다운로드 방법 - 직접 PDF URL 탐색"""
        print("\n대안 방법으로 PDF 찾기...")

        try:
            # 페이지의 모든 네트워크 요청에서 PDF URL 찾기
            # 또는 페이지 소스에서 PDF URL 패턴 검색

            page_content = self.page.content()

            # PDF URL 패턴 찾기
            import re
            pdf_url_patterns = [
                r'href=["\'](.*?\.pdf[^"\']*)["\']',
                r'url\s*[:=]\s*["\'](.*?\.pdf[^"\']*)["\']',
                r'(https?://[^\s"\'<>]*\.pdf[^\s"\'<>]*)'
            ]

            found_urls = []
            for pattern in pdf_url_patterns:
                matches = re.findall(pattern, page_content, re.IGNORECASE)
                found_urls.extend(matches)

            if found_urls:
                print(f"발견된 PDF URL: {len(found_urls)}개")
                for url in found_urls[:5]:  # 처음 5개만 출력
                    print(f"  - {url}")
                return found_urls
            else:
                print("PDF URL을 찾을 수 없습니다.")
                return []

        except Exception as e:
            print(f"대안 방법 실패: {e}")
            return []

    def run_scraper(self):
        """메인 스크래핑 실행"""
        print("KB 딱좋은 e-건강보험 PDF 다운로드 스크래퍼 시작")
        print("="*60)

        try:
            # 1. 브라우저 설정
            self.setup_browser()

            # 2. 상품 페이지 이동
            if not self.navigate_to_product_page():
                return

            # 3. PDF 다운로드 링크 찾기
            download_links = self.find_pdf_download_links()

            if download_links:
                # 4. PDF 다운로드
                downloaded_files = self.download_pdfs(download_links)

                # 5. 결과 출력
                print("\n" + "="*60)
                print("PDF 다운로드 결과")
                print("="*60)

                if downloaded_files:
                    print(f"성공적으로 다운로드된 파일: {len(downloaded_files)}개")
                    for i, file_path in enumerate(downloaded_files, 1):
                        file_size = os.path.getsize(file_path) / 1024  # KB 단위
                        print(f"  {i}. {Path(file_path).name} ({file_size:.1f} KB)")
                else:
                    print("다운로드된 파일이 없습니다.")
            else:
                # 대안 방법 시도
                alternative_urls = self.alternative_download_method()
                if alternative_urls:
                    print("대안 방법으로 PDF URL을 발견했지만, 직접 다운로드는 별도 구현이 필요합니다.")
                    for url in alternative_urls[:3]:
                        print(f"  - {url}")

        except Exception as e:
            print(f"스크래퍼 실행 중 오류: {e}")

        finally:
            # 브라우저 종료
            try:
                if hasattr(self, 'context'):
                    self.context.close()
                if hasattr(self, 'browser'):
                    self.browser.close()
                if hasattr(self, 'playwright'):
                    self.playwright.stop()
                print("\n브라우저 종료 완료")
            except:
                pass

def main():
    """메인 함수"""
    scraper = KBHealthInsurancePDFScraper()
    scraper.run_scraper()

if __name__ == "__main__":
    main()