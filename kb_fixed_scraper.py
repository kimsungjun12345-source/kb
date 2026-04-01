import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBFixedScraper:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.data = []

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security"
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        return browser, context

    def generate_birthdate(self, age):
        current_year = datetime.now().year
        birth_year = current_year - age
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return f"{birth_year}{month:02d}{day:02d}"

    async def wait_random(self, min_seconds=2, max_seconds=4):
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def scrape_single_case(self, age, gender):
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info(f"데이터 수집 시작: {age}세 {gender}")

                # 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle")
                await self.wait_random(3, 5)

                # 생년월일 입력
                birthdate = self.generate_birthdate(age)
                logger.info(f"생년월일 입력: {birthdate}")

                await page.fill("#birthday", birthdate)
                await self.wait_random(1, 2)

                # 성별 선택 (JavaScript로 직접 처리)
                gender_value = "M" if gender == "남성" else "F"
                logger.info(f"성별 선택 시도: {gender} ({gender_value})")

                # JavaScript로 라디오 버튼 선택
                await page.evaluate(f"""
                    const radios = document.querySelectorAll('input[name="genderCode"]');
                    for (let radio of radios) {{
                        if (radio.value === '{gender_value}') {{
                            radio.checked = true;
                            radio.click();
                            // 이벤트 발생시키기
                            radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            break;
                        }}
                    }}
                """)

                logger.info("성별 선택 완료")
                await self.wait_random(2, 3)

                # 설계견적하기 버튼 찾고 클릭
                logger.info("설계견적하기 버튼 찾는 중...")

                # JavaScript로 설계견적 버튼 찾아서 클릭
                button_clicked = await page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (let button of buttons) {
                            const text = button.textContent || button.innerText;
                            if (text.includes('설계') || text.includes('견적') || text.includes('계산')) {
                                console.log('Found button:', text);
                                button.click();
                                return text;
                            }
                        }
                        return null;
                    }
                """)

                if button_clicked:
                    logger.info(f"버튼 클릭 성공: {button_clicked}")
                else:
                    logger.error("설계견적 버튼을 찾을 수 없습니다")
                    return None

                # 페이지 로딩 대기
                await self.wait_random(5, 8)

                # 결과 데이터 수집
                result_data = await self.collect_data_from_page(page, age, gender, birthdate)

                # 스크린샷 저장
                await page.screenshot(path=f"kb_final_result_{age}_{gender}.png", full_page=True)

                return result_data

            except Exception as e:
                logger.error(f"스크래핑 중 오류: {str(e)}")
                return None
            finally:
                await browser.close()

    async def collect_data_from_page(self, page, age, gender, birthdate):
        """페이지에서 모든 데이터 수집"""
        try:
            result_data = {
                "age": age,
                "gender": gender,
                "birthdate": birthdate,
                "scraped_at": datetime.now().isoformat(),
                "page_url": page.url,
                "plans": [],
                "special_clauses": [],
                "all_text_data": []
            }

            logger.info("페이지 데이터 수집 시작")

            # 현재 페이지 HTML 저장
            page_content = await page.content()
            with open(f"kb_final_page_{age}_{gender}.html", "w", encoding="utf-8") as f:
                f.write(page_content)

            # 모든 보이는 텍스트 수집
            visible_elements = await page.query_selector_all("*")
            text_data = []

            for element in visible_elements:
                try:
                    is_visible = await element.is_visible()
                    if is_visible:
                        text_content = await element.text_content()
                        if text_content and text_content.strip():
                            # 보험료, 금액, 플랜 관련 텍스트 우선 수집
                            text = text_content.strip()
                            if any(keyword in text for keyword in ['원', '만원', '플랜', '보험료', '보장', '특약', '급여']):
                                text_data.append({
                                    "text": text[:200],  # 처음 200자만
                                    "tag_name": await element.evaluate("el => el.tagName"),
                                    "class_name": await element.get_attribute("class")
                                })
                except:
                    continue

            result_data["all_text_data"] = text_data[:100]  # 상위 100개만

            # 테이블 데이터 수집
            await self.collect_table_data(page, result_data)

            # 체크박스 데이터 수집
            await self.collect_checkbox_data(page, result_data)

            # 특별히 보험료 관련 데이터 수집
            await self.collect_premium_data(page, result_data)

            logger.info(f"데이터 수집 완료: 텍스트 {len(result_data['all_text_data'])}개, 특약 {len(result_data['special_clauses'])}개")

            return result_data

        except Exception as e:
            logger.error(f"데이터 수집 중 오류: {str(e)}")
            return None

    async def collect_table_data(self, page, result_data):
        """테이블 데이터 수집"""
        try:
            tables = await page.query_selector_all("table")
            table_data = []

            for i, table in enumerate(tables):
                try:
                    rows = await table.query_selector_all("tr")
                    table_content = []

                    for row in rows:
                        cells = await row.query_selector_all("td, th")
                        row_data = []
                        for cell in cells:
                            cell_text = await cell.text_content()
                            if cell_text:
                                row_data.append(cell_text.strip())
                        if row_data:
                            table_content.append(row_data)

                    if table_content:
                        table_data.append({
                            "table_index": i,
                            "content": table_content[:10]  # 처음 10행만
                        })
                except:
                    continue

            result_data["tables"] = table_data
            logger.info(f"테이블 데이터 수집: {len(table_data)}개")

        except Exception as e:
            logger.error(f"테이블 데이터 수집 중 오류: {str(e)}")

    async def collect_checkbox_data(self, page, result_data):
        """체크박스 데이터 수집"""
        try:
            checkboxes = await page.query_selector_all("input[type='checkbox']")
            checkbox_data = []

            for i, checkbox in enumerate(checkboxes):
                try:
                    is_checked = await checkbox.is_checked()
                    checkbox_id = await checkbox.get_attribute("id")
                    checkbox_name = await checkbox.get_attribute("name")

                    # 체크박스와 연관된 레이블 텍스트 찾기
                    label_text = ""
                    parent = await checkbox.evaluate("el => el.closest('label, tr, div')")
                    if parent:
                        parent_text = await parent.text_content()
                        if parent_text:
                            label_text = parent_text.strip()[:100]

                    checkbox_info = {
                        "index": i,
                        "id": checkbox_id,
                        "name": checkbox_name,
                        "is_checked": is_checked,
                        "label": label_text
                    }

                    checkbox_data.append(checkbox_info)

                except:
                    continue

            result_data["special_clauses"] = checkbox_data
            logger.info(f"체크박스 데이터 수집: {len(checkbox_data)}개")

        except Exception as e:
            logger.error(f"체크박스 데이터 수집 중 오류: {str(e)}")

    async def collect_premium_data(self, page, result_data):
        """보험료 관련 데이터 특별 수집"""
        try:
            # 숫자와 '원'이 포함된 모든 요소 찾기
            premium_elements = await page.evaluate("""
                () => {
                    return Array.from(document.querySelectorAll('*')).filter(el => {
                        const text = el.textContent;
                        return text && (text.includes('원') || text.includes('만원') || /\\d{1,3}(,\\d{3})*/.test(text));
                    }).slice(0, 50).map(el => ({
                        text: el.textContent.trim().substring(0, 100),
                        tagName: el.tagName,
                        className: el.className
                    }));
                }
            """)

            result_data["premium_data"] = premium_elements
            logger.info(f"보험료 관련 데이터 수집: {len(premium_elements)}개")

        except Exception as e:
            logger.error(f"보험료 데이터 수집 중 오류: {str(e)}")

    async def test_and_save(self, age=30, gender="남성"):
        """테스트 실행 및 결과 저장"""
        logger.info(f"KB 보험 스크래핑 테스트: {age}세 {gender}")

        result = await self.scrape_single_case(age, gender)

        if result:
            # JSON 파일로 저장
            filename = f"kb_complete_result_{age}_{gender}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

            logger.info(f"결과 저장 완료: {filename}")

            # 결과 요약 출력
            print("\n" + "="*50)
            print(f"KB생명 보험 데이터 수집 결과")
            print("="*50)
            print(f"나이: {result['age']}세")
            print(f"성별: {result['gender']}")
            print(f"생년월일: {result['birthdate']}")
            print(f"페이지 URL: {result['page_url']}")
            print(f"수집 시간: {result['scraped_at']}")
            print("-"*50)

            if 'tables' in result and result['tables']:
                print(f"테이블 데이터: {len(result['tables'])}개")

            if result['special_clauses']:
                print(f"특약/체크박스: {len(result['special_clauses'])}개")
                print("\n주요 특약:")
                for i, clause in enumerate(result['special_clauses'][:5]):
                    status = "선택됨" if clause.get('is_checked') else "선택안됨"
                    print(f"  {i+1}. {clause.get('label', 'N/A')[:50]} ({status})")

            if 'premium_data' in result and result['premium_data']:
                print(f"\n보험료 관련 데이터: {len(result['premium_data'])}개")
                print("주요 보험료 정보:")
                for i, premium in enumerate(result['premium_data'][:5]):
                    print(f"  {i+1}. {premium.get('text', 'N/A')[:80]}")

            print("="*50)

        else:
            logger.error("스크래핑 실패")

        return result

async def main():
    scraper = KBFixedScraper()
    await scraper.test_and_save(30, "남성")

if __name__ == "__main__":
    asyncio.run(main())