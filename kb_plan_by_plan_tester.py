import asyncio
from playwright.async_api import async_playwright
import logging
import random
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBPlanByPlanTester:
    """플랜별 특약 차이 분석기"""

    def __init__(self):
        self.base_url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async def create_stealth_browser(self, playwright):
        browser = await playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
            ]
        )

        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        return browser, context

    def generate_birthdate(self, age=30):
        current_year = datetime.now().year
        birth_year = current_year - age
        return f"{birth_year}0315"

    async def wait_random(self, min_seconds=2, max_seconds=4):
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def select_gender(self, page, gender="남성"):
        """성별 선택 (수정된 버전)"""
        gender_value = "1" if gender == "남성" else "2"
        logger.info(f"성별 선택: {gender} ({gender_value})")

        success = await page.evaluate(f"""
            () => {{
                const radios = document.querySelectorAll('input[name="genderCode"]');
                for (let radio of radios) {{
                    if (radio.value === '{gender_value}') {{
                        radio.checked = true;
                        radio.click();
                        radio.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        return true;
                    }}
                }}
                return false;
            }}
        """)

        if success:
            logger.info("✅ 성별 선택 성공")
            return True
        else:
            logger.error("❌ 성별 선택 실패")
            return False

    async def test_plan_specific_clauses(self):
        """플랜별 특약 차이 테스트"""
        async with async_playwright() as playwright:
            browser, context = await self.create_stealth_browser(playwright)

            try:
                page = await context.new_page()
                logger.info("🔍 플랜별 특약 차이 분석 시작")

                # 기본 페이지 로드
                await page.goto(self.base_url, wait_until="networkidle")
                await self.wait_random(3, 5)

                # 생년월일과 성별 입력
                birthdate = self.generate_birthdate(30)
                await page.fill("#birthday", birthdate)
                await self.wait_random(1, 2)

                await self.select_gender(page, "남성")
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

                if button_clicked:
                    logger.info(f"✅ {button_clicked} 버튼 클릭")
                else:
                    logger.error("❌ 설계견적 버튼 찾을 수 없음")
                    return

                await self.wait_random(5, 8)

                # 플랜별 분석 시작
                plan_results = {}

                # 기본 상태 (플랜 선택 전)
                logger.info("📋 기본 상태 (플랜 선택 전) 특약 분석")
                default_clauses = await self.get_available_clauses(page)
                plan_results["default_state"] = {
                    "clause_count": len(default_clauses),
                    "clauses": default_clauses
                }
                logger.info(f"기본 상태: {len(default_clauses)}개 특약")

                # 플랜 라디오 버튼 찾기
                plan_radios = await page.evaluate("""
                    () => {
                        const radios = Array.from(document.querySelectorAll('input[type="radio"]'));
                        const plans = [];

                        radios.forEach((radio, index) => {
                            if (radio.name !== 'genderCode') {
                                const parent = radio.closest('tr, div, li, label');
                                const text = parent ? parent.textContent?.trim() : '';

                                if (text.includes('플랜') || text.includes('형') ||
                                    text.includes('타입') || radio.name.includes('quest') ||
                                    radio.name.includes('type')) {

                                    plans.push({
                                        index: index,
                                        name: radio.name,
                                        value: radio.value,
                                        text: text.substring(0, 100),
                                        checked: radio.checked,
                                        visible: radio.offsetParent !== null
                                    });
                                }
                            }
                        });

                        return plans;
                    }
                """)

                logger.info(f"발견된 플랜 옵션: {len(plan_radios)}개")

                # 각 플랜별로 테스트
                for i, plan in enumerate(plan_radios[:6]):  # 최대 6개 테스트
                    if not plan['visible']:
                        continue

                    plan_key = f"plan_{plan['name']}_{plan['value']}"
                    logger.info(f"🎯 플랜 {i+1} 테스트: {plan['name']}={plan['value']}")
                    logger.info(f"   설명: {plan['text'][:50]}")

                    try:
                        # 플랜 선택
                        await page.evaluate(f"""
                            () => {{
                                const radios = document.querySelectorAll('input[type="radio"]');
                                const target = radios[{plan['index']}];
                                if (target && target.offsetParent !== null) {{
                                    target.checked = true;
                                    target.click();
                                    target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                }}
                            }}
                        """)

                        await self.wait_random(3, 5)  # 플랜 변경 후 페이지 업데이트 대기

                        # 이 플랜에서 사용가능한 특약들 확인
                        plan_clauses = await self.get_available_clauses(page)

                        # 보험료 확인
                        premium = await self.get_current_premium(page)

                        plan_results[plan_key] = {
                            "plan_info": plan,
                            "clause_count": len(plan_clauses),
                            "clauses": plan_clauses,
                            "premium": premium,
                            "difference_from_default": self.compare_clause_lists(default_clauses, plan_clauses)
                        }

                        logger.info(f"   특약 개수: {len(plan_clauses)}개")
                        logger.info(f"   보험료: {premium}")

                        # 기본 상태와 차이점 분석
                        diff = self.compare_clause_lists(default_clauses, plan_clauses)
                        if diff['added'] or diff['removed']:
                            logger.info(f"   📊 기본 상태와 차이:")
                            if diff['added']:
                                logger.info(f"      추가된 특약: {len(diff['added'])}개")
                                for clause in diff['added'][:3]:  # 처음 3개만
                                    logger.info(f"        + {clause[:40]}")
                            if diff['removed']:
                                logger.info(f"      제거된 특약: {len(diff['removed'])}개")
                                for clause in diff['removed'][:3]:  # 처음 3개만
                                    logger.info(f"        - {clause[:40]}")
                        else:
                            logger.info("   📊 기본 상태와 동일한 특약 구성")

                    except Exception as e:
                        logger.error(f"플랜 {i+1} 테스트 중 오류: {str(e)}")
                        plan_results[plan_key] = {"error": str(e)}

                # 결과 저장
                await self.save_plan_analysis(plan_results)

                input("분석 완료. 엔터를 눌러 종료하세요...")

            finally:
                await browser.close()

    async def get_available_clauses(self, page):
        """현재 상태에서 사용가능한 특약들 수집"""
        try:
            clauses = await page.evaluate("""
                () => {
                    const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
                    const clauses = [];

                    checkboxes.forEach((checkbox, index) => {
                        const parent = checkbox.closest('tr, div, li, label');
                        if (!parent) return;

                        const text = parent.textContent?.trim();

                        // 약관/동의 관련은 제외, 보험 관련만 포함
                        if (!text.includes('동의') && !text.includes('약관') &&
                            !text.includes('개인정보') && !text.includes('통신사') &&
                            (text.includes('특약') || text.includes('보장') ||
                             text.includes('급여') || text.includes('질환') ||
                             text.includes('상해') || text.includes('수술') ||
                             text.includes('암') || text.includes('뇌') ||
                             text.includes('심장') || text.includes('치료'))) {

                            clauses.push({
                                index: index,
                                text: text.substring(0, 100),
                                enabled: !checkbox.disabled,
                                visible: checkbox.offsetParent !== null && checkbox.offsetWidth > 0,
                                checked: checkbox.checked
                            });
                        }
                    });

                    return clauses;
                }
            """)

            return clauses

        except Exception as e:
            logger.error(f"특약 수집 중 오류: {str(e)}")
            return []

    async def get_current_premium(self, page):
        """현재 보험료 추출"""
        try:
            premium = await page.evaluate("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));

                    for (let el of elements) {
                        const text = el.textContent?.trim();
                        if (text && text.includes('원') &&
                            /\\d{1,3}(,\\d{3})*/.test(text) &&
                            el.offsetParent !== null) {

                            const parent = el.closest('tr, div');
                            const context = parent ? parent.textContent : text;

                            if (context.includes('총보험료') || context.includes('월납보험료') ||
                                context.includes('보험료계') || context.includes('납입보험료')) {
                                const match = text.match(/\\d{1,3}(,\\d{3})*원/);
                                return match ? match[0] : text.trim();
                            }
                        }
                    }

                    // 대안: 첫 번째 보험료 패턴
                    const premiumPattern = /\\d{1,3}(,\\d{3})*원/;
                    for (let el of elements) {
                        const match = el.textContent.match(premiumPattern);
                        if (match && el.offsetParent !== null) {
                            return match[0];
                        }
                    }

                    return null;
                }
            """)

            return premium

        except Exception as e:
            logger.error(f"보험료 추출 중 오류: {str(e)}")
            return None

    def compare_clause_lists(self, list1, list2):
        """두 특약 리스트 비교"""
        try:
            texts1 = set([clause['text'] for clause in list1])
            texts2 = set([clause['text'] for clause in list2])

            return {
                'added': list(texts2 - texts1),
                'removed': list(texts1 - texts2),
                'common': list(texts1 & texts2)
            }

        except Exception as e:
            logger.error(f"특약 리스트 비교 중 오류: {str(e)}")
            return {'added': [], 'removed': [], 'common': []}

    async def save_plan_analysis(self, results):
        """플랜 분석 결과 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"kb_plan_analysis_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            logger.info(f"플랜 분석 결과 저장: {filename}")

            # 요약 출력
            print("\n" + "="*60)
            print("🎯 KB생명 플랜별 특약 차이 분석 결과")
            print("="*60)

            default_count = results.get("default_state", {}).get("clause_count", 0)
            print(f"기본 상태 특약: {default_count}개")

            plan_count = 0
            for key, data in results.items():
                if key.startswith("plan_") and not data.get("error"):
                    plan_count += 1
                    clause_count = data.get("clause_count", 0)
                    premium = data.get("premium", "N/A")
                    diff = data.get("difference_from_default", {})

                    print(f"\n플랜 {plan_count}: {clause_count}개 특약, 보험료: {premium}")
                    if diff.get('added'):
                        print(f"  + 추가된 특약: {len(diff['added'])}개")
                    if diff.get('removed'):
                        print(f"  - 제거된 특약: {len(diff['removed'])}개")

            print("="*60)

        except Exception as e:
            logger.error(f"결과 저장 중 오류: {str(e)}")

async def main():
    tester = KBPlanByPlanTester()
    await tester.test_plan_specific_clauses()

if __name__ == "__main__":
    asyncio.run(main())