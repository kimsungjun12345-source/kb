import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBTestCollector:
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

    async def test_single_case(self, age=30, gender="남성"):
        """단일 케이스 상세 테스트"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info(f"🎯 특약 개별 테스트 시작: {age}세 {gender}")

                # 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle", timeout=45000)
                await self.wait_random(2, 4)

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
                    logger.error("설계견적 버튼을 찾을 수 없음")
                    return None

                logger.info(f"✅ 버튼 클릭 성공: {button_clicked}")

                # 결과 페이지 로딩 대기
                await self.wait_random(4, 7)

                # 특약 개별 테스트 실행
                result = await self.test_special_clauses(page, age, gender, birthdate)

                # 결과 저장
                if result:
                    await self.save_test_data(result, age, gender)

                return result

            except Exception as e:
                logger.error(f"테스트 중 오류: {str(e)}")
                return None
            finally:
                await browser.close()

    async def test_special_clauses(self, page, age, gender, birthdate):
        """특약 개별 활성화 테스트"""
        try:
            result_data = {
                "age": age,
                "gender": gender,
                "birthdate": birthdate,
                "scraped_at": datetime.now().isoformat(),
                "page_url": page.url,
                "special_clauses": []
            }

            logger.info("🔍 특약 개별 테스트 시작...")

            # 먼저 기본 보험료 확인
            base_premium = await self.get_current_premium_amount(page)
            logger.info(f"💰 기본 보험료: {base_premium}")

            checkboxes = await page.query_selector_all("input[type='checkbox']")
            insurance_checkboxes = []

            # 보험 관련 체크박스만 필터링
            for i, checkbox in enumerate(checkboxes):
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

            logger.info(f"🎯 보험 관련 특약 발견: {len(insurance_checkboxes)}개")

            # 각 특약을 개별적으로 테스트 (최대 10개)
            test_count = 0
            for idx, (i, checkbox, parent_text) in enumerate(insurance_checkboxes[:10]):
                try:
                    is_checked = await checkbox.is_checked()

                    clause_info = {
                        "index": i,
                        "text": parent_text,
                        "is_checked": is_checked,
                        "base_premium": base_premium.get('amount') if base_premium else None,
                        "premium_with_clause": None,
                        "premium_difference": None,
                        "test_successful": False
                    }

                    # 체크되지 않은 특약만 테스트
                    if not is_checked:
                        try:
                            logger.info(f"📋 특약 {test_count+1} 테스트: {parent_text[:40]}...")

                            # 체크박스가 보이는지 확인
                            is_visible = await checkbox.evaluate("el => el.offsetParent !== null && el.offsetWidth > 0")

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
                                        difference = new_amount - base_amount
                                        clause_info["premium_difference"] = difference
                                        clause_info["test_successful"] = True

                                        logger.info(f"✅ 특약 테스트 성공: {difference:+,}원")

                                    except Exception as calc_e:
                                        clause_info["premium_difference"] = f"계산 오류: {str(calc_e)}"

                                # 체크박스 다시 해제
                                await checkbox.click()
                                await asyncio.sleep(1)

                                test_count += 1

                            else:
                                logger.warning(f"⚠️ 체크박스 보이지 않음: {parent_text[:30]}")

                        except Exception as e:
                            logger.warning(f"❌ 특약 테스트 오류: {str(e)}")

                    result_data["special_clauses"].append(clause_info)

                except Exception as e:
                    logger.warning(f"체크박스 처리 오류: {str(e)}")
                    continue

            logger.info(f"🎯 특약 테스트 완료: {test_count}개 성공")

            return result_data

        except Exception as e:
            logger.error(f"특약 테스트 중 오류: {str(e)}")
            return None

    async def save_test_data(self, data, age, gender):
        """테스트 데이터 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"kb_test_result_{age}_{gender}_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 테스트 결과 저장: {filename}")

            # 결과 요약 출력
            print("\n" + "="*60)
            print(f"🎯 KB생명 특약 개별 테스트 결과 - {age}세 {gender}")
            print("="*60)

            if data.get('special_clauses'):
                successful_tests = [c for c in data['special_clauses'] if c.get('test_successful')]
                print(f"총 발견된 특약: {len(data['special_clauses'])}개")
                print(f"성공한 테스트: {len(successful_tests)}개")

                if successful_tests:
                    print("\n💰 특약별 보험료 변화:")
                    for clause in successful_tests:
                        diff = clause.get('premium_difference', 0)
                        if isinstance(diff, int):
                            print(f"  - {clause['text'][:40]}: {diff:+,}원")

            print(f"수집 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print("="*60)

            return filename

        except Exception as e:
            logger.error(f"테스트 데이터 저장 오류: {str(e)}")
            return None

async def main():
    collector = KBTestCollector()
    logger.info("🚀 KB생명 특약 개별 테스트 시작")

    # 30세 남성으로 테스트
    result = await collector.test_single_case(30, "남성")

    if result:
        logger.info("✅ 특약 개별 테스트 완료!")
    else:
        logger.error("❌ 특약 개별 테스트 실패")

if __name__ == "__main__":
    asyncio.run(main())