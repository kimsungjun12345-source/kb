import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBFullScraper:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.data = []
        self.failed_cases = []

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=True,  # 전체 수집시에는 headless 모드
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-images",  # 이미지 로딩 안함 (속도 향상)
                "--disable-javascript",  # 일부 JS 비활성화
                "--disable-plugins"
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

    async def wait_random(self, min_seconds=3, max_seconds=6):
        """차단 방지를 위한 긴 대기"""
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def scrape_single_case(self, age, gender, retry_count=0):
        """단일 케이스 스크래핑"""
        max_retries = 3

        if retry_count >= max_retries:
            logger.error(f"최대 재시도 횟수 초과: {age}세 {gender}")
            return None

        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info(f"데이터 수집: {age}세 {gender} (시도 {retry_count + 1}/{max_retries})")

                # 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle", timeout=45000)
                await self.wait_random(2, 4)

                # 방화벽 체크
                page_content = await page.content()
                if "firewall" in page_content.lower() or "blocked" in page_content.lower():
                    logger.warning(f"방화벽 차단 감지: {age}세 {gender}")
                    await browser.close()
                    await asyncio.sleep(random.uniform(10, 20))  # 긴 대기
                    return await self.scrape_single_case(age, gender, retry_count + 1)

                # 생년월일 입력
                birthdate = self.generate_birthdate(age)
                await page.fill("#birthday", birthdate)
                await self.wait_random(1, 2)

                # 성별 선택
                gender_value = "M" if gender == "남성" else "F"
                await page.evaluate(f"""
                    const radios = document.querySelectorAll('input[name="genderCode"]');
                    for (let radio of radios) {{
                        if (radio.value === '{gender_value}') {{
                            radio.checked = true;
                            radio.click();
                            radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            break;
                        }}
                    }}
                """)

                await self.wait_random(1, 2)

                # 설계견적하기 버튼 클릭
                button_clicked = await page.evaluate("""
                    () => {
                        const buttons = document.querySelectorAll('button');
                        for (let button of buttons) {
                            const text = button.textContent || button.innerText;
                            if (text.includes('설계') || text.includes('견적')) {
                                button.click();
                                return text;
                            }
                        }
                        return null;
                    }
                """)

                if not button_clicked:
                    logger.warning(f"설계견적 버튼을 찾을 수 없음: {age}세 {gender}")
                    await browser.close()
                    return await self.scrape_single_case(age, gender, retry_count + 1)

                # 결과 페이지 로딩 대기
                await self.wait_random(4, 7)

                # 데이터 수집
                result_data = await self.collect_essential_data(page, age, gender, birthdate)

                return result_data

            except Exception as e:
                logger.error(f"스크래핑 오류: {age}세 {gender} - {str(e)}")
                await browser.close()

                # 네트워크 오류 등의 경우 재시도
                if "timeout" in str(e).lower() or "network" in str(e).lower():
                    await asyncio.sleep(random.uniform(5, 10))
                    return await self.scrape_single_case(age, gender, retry_count + 1)

                return None
            finally:
                await browser.close()

    async def collect_essential_data(self, page, age, gender, birthdate):
        """핵심 데이터만 빠르게 수집"""
        try:
            result_data = {
                "age": age,
                "gender": gender,
                "birthdate": birthdate,
                "scraped_at": datetime.now().isoformat(),
                "page_url": page.url,
                "premium_info": [],
                "plan_info": [],
                "special_clauses": []
            }

            # 보험료 관련 텍스트만 빠르게 추출
            premium_data = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const premiums = [];

                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && (text.includes('원') || text.includes('만원')) &&
                            (/\\d{1,3}(,\\d{3})*/.test(text))) {
                            premiums.push({
                                text: text.trim().substring(0, 150),
                                tagName: el.tagName
                            });
                            if (premiums.length >= 30) break;  // 최대 30개만
                        }
                    }
                    return premiums;
                }
            """)

            result_data["premium_info"] = premium_data

            # 플랜/보장 관련 정보 수집
            plan_data = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    const plans = [];

                    for (let el of elements) {
                        const text = el.textContent;
                        if (text && (text.includes('플랜') || text.includes('보장') ||
                            text.includes('급여') || text.includes('지급'))) {
                            plans.push({
                                text: text.trim().substring(0, 200),
                                tagName: el.tagName
                            });
                            if (plans.length >= 20) break;  // 최대 20개만
                        }
                    }
                    return plans;
                }
            """)

            result_data["plan_info"] = plan_data

            # 체크박스 정보 (특약)
            checkboxes = await page.query_selector_all("input[type='checkbox']")
            for i, checkbox in enumerate(checkboxes[:20]):  # 최대 20개만
                try:
                    is_checked = await checkbox.is_checked()
                    parent_text = await checkbox.evaluate("el => el.closest('tr, div, label')?.textContent?.trim()?.substring(0, 100)")

                    if parent_text:
                        result_data["special_clauses"].append({
                            "index": i,
                            "text": parent_text,
                            "is_checked": is_checked
                        })
                except:
                    continue

            logger.info(f"데이터 수집 완료: {age}세 {gender} - 보험료 {len(premium_data)}개, 플랜 {len(plan_data)}개, 특약 {len(result_data['special_clauses'])}개")

            return result_data

        except Exception as e:
            logger.error(f"데이터 수집 오류: {str(e)}")
            return None

    async def scrape_all_data(self, start_age=20, end_age=64, genders=None):
        """전체 데이터 스크래핑"""
        if genders is None:
            genders = ["남성", "여성"]

        ages = list(range(start_age, end_age + 1))
        total_cases = len(ages) * len(genders)

        logger.info(f"전체 데이터 수집 시작: {start_age}-{end_age}세, {len(genders)}개 성별")
        logger.info(f"총 {total_cases}개 케이스 예상")

        successful_count = 0
        failed_count = 0

        for age in ages:
            for gender in genders:
                case_num = successful_count + failed_count + 1
                logger.info(f"진행률: {case_num}/{total_cases} - {age}세 {gender}")

                try:
                    result = await self.scrape_single_case(age, gender)

                    if result:
                        self.data.append(result)
                        successful_count += 1
                        logger.info(f"✓ 성공: {age}세 {gender}")

                        # 중간 저장 (10건마다)
                        if len(self.data) % 10 == 0:
                            await self.save_intermediate_data()

                    else:
                        self.failed_cases.append({"age": age, "gender": gender})
                        failed_count += 1
                        logger.warning(f"✗ 실패: {age}세 {gender}")

                    # 요청 간 대기 (차단 방지)
                    await self.wait_random(4, 8)

                except Exception as e:
                    logger.error(f"케이스 처리 중 오류: {age}세 {gender} - {str(e)}")
                    self.failed_cases.append({"age": age, "gender": gender, "error": str(e)})
                    failed_count += 1

                # 진행 상황 출력
                if case_num % 20 == 0:
                    logger.info(f"진행 상황: 성공 {successful_count}, 실패 {failed_count}, 전체 {case_num}/{total_cases}")

        # 최종 저장
        await self.save_final_data()

        logger.info(f"전체 수집 완료: 성공 {successful_count}, 실패 {failed_count}")
        return self.data

    async def save_intermediate_data(self):
        """중간 저장"""
        try:
            filename = f"kb_intermediate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "collected_data": self.data,
                    "failed_cases": self.failed_cases,
                    "stats": {
                        "successful": len(self.data),
                        "failed": len(self.failed_cases),
                        "timestamp": datetime.now().isoformat()
                    }
                }, f, ensure_ascii=False, indent=2)

            logger.info(f"중간 저장 완료: {filename}")
        except Exception as e:
            logger.error(f"중간 저장 오류: {str(e)}")

    async def save_final_data(self):
        """최종 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 전체 데이터
            main_filename = f"kb_insurance_complete_{timestamp}.json"
            with open(main_filename, 'w', encoding='utf-8') as f:
                json.dump({
                    "metadata": {
                        "total_records": len(self.data),
                        "failed_cases": len(self.failed_cases),
                        "collection_date": timestamp,
                        "age_range": f"{min([d['age'] for d in self.data]) if self.data else 'N/A'}-{max([d['age'] for d in self.data]) if self.data else 'N/A'}",
                        "genders": list(set([d['gender'] for d in self.data]))
                    },
                    "data": self.data,
                    "failed_cases": self.failed_cases
                }, f, ensure_ascii=False, indent=2)

            # CSV 형태로도 저장 (분석 용이)
            await self.save_as_csv(timestamp)

            logger.info(f"최종 데이터 저장 완료: {main_filename}")

            # 통계 출력
            print("\n" + "="*60)
            print("KB생명 보험 데이터 수집 최종 결과")
            print("="*60)
            print(f"총 수집된 레코드: {len(self.data)}개")
            print(f"실패한 케이스: {len(self.failed_cases)}개")
            if self.data:
                ages = [d['age'] for d in self.data]
                print(f"나이 범위: {min(ages)}-{max(ages)}세")
                genders = list(set([d['gender'] for d in self.data]))
                print(f"성별: {', '.join(genders)}")
            print(f"수집 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*60)

        except Exception as e:
            logger.error(f"최종 저장 오류: {str(e)}")

    async def save_as_csv(self, timestamp):
        """CSV 형태로 간단한 데이터 저장"""
        try:
            csv_filename = f"kb_insurance_summary_{timestamp}.csv"

            with open(csv_filename, 'w', encoding='utf-8-sig') as f:
                # 헤더
                f.write("나이,성별,생년월일,보험료_개수,플랜_개수,특약_개수,수집시간\n")

                # 데이터
                for record in self.data:
                    f.write(f"{record['age']},{record['gender']},{record['birthdate']},")
                    f.write(f"{len(record.get('premium_info', []))},{len(record.get('plan_info', []))},")
                    f.write(f"{len(record.get('special_clauses', []))},{record['scraped_at']}\n")

            logger.info(f"CSV 파일 저장 완료: {csv_filename}")

        except Exception as e:
            logger.error(f"CSV 저장 오류: {str(e)}")

    async def run_full_collection(self, start_age=20, end_age=64):
        """전체 수집 실행"""
        logger.info("KB생명 보험 전체 데이터 수집 시작")

        # 작은 범위로 테스트 (예: 20-25세)
        if input("전체 수집하시겠습니까? (y/n): ").lower() != 'y':
            start_age = 20
            end_age = 25
            logger.info(f"테스트 모드: {start_age}-{end_age}세만 수집")

        await self.scrape_all_data(start_age, end_age)

async def main():
    scraper = KBFullScraper()
    await scraper.run_full_collection()

if __name__ == "__main__":
    asyncio.run(main())