import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBCompleteCollector:
    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"
        self.data = []
        self.failed_cases = []

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-images",
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
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def get_current_premium_amount(self, page):
        """현재 페이지에서 보험료 금액 추출"""
        try:
            premium_amount = await page.evaluate("""
                () => {
                    const selectors = [
                        '[class*="premium"]',
                        '[class*="price"]',
                        '[class*="amount"]',
                        '[id*="premium"]',
                        '[id*="price"]',
                        'td, th, span, div, strong'
                    ];

                    for (let selector of selectors) {
                        const elements = document.querySelectorAll(selector);

                        for (let el of elements) {
                            const text = el.textContent?.trim();

                            if (text && text.match(/\\d{1,3}(,\\d{3})*\\s*원/)) {
                                const match = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                                if (match && el.offsetParent !== null) {
                                    return {
                                        amount: match[1],
                                        fullText: text.substring(0, 50),
                                        selector: selector
                                    };
                                }
                            }
                        }
                    }
                    return null;
                }
            """)

            return premium_amount

        except Exception as e:
            logger.warning(f"보험료 금액 추출 중 오류: {str(e)}")
            return None

    async def scrape_single_case(self, age, gender, retry_count=0):
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
                    await asyncio.sleep(random.uniform(10, 20))
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
                result_data = await self.collect_complete_data(page, age, gender, birthdate)

                return result_data

            except Exception as e:
                logger.error(f"스크래핑 오류: {age}세 {gender} - {str(e)}")
                await browser.close()

                if "timeout" in str(e).lower() or "network" in str(e).lower():
                    await asyncio.sleep(random.uniform(5, 10))
                    return await self.scrape_single_case(age, gender, retry_count + 1)

                return None
            finally:
                await browser.close()

    async def collect_complete_data(self, page, age, gender, birthdate):
        """완전한 데이터 수집 (개선된 버전)"""
        try:
            result_data = {
                "age": age,
                "gender": gender,
                "birthdate": birthdate,
                "scraped_at": datetime.now().isoformat(),
                "page_url": page.url,
                "premium_info": [],
                "plan_info": [],
                "special_clauses": [],
                "tooltips": []
            }

            # 보험료 정보 수집 (개선된 로직)
            premium_data = await page.evaluate("""
                () => {
                    const premiums = [];
                    const allElements = document.querySelectorAll('*');

                    for (let el of allElements) {
                        const text = el.textContent?.trim();

                        if (text && text.length < 200 && el.offsetParent !== null) {
                            const premiumMatch = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/g);

                            if (premiumMatch) {
                                const cleanText = text.replace(/\\s+/g, ' ').trim();
                                if (!cleanText.includes('CDN') && !cleanText.includes('font-face') &&
                                    !cleanText.includes('JavaScript') && cleanText.length < 100) {

                                    premiums.push({
                                        text: cleanText,
                                        tagName: el.tagName,
                                        amounts: premiumMatch
                                    });

                                    if (premiums.length >= 15) break;
                                }
                            }
                        }
                    }
                    return premiums;
                }
            """)

            result_data["premium_info"] = premium_data

            # 플랜 정보 수집
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
                            if (plans.length >= 20) break;
                        }
                    }
                    return plans;
                }
            """)

            result_data["plan_info"] = plan_data

            # 특약 개별 활성화 및 보험료 변화 확인
            logger.info("특약 개별 테스트 시작...")

            # 먼저 기본 보험료 확인
            base_premium = await self.get_current_premium_amount(page)
            logger.info(f"기본 보험료: {base_premium}")

            checkboxes = await page.query_selector_all("input[type='checkbox']")
            insurance_checkboxes = []

            # 보험 관련 체크박스만 필터링
            for i, checkbox in enumerate(checkboxes[:20]):
                try:
                    parent_text = await checkbox.evaluate("el => el.closest('tr, div, label')?.textContent?.trim()?.substring(0, 100)")

                    if (parent_text and
                        not parent_text.startswith('통신사') and
                        not parent_text.startswith('개인정보') and
                        not parent_text.startswith('서비스') and
                        not parent_text.startswith('전체동의') and
                        ('특약' in parent_text or '보장' in parent_text or '급여' in parent_text or
                         '질환' in parent_text or '상해' in parent_text or '수술' in parent_text)):

                        insurance_checkboxes.append((i, checkbox, parent_text))

                except:
                    continue

            logger.info(f"보험 관련 특약 발견: {len(insurance_checkboxes)}개")

            # 각 특약을 개별적으로 테스트
            for idx, (i, checkbox, parent_text) in enumerate(insurance_checkboxes[:15]):
                try:
                    is_checked = await checkbox.is_checked()

                    clause_info = {
                        "index": i,
                        "text": parent_text,
                        "is_checked": is_checked,
                        "base_premium": base_premium.get('amount') if base_premium else None,
                        "premium_with_clause": None,
                        "premium_difference": None
                    }

                    # 체크되지 않은 특약만 테스트
                    if not is_checked:
                        try:
                            logger.info(f"특약 {idx+1}/{len(insurance_checkboxes)} 테스트: {parent_text[:30]}...")

                            # 체크박스가 보이는지 확인
                            is_visible = await checkbox.evaluate("el => el.offsetParent !== null")

                            if is_visible:
                                # 특약 활성화
                                await checkbox.click()
                                await asyncio.sleep(2)  # 보험료 재계산 대기

                                # 변경된 보험료 확인
                                new_premium = await self.get_current_premium_amount(page)

                                if new_premium and base_premium:
                                    clause_info["premium_with_clause"] = new_premium.get('amount')

                                    # 보험료 차이 계산
                                    try:
                                        base_amount = int(base_premium.get('amount', '0').replace(',', ''))
                                        new_amount = int(new_premium.get('amount', '0').replace(',', ''))
                                        clause_info["premium_difference"] = new_amount - base_amount
                                    except:
                                        clause_info["premium_difference"] = "계산 불가"

                                # 체크박스 다시 해제
                                await checkbox.click()
                                await asyncio.sleep(1)

                                logger.info(f"✓ 특약 테스트 완료: {clause_info['premium_difference']}")

                            else:
                                logger.warning(f"특약 체크박스 보이지 않음: {parent_text[:30]}")

                        except Exception as e:
                            logger.warning(f"특약 테스트 오류: {str(e)}")

                    result_data["special_clauses"].append(clause_info)

                except Exception as e:
                    logger.warning(f"체크박스 처리 오류: {str(e)}")
                    continue

            # 툴팁 수집
            tooltips = await page.evaluate("""
                () => {
                    const tooltips = [];
                    const elements = document.querySelectorAll('[title], [data-tooltip], [alt]');

                    for (let i = 0; i < Math.min(elements.length, 20); i++) {
                        const el = elements[i];
                        const title = el.getAttribute('title') || el.getAttribute('data-tooltip') || el.getAttribute('alt');

                        if (title && title.trim()) {
                            tooltips.push({
                                content: title.trim(),
                                tagName: el.tagName,
                                index: i
                            });
                        }
                    }
                    return tooltips;
                }
            """)

            result_data["tooltips"] = tooltips

            logger.info(f"데이터 수집 완료: {age}세 {gender} - 보험료 {len(premium_data)}개, 플랜 {len(plan_data)}개, 특약 {len(result_data['special_clauses'])}개, 툴팁 {len(tooltips)}개")

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
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # 전체 데이터
            main_filename = f"kb_complete_data_{timestamp}.json"
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

            # CSV 형태로도 저장
            csv_filename = f"kb_complete_summary_{timestamp}.csv"
            with open(csv_filename, 'w', encoding='utf-8-sig') as f:
                f.write("나이,성별,생년월일,보험료_개수,플랜_개수,특약_개수,툴팁_개수,수집시간\n")
                for record in self.data:
                    f.write(f"{record['age']},{record['gender']},{record['birthdate']},")
                    f.write(f"{len(record.get('premium_info', []))},{len(record.get('plan_info', []))},")
                    f.write(f"{len(record.get('special_clauses', []))},{len(record.get('tooltips', []))},{record['scraped_at']}\n")

            logger.info(f"최종 데이터 저장 완료: {main_filename}, {csv_filename}")

            # 결과 요약 출력
            print("\n" + "="*60)
            print("KB생명 보험 완전한 데이터 수집 결과")
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

    async def run_full_collection(self, start_age=20, end_age=64):
        """전체 수집 실행"""
        logger.info("KB생명 보험 완전한 데이터 수집 시작")

        # 사용자 확인
        print(f"\n전체 수집 범위: {start_age}-{end_age}세 (총 {(end_age-start_age+1)*2}개 케이스)")
        print("예상 소요시간: 약 3-5시간")

        if input("전체 수집을 시작하시겠습니까? (y/n): ").lower() == 'y':
            await self.scrape_all_data(start_age, end_age)
        else:
            logger.info("수집이 취소되었습니다.")

async def main():
    collector = KBCompleteCollector()
    await collector.run_full_collection()

if __name__ == "__main__":
    asyncio.run(main())