"""
KB생명 보험 상품 PDF 자동 다운로드
상품설명서, 약관 등 PDF 문서를 자동으로 다운로드하는 Playwright 기반 스크래퍼
"""

import asyncio
import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Download

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_downloader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KBPDFDownloader:
    """KB생명 PDF 다운로드 자동화 클래스"""

    def __init__(self, download_dir: str = "downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)

        # KB생명 보험 상품 목록
        self.products = {
            "ON_PD_KC_01": {
                "name": "KB 착한암보험 무배당",
                "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5"
            },
            "ON_PD_YG_01": {
                "name": "KB 딱좋은 e-건강보험 무배당",
                "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
            },
            "ON_PD_YT_01": {
                "name": "KB 딱좋은 e-건강보험 간편형",
                "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YT_01&productType=5"
            },
            "ON_PD_SR_01": {
                "name": "KB 착한정기보험II 무배당",
                "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_SR_01&productType=5"
            },
            "ON_PD_NP_01": {
                "name": "KB 하이파이브평생연금보험 무배당",
                "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_NP_01&productType=5"
            }
        }

        # PDF 다운로드 대상 문서 유형
        self.pdf_selectors = {
            "상품설명서": [
                'a[href*="product"][href*="guide"]',
                'a[href*="상품설명서"]',
                'a[onclick*="상품설명서"]',
                'a[title*="상품설명서"]',
                '.product-guide a',
                '.document-list a[href*=".pdf"]'
            ],
            "약관": [
                'a[href*="terms"]',
                'a[href*="약관"]',
                'a[onclick*="약관"]',
                'a[title*="약관"]',
                '.terms-link a',
                '.contract-terms a'
            ],
            "상품요약서": [
                'a[href*="summary"]',
                'a[href*="요약서"]',
                'a[onclick*="요약서"]',
                'a[title*="요약서"]',
                '.product-summary a'
            ]
        }

    async def setup_browser(self) -> tuple[Browser, BrowserContext]:
        """브라우저 설정 (다운로드 허용)"""
        playwright = await async_playwright().start()

        browser = await playwright.chromium.launch(
            headless=False,  # 브라우저 창 표시
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security'
            ]
        )

        # 다운로드 허용하는 컨텍스트 생성
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            accept_downloads=True  # 다운로드 허용
        )

        return browser, context

    async def handle_popups(self, page: Page):
        """팝업 처리"""
        popup_selectors = [
            '[class*="popup"] [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '.popup-close', '.modal-close', '#popup_close',
            'button[onclick*="close"]', '.layer-close'
        ]

        for selector in popup_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    await page.wait_for_timeout(1000)
                    logger.info(f"팝업 닫기: {selector}")
                    break
            except:
                continue

    async def wait_for_download(self, download: Download, expected_filename: str = None) -> Optional[str]:
        """다운로드 완료 대기 및 파일명 변경"""
        try:
            # 다운로드 완료 대기
            downloaded_path = await download.path()
            if not downloaded_path:
                logger.error("다운로드 경로를 가져올 수 없습니다")
                return None

            # 원본 파일명
            suggested_filename = download.suggested_filename
            logger.info(f"다운로드 완료: {suggested_filename}")

            # 목적지 파일명 생성
            if expected_filename:
                dest_filename = f"{expected_filename}.pdf"
            else:
                # 타임스탬프 추가
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                dest_filename = f"{suggested_filename.replace('.pdf', '')}_{timestamp}.pdf"

            dest_path = self.download_dir / dest_filename

            # 파일 이동
            import shutil
            shutil.move(downloaded_path, dest_path)

            logger.info(f"파일 저장: {dest_path}")
            return str(dest_path)

        except Exception as e:
            logger.error(f"다운로드 처리 중 오류: {e}")
            return None

    async def find_and_download_pdfs(self, page: Page, product_code: str, product_name: str) -> List[str]:
        """PDF 문서 찾기 및 다운로드"""
        downloaded_files = []

        logger.info(f"PDF 문서 검색 시작: {product_name}")

        for doc_type, selectors in self.pdf_selectors.items():
            logger.info(f"  {doc_type} 검색 중...")

            for selector in selectors:
                try:
                    # PDF 링크 찾기
                    elements = await page.query_selector_all(selector)

                    for i, element in enumerate(elements):
                        try:
                            # 링크 텍스트 확인
                            link_text = await element.inner_text()
                            href = await element.get_attribute('href')
                            onclick = await element.get_attribute('onclick')

                            logger.debug(f"    발견된 링크: {link_text} | href: {href} | onclick: {onclick}")

                            # PDF 관련 링크인지 확인
                            is_pdf_link = (
                                (href and ('.pdf' in href.lower() or doc_type in href)) or
                                (onclick and ('.pdf' in onclick.lower() or doc_type in onclick)) or
                                (link_text and doc_type in link_text)
                            )

                            if is_pdf_link:
                                logger.info(f"    PDF 링크 발견: {link_text}")

                                # 다운로드 시작
                                async with page.expect_download() as download_info:
                                    await element.click()
                                    await page.wait_for_timeout(2000)

                                download = await download_info.value

                                # 파일명 생성
                                safe_product_name = product_name.replace("/", "_").replace("\\", "_")
                                expected_filename = f"{safe_product_name}__{doc_type}_{i+1}"

                                # 다운로드 완료 대기
                                file_path = await self.wait_for_download(download, expected_filename)
                                if file_path:
                                    downloaded_files.append(file_path)
                                    logger.info(f"    ✅ {doc_type} 다운로드 완료: {file_path}")

                                # 다음 다운로드 전 대기
                                await page.wait_for_timeout(3000)

                        except Exception as e:
                            logger.debug(f"    링크 처리 중 오류: {e}")
                            continue

                    if downloaded_files:
                        break  # 해당 문서 유형에서 다운로드 성공했으면 다음 유형으로

                except Exception as e:
                    logger.debug(f"  셀렉터 {selector} 처리 중 오류: {e}")
                    continue

            if not any(doc_type in f for f in downloaded_files):
                logger.warning(f"  ❌ {doc_type} 문서를 찾을 수 없습니다")

        return downloaded_files

    async def download_product_pdfs(self, product_code: str) -> List[str]:
        """특정 상품의 PDF 다운로드"""
        if product_code not in self.products:
            logger.error(f"알 수 없는 상품 코드: {product_code}")
            return []

        product_info = self.products[product_code]
        product_name = product_info["name"]
        product_url = product_info["url"]

        logger.info(f"상품 PDF 다운로드 시작: {product_name}")

        browser = None
        context = None
        downloaded_files = []

        try:
            browser, context = await self.setup_browser()
            page = await context.new_page()

            # 상품 페이지 방문
            logger.info(f"페이지 방문: {product_url}")
            await page.goto(product_url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(5000)

            # 팝업 처리
            await self.handle_popups(page)

            # PDF 문서 검색 및 다운로드
            downloaded_files = await self.find_and_download_pdfs(page, product_code, product_name)

            # 추가 PDF 링크 검색 (더 깊게)
            if not downloaded_files:
                logger.info("기본 검색에서 PDF를 찾지 못했습니다. 추가 검색 중...")
                await self.search_additional_pdfs(page, product_code, product_name)

        except Exception as e:
            logger.error(f"PDF 다운로드 중 오류: {e}")
        finally:
            if context:
                await context.close()
            if browser:
                await browser.close()

        logger.info(f"다운로드 완료: {len(downloaded_files)}개 파일")
        return downloaded_files

    async def search_additional_pdfs(self, page: Page, product_code: str, product_name: str):
        """추가 PDF 검색 (탭, 아코디언 등)"""
        try:
            # 탭 메뉴 클릭해보기
            tab_selectors = [
                '.tab-menu a', '.tab-list a', '.nav-tabs a',
                '[role="tab"]', '.product-tab a'
            ]

            for tab_selector in tab_selectors:
                try:
                    tabs = await page.query_selector_all(tab_selector)
                    for tab in tabs:
                        tab_text = await tab.inner_text()
                        if any(keyword in tab_text for keyword in ['약관', '상품설명서', '요약서', '문서']):
                            logger.info(f"관련 탭 클릭: {tab_text}")
                            await tab.click()
                            await page.wait_for_timeout(3000)

                            # 이 탭에서 PDF 검색
                            pdfs = await self.find_and_download_pdfs(page, product_code, product_name)
                            if pdfs:
                                return pdfs
                except:
                    continue

            # 아코디언이나 더보기 버튼
            expand_selectors = [
                '.accordion-toggle', '.expand-btn', '.more-btn',
                'button[onclick*="expand"]', '[class*="toggle"]'
            ]

            for expand_selector in expand_selectors:
                try:
                    elements = await page.query_selector_all(expand_selector)
                    for element in elements:
                        await element.click()
                        await page.wait_for_timeout(2000)

                        pdfs = await self.find_and_download_pdfs(page, product_code, product_name)
                        if pdfs:
                            return pdfs
                except:
                    continue

        except Exception as e:
            logger.error(f"추가 PDF 검색 중 오류: {e}")

    async def download_all_products(self) -> Dict[str, List[str]]:
        """모든 상품의 PDF 다운로드"""
        all_downloads = {}

        for product_code in self.products.keys():
            try:
                logger.info(f"\n{'='*50}")
                logger.info(f"상품 처리: {self.products[product_code]['name']}")
                logger.info(f"{'='*50}")

                downloaded_files = await self.download_product_pdfs(product_code)
                all_downloads[product_code] = downloaded_files

                # 다음 상품 처리 전 대기
                await asyncio.sleep(3)

            except Exception as e:
                logger.error(f"상품 {product_code} 처리 중 오류: {e}")
                all_downloads[product_code] = []

        return all_downloads

async def main():
    """메인 실행 함수"""
    try:
        print("KB생명 PDF 다운로드를 시작합니다...")

        downloader = KBPDFDownloader()

        # KB 착한암보험 무배당만 먼저 테스트
        product_code = "ON_PD_KC_01"
        print(f"테스트 상품: {downloader.products[product_code]['name']}")

        # 단일 상품 다운로드
        downloaded_files = await downloader.download_product_pdfs(product_code)

        if downloaded_files:
            print(f"\n다운로드 완료: {len(downloaded_files)}개 파일")
            for file_path in downloaded_files:
                print(f"  {file_path}")
        else:
            print("\n다운로드된 파일이 없습니다.")
            print("브라우저 창에서 직접 PDF 링크를 확인해보세요.")

        # 전체 상품 다운로드를 원하는 경우 주석 해제
        # print("\n모든 상품 다운로드 시작...")
        # all_downloads = await downloader.download_all_products()
        #
        # print(f"\n전체 다운로드 결과:")
        # for product_code, files in all_downloads.items():
        #     product_name = downloader.products[product_code]['name']
        #     print(f"  {product_name}: {len(files)}개 파일")

    except KeyboardInterrupt:
        print("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"실행 중 오류: {e}")
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())