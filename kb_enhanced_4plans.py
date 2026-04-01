"""
KB Life e-건강보험 4개 플랜 전체 스크래퍼
종합플랜(든든), 종합플랜(실속), 입원간병플랜, 뇌심플랜 모두 수집
"""

import asyncio
import json
import random
from datetime import datetime
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KB_EHealth_4Plans:
    def __init__(self):
        self.url = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

    async def create_browser(self):
        """브라우저 생성"""
        playwright = await async_playwright().__aenter__()
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
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
        """)

        return playwright, browser, context

    def generate_birthdate(self, age):
        """생년월일 생성"""
        current_year = datetime.now().year
        birth_year = current_year - age
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return f"{birth_year}{month:02d}{day:02d}"

    async def scrape_all_plans(self, age, gender):
        """4개 플랜 모두 스크래핑"""
        playwright, browser, context = await self.create_browser()

        try:
            page = await context.new_page()
            logger.info(f"KB e-건강보험 4개 플랜 스크래핑 시작: {age}세 {gender}")

            # 페이지 접속
            await page.goto(self.url, wait_until="networkidle")
            await asyncio.sleep(5)

            # 기본 정보 입력
            birthdate = self.generate_birthdate(age)
            await page.fill("#birthday", birthdate)
            await asyncio.sleep(2)

            # 성별 선택
            gender_value = "1" if gender == "남성" else "2"
            await page.click(f'input[name="genderCode"][value="{gender_value}"]')
            await asyncio.sleep(2)

            # 계산하기 버튼
            await page.click("#calculateResult")
            await asyncio.sleep(5)

            # 페이지 안정화 대기
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)

            # 모든 플랜 탐지
            all_plans = await self.detect_all_plans(page)
            logger.info(f"감지된 플랜 수: {len(all_plans)}")

            result_data = {
                "basic_info": {
                    "age": age,
                    "gender": gender,
                    "birthdate": birthdate,
                    "scraped_at": datetime.now().isoformat(),
                    "product_name": "KB 딱좋은 e-건강보험 무배당 (갱신형)(일반심사형)(해약환급금 미지급형)"
                },
                "detected_plans": {},
                "comprehensive_plans": {},
                "special_plans": {}
            }

            # 각 플랜별 스크래핑
            for plan_info in all_plans:
                await self.scrape_single_plan(page, plan_info, result_data)
                await asyncio.sleep(3)

            # 결과 저장
            await self.save_results(result_data, age, gender)

            return result_data

        finally:
            await browser.close()
            await playwright.__aexit__(None, None, None)

    async def detect_all_plans(self, page):
        """모든 플랜 감지 - 강화된 버전"""
        plans = await page.evaluate("""
            () => {
                const allPlans = [];

                // 1. 라디오 버튼 기반 플랜 감지
                const radios = document.querySelectorAll('input[type="radio"]');
                radios.forEach((radio, index) => {
                    if (radio.name !== 'genderCode') {
                        const parent = radio.closest('tr, div, li, label, td');
                        if (parent) {
                            const text = parent.textContent?.trim() || '';

                            // e-건강보험 플랜 키워드 감지
                            const planKeywords = [
                                '든든', '실속', '입원', '간병', '뇌심',
                                '종합', '플랜', '보장', '형'
                            ];

                            const hasKeyword = planKeywords.some(keyword =>
                                text.includes(keyword)
                            );

                            if (hasKeyword && text.length > 2 && text.length < 200) {
                                allPlans.push({
                                    type: 'radio',
                                    index: index,
                                    name: radio.name || '',
                                    value: radio.value || '',
                                    id: radio.id || '',
                                    text: text,
                                    checked: radio.checked,
                                    visible: radio.offsetParent !== null
                                });
                            }
                        }
                    }
                });

                // 2. 체크박스 기반 플랜/특약 감지
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                checkboxes.forEach((checkbox, index) => {
                    const parent = checkbox.closest('tr, div, li, label, td');
                    if (parent) {
                        const text = parent.textContent?.trim() || '';

                        // 플랜 관련 체크박스 감지
                        if ((text.includes('플랜') || text.includes('든든') || text.includes('실속') ||
                             text.includes('입원간병') || text.includes('뇌심')) &&
                            !text.includes('동의') && !text.includes('약관')) {

                            allPlans.push({
                                type: 'checkbox',
                                index: index,
                                name: checkbox.name || '',
                                value: checkbox.value || '',
                                id: checkbox.id || '',
                                text: text,
                                checked: checkbox.checked,
                                visible: checkbox.offsetParent !== null
                            });
                        }
                    }
                });

                // 3. 테이블 행 기반 플랜 감지
                const rows = document.querySelectorAll('tr, .plan-row, .product-row');
                rows.forEach((row, index) => {
                    const text = row.textContent?.trim() || '';
                    const hasInput = row.querySelector('input[type="radio"], input[type="checkbox"]');

                    if (hasInput && (text.includes('든든') || text.includes('실속') ||
                                   text.includes('입원간병') || text.includes('뇌심'))) {
                        allPlans.push({
                            type: 'row',
                            index: index,
                            text: text,
                            element: 'tr'
                        });
                    }
                });

                return allPlans;
            }
        """)

        # 플랜 분류
        classified_plans = self.classify_plans(plans)
        return classified_plans

    def classify_plans(self, plans):
        """플랜 분류 및 중복 제거"""
        classified = {
            'comprehensive_dundeun': [],
            'comprehensive_silsok': [],
            'hospital_care': [],
            'brain_heart': []
        }

        for plan in plans:
            text_lower = plan['text'].lower()

            if '든든' in plan['text']:
                classified['comprehensive_dundeun'].append(plan)
            elif '실속' in plan['text']:
                classified['comprehensive_silsok'].append(plan)
            elif '입원' in plan['text'] and '간병' in plan['text']:
                classified['hospital_care'].append(plan)
            elif '뇌심' in plan['text'] or ('뇌' in plan['text'] and '심' in plan['text']):
                classified['brain_heart'].append(plan)
            elif '종합' in plan['text']:
                # 종합플랜인데 든든/실속 구분이 없는 경우
                if len(classified['comprehensive_dundeun']) == 0:
                    classified['comprehensive_dundeun'].append(plan)
                else:
                    classified['comprehensive_silsok'].append(plan)

        # 각 카테고리에서 가장 적합한 플랜 선택
        final_plans = []
        for category, plan_list in classified.items():
            if plan_list:
                # 가장 적합한 플랜 선택 (visible이고 활성화된 것 우선)
                best_plan = max(plan_list, key=lambda p: (
                    p.get('visible', False),
                    p.get('checked', False),
                    len(p.get('text', ''))
                ))
                best_plan['category'] = category
                final_plans.append(best_plan)

        return final_plans

    async def scrape_single_plan(self, page, plan_info, result_data):
        """단일 플랜 스크래핑"""
        try:
            category = plan_info.get('category', 'unknown')
            plan_text = plan_info.get('text', '')[:50]

            logger.info(f"플랜 스크래핑: {category} - {plan_text}")

            # 플랜 선택
            if plan_info['type'] == 'radio':
                await page.evaluate(f"""
                    () => {{
                        const radios = document.querySelectorAll('input[type="radio"]');
                        const target = radios[{plan_info['index']}];
                        if (target) {{
                            target.checked = true;
                            target.click();
                            target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                """)
            elif plan_info['type'] == 'checkbox':
                await page.evaluate(f"""
                    () => {{
                        const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                        const target = checkboxes[{plan_info['index']}];
                        if (target) {{
                            target.checked = true;
                            target.click();
                            target.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        }}
                    }}
                """)

            await asyncio.sleep(3)

            # 보험료 추출
            premium = await self.extract_premium(page)

            # 특약 정보 추출
            clauses = await self.extract_clauses(page)

            # 결과 저장
            plan_data = {
                "plan_info": plan_info,
                "premium": premium,
                "clauses": clauses,
                "clause_count": len(clauses)
            }

            if 'comprehensive' in category:
                result_data["comprehensive_plans"][category] = plan_data
            else:
                result_data["special_plans"][category] = plan_data

            logger.info(f"{category}: 보험료={premium}, 특약={len(clauses)}개")

        except Exception as e:
            logger.error(f"플랜 스크래핑 오류 ({category}): {str(e)}")

    async def extract_premium(self, page):
        """보험료 추출"""
        try:
            premium = await page.evaluate("""
                () => {
                    const elements = document.querySelectorAll('*');

                    for (let el of elements) {
                        const text = el.textContent?.trim();
                        if (!text || !el.offsetParent) continue;

                        // 보험료 패턴 매치
                        const match = text.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                        if (match) {
                            const parent = el.closest('tr, div, section');
                            const context = parent ? parent.textContent : text;

                            // 우선순위 키워드
                            const priorities = ['총보험료', '월납보험료', '보험료계', '납입보험료'];

                            for (let keyword of priorities) {
                                if (context.includes(keyword)) {
                                    return match[0];
                                }
                            }
                        }
                    }

                    // 대안: 첫 번째 보험료 패턴
                    for (let el of elements) {
                        const match = el.textContent?.match(/(\\d{1,3}(?:,\\d{3})*)\\s*원/);
                        if (match && el.offsetParent !== null) {
                            return match[0];
                        }
                    }

                    return null;
                }
            """)
            return premium
        except:
            return None

    async def extract_clauses(self, page):
        """특약 추출"""
        try:
            clauses = await page.evaluate("""
                () => {
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    const result = [];

                    checkboxes.forEach((checkbox, index) => {
                        const parent = checkbox.closest('tr, div, li, label');
                        if (parent) {
                            const text = parent.textContent?.trim();

                            // 보험 특약만 필터링
                            if (text && !text.includes('동의') && !text.includes('약관') &&
                                (text.includes('특약') || text.includes('보장') ||
                                 text.includes('진단') || text.includes('치료') ||
                                 text.includes('수술') || text.includes('입원'))) {

                                result.push({
                                    index: index,
                                    text: text.substring(0, 100),
                                    enabled: !checkbox.disabled,
                                    visible: checkbox.offsetParent !== null,
                                    checked: checkbox.checked
                                });
                            }
                        }
                    });

                    return result;
                }
            """)
            return clauses
        except:
            return []

    async def save_results(self, data, age, gender):
        """결과 저장"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"kb_ehealth_4plans_{age}_{gender}_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"결과 저장 완료: {filename}")

            # 요약 출력
            print("\n" + "="*80)
            print(f"KB 딱좋은 e-건강보험 4개 플랜 스크래핑 결과 - {age}세 {gender}")
            print("="*80)

            comp_plans = data.get("comprehensive_plans", {})
            special_plans = data.get("special_plans", {})

            print(f"종합플랜: {len(comp_plans)}개")
            for plan_key, plan_data in comp_plans.items():
                premium = plan_data.get("premium", "N/A")
                clause_count = plan_data.get("clause_count", 0)
                print(f"   - {plan_key}: 보험료={premium}, 특약={clause_count}개")

            print(f"특수플랜: {len(special_plans)}개")
            for plan_key, plan_data in special_plans.items():
                premium = plan_data.get("premium", "N/A")
                clause_count = plan_data.get("clause_count", 0)
                print(f"   - {plan_key}: 보험료={premium}, 특약={clause_count}개")

            total_plans = len(comp_plans) + len(special_plans)
            print(f"\n총 감지된 플랜: {total_plans}/4개")
            print("="*80)

        except Exception as e:
            logger.error(f"결과 저장 오류: {str(e)}")

async def main():
    scraper = KB_EHealth_4Plans()
    await scraper.scrape_all_plans(30, "남성")

if __name__ == "__main__":
    asyncio.run(main())