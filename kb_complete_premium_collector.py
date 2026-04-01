#!/usr/bin/env python3
"""
KB생명 보험 완전 수집기 - 생년월일/성별 입력, 플랜별 특약, 도움말 포함
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import time
import random

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class KBCompletePremiumCollector:
    def __init__(self):
        self.browser = None
        self.page = None
        self.results = {
            'metadata': {
                'scraped_at': datetime.now().isoformat(),
                'scraper_version': 'complete_premium_1.0',
                'description': '생년월일/성별 입력, 플랜별 특약, 도움말 완전 수집기'
            },
            'products': []
        }

        # 테스트할 사람들 (나이/성별)
        self.test_profiles = [
            {'birth_date': '19900315', 'gender': '남성', 'age': 34},
            {'birth_date': '19850720', 'gender': '여성', 'age': 39},
            {'birth_date': '19950505', 'gender': '남성', 'age': 29},
            {'birth_date': '19800910', 'gender': '여성', 'age': 44}
        ]

        # KB생명 보험상품 URL들
        self.product_urls = [
            'https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5',  # 착한암보험
            'https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5',  # 딱좋은e건강보험
            'https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YT_01&productType=5',  # 딱좋은e건강보험 간편형
            'https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_SR_01&productType=5',  # 착한정기보험II
            'https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_NP_01&productType=5'   # 하이파이브평생연금보험
        ]

    async def setup_browser(self):
        """브라우저 초기화"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=False,
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor',
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ]
        )

        context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )

        self.page = await context.new_page()

        # 탐지 방지 스크립트 실행
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            window.chrome = {
                runtime: {},
            };

            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
        """)

    async def wait_random(self, min_seconds=2, max_seconds=5):
        """랜덤 대기"""
        wait_time = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(wait_time)

    async def input_birth_date_and_gender(self, birth_date, gender):
        """생년월일과 성별 입력 - 실제 KB생명 필드명 사용"""
        try:
            logger.info(f"생년월일 {birth_date}, 성별 {gender} 입력 중...")

            # 실제 생년월일 입력 필드: id="birthday"
            try:
                birth_field = await self.page.wait_for_selector('#birthday', timeout=10000)
                if birth_field:
                    # 기존 텍스트 지우고 새로 입력
                    await birth_field.click()
                    await birth_field.press('Control+a')  # 모든 텍스트 선택
                    await birth_field.fill(birth_date)    # 새 텍스트로 교체
                    logger.info(f"생년월일 입력 완료: {birth_date}")
                else:
                    logger.error("생년월일 입력 필드를 찾을 수 없습니다.")
                    return False
            except Exception as e:
                logger.error(f"생년월일 입력 실패: {e}")
                return False

            await self.wait_random(1, 2)

            # 실제 성별 라디오 버튼: name="genderCode", value="1"(남성), "2"(여성)
            gender_value = "1" if gender == "남성" else "2"
            try:
                gender_selector = f'input[name="genderCode"][value="{gender_value}"]'
                gender_field = await self.page.wait_for_selector(gender_selector, timeout=5000)
                if gender_field:
                    await gender_field.click()
                    logger.info(f"성별 선택 완료: {gender} (value={gender_value})")
                else:
                    logger.error(f"성별 라디오 버튼을 찾을 수 없습니다: {gender_selector}")
                    return False
            except Exception as e:
                logger.error(f"성별 선택 실패: {e}")
                return False

            await self.wait_random(1, 2)
            return True

        except Exception as e:
            logger.error(f"생년월일/성별 입력 실패: {e}")
            return False

    async def calculate_premium(self):
        """보험료 계산 실행"""
        try:
            # 보험료 계산 버튼 찾기
            calc_selectors = [
                'button:has-text("보험료")',
                'button:has-text("계산")',
                'input[type="submit"]',
                'button[onclick*="calc"]',
                '.calc-btn',
                '#calcBtn',
                'button:has-text("조회")'
            ]

            for selector in calc_selectors:
                try:
                    calc_btn = await self.page.wait_for_selector(selector, timeout=3000)
                    if calc_btn:
                        await calc_btn.click()
                        logger.info("보험료 계산 버튼 클릭")
                        await self.wait_random(3, 5)
                        return True
                except:
                    continue

            logger.warning("보험료 계산 버튼을 찾을 수 없습니다.")
            return False

        except Exception as e:
            logger.error(f"보험료 계산 실패: {e}")
            return False

    async def collect_plan_premiums(self):
        """4가지 플랜별 보험료 수집"""
        plans_data = {}

        try:
            # 플랜 탭들 찾기
            plan_selectors = [
                'button[data-plan]',
                '.plan-tab',
                'input[name="planType"]',
                'button:has-text("플랜")',
                '.tab-menu button'
            ]

            plan_buttons = []
            for selector in plan_selectors:
                try:
                    buttons = await self.page.query_selector_all(selector)
                    if buttons:
                        plan_buttons.extend(buttons)
                except:
                    continue

            if not plan_buttons:
                logger.warning("플랜 버튼을 찾을 수 없습니다.")
                return plans_data

            # 각 플랜별로 처리
            for i, plan_btn in enumerate(plan_buttons[:4]):  # 최대 4개 플랜
                try:
                    plan_name = await plan_btn.inner_text()
                    logger.info(f"플랜 {i+1} 처리 중: {plan_name}")

                    await plan_btn.click()
                    await self.wait_random(2, 3)

                    # 모든 특약 활성화
                    special_coverage_data = await self.activate_all_special_coverages()

                    # 보험료 정보 수집
                    premium_info = await self.collect_premium_info()

                    # 도움말 정보 수집
                    help_info = await self.collect_help_info()

                    plans_data[f'plan_{i+1}'] = {
                        'plan_name': plan_name,
                        'premium_info': premium_info,
                        'special_coverages': special_coverage_data,
                        'help_info': help_info
                    }

                except Exception as e:
                    logger.error(f"플랜 {i+1} 처리 실패: {e}")
                    continue

            return plans_data

        except Exception as e:
            logger.error(f"플랜별 보험료 수집 실패: {e}")
            return plans_data

    async def activate_all_special_coverages(self):
        """모든 특약 활성화"""
        special_coverages = {}

        try:
            # 특약 체크박스들 찾기
            coverage_selectors = [
                'input[type="checkbox"]:not([disabled])',
                '.special-coverage input[type="checkbox"]',
                '.option-checkbox',
                'input[name*="special"]',
                'input[name*="coverage"]'
            ]

            all_checkboxes = []
            for selector in coverage_selectors:
                try:
                    checkboxes = await self.page.query_selector_all(selector)
                    all_checkboxes.extend(checkboxes)
                except:
                    continue

            logger.info(f"발견된 특약 체크박스: {len(all_checkboxes)}개")

            for i, checkbox in enumerate(all_checkboxes):
                try:
                    # 이미 체크되어 있는지 확인
                    is_checked = await checkbox.is_checked()

                    if not is_checked:
                        await checkbox.check()
                        await self.wait_random(0.5, 1)

                    # 특약 이름 가져오기
                    coverage_name = f"특약_{i+1}"
                    try:
                        # 라벨 텍스트 찾기
                        label = await self.page.evaluate('''(checkbox) => {
                            const label = checkbox.closest('label') || document.querySelector(`label[for="${checkbox.id}"]`);
                            return label ? label.textContent.trim() : '';
                        }''', checkbox)
                        if label:
                            coverage_name = label
                    except:
                        pass

                    special_coverages[coverage_name] = {
                        'activated': True,
                        'index': i
                    }

                except Exception as e:
                    logger.error(f"특약 {i} 활성화 실패: {e}")
                    continue

            # 특약 활성화 후 보험료 재계산
            await self.calculate_premium()

            return special_coverages

        except Exception as e:
            logger.error(f"특약 활성화 실패: {e}")
            return special_coverages

    async def collect_premium_info(self):
        """보험료 정보 수집"""
        premium_info = {}

        try:
            # 보험료 관련 텍스트들 수집
            premium_selectors = [
                '.premium-amount',
                '.price',
                '[class*="premium"]',
                '[id*="premium"]',
                '.amount',
                '.monthly-premium',
                '.annual-premium'
            ]

            for selector in premium_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements:
                        text = await element.inner_text()
                        if text and ('원' in text or ',' in text):
                            premium_info[selector] = text.strip()
                except:
                    continue

            # 전체 페이지에서 보험료 관련 텍스트 검색
            page_text = await self.page.inner_text('body')
            lines = page_text.split('\n')

            for line in lines:
                line = line.strip()
                if line and ('보험료' in line or '원' in line) and len(line) < 100:
                    key = f"text_line_{len(premium_info)}"
                    premium_info[key] = line

            return premium_info

        except Exception as e:
            logger.error(f"보험료 정보 수집 실패: {e}")
            return premium_info

    async def collect_help_info(self):
        """도움말(물음표) 정보 수집"""
        help_info = {}

        try:
            # 물음표, 도움말 아이콘들 찾기
            help_selectors = [
                '[title*="도움말"]',
                '[alt*="도움말"]',
                '.help-icon',
                '.tooltip',
                '[class*="help"]',
                '[class*="question"]',
                'span:has-text("?")',
                'i:has-text("?")',
                '.fa-question',
                '.question-mark'
            ]

            help_count = 0
            for selector in help_selectors:
                try:
                    help_elements = await self.page.query_selector_all(selector)

                    for help_elem in help_elements:
                        try:
                            # 도움말 요소 클릭
                            await help_elem.hover()
                            await self.wait_random(0.5, 1)

                            # 툴팁이나 팝업 내용 수집
                            tooltip_selectors = [
                                '.tooltip-content',
                                '.help-popup',
                                '.tooltip-text',
                                '.popup-content',
                                '[role="tooltip"]'
                            ]

                            for tooltip_sel in tooltip_selectors:
                                try:
                                    tooltip = await self.page.wait_for_selector(tooltip_sel, timeout=2000)
                                    if tooltip:
                                        help_text = await tooltip.inner_text()
                                        if help_text.strip():
                                            help_info[f'help_{help_count}'] = {
                                                'selector': selector,
                                                'content': help_text.strip()
                                            }
                                            help_count += 1
                                            break
                                except:
                                    continue

                            # title 속성 확인
                            title = await help_elem.get_attribute('title')
                            if title and title.strip():
                                help_info[f'help_{help_count}'] = {
                                    'selector': selector,
                                    'content': title.strip()
                                }
                                help_count += 1

                        except Exception as e:
                            continue

                except Exception as e:
                    continue

            logger.info(f"도움말 정보 {help_count}개 수집")
            return help_info

        except Exception as e:
            logger.error(f"도움말 정보 수집 실패: {e}")
            return help_info

    async def process_product(self, url):
        """개별 상품 처리"""
        product_data = {
            'url': url,
            'processed_at': datetime.now().isoformat(),
            'profiles': {}
        }

        try:
            logger.info(f"상품 페이지 접속: {url}")
            await self.page.goto(url, wait_until='networkidle', timeout=30000)
            await self.wait_random(3, 5)

            # 상품명 추출
            try:
                title_selectors = [
                    'h1', 'h2', '.product-title', '.title', '#productName'
                ]

                product_name = "Unknown Product"
                for selector in title_selectors:
                    try:
                        title_elem = await self.page.wait_for_selector(selector, timeout=3000)
                        if title_elem:
                            product_name = await title_elem.inner_text()
                            break
                    except:
                        continue

                product_data['product_name'] = product_name.strip()
                logger.info(f"상품명: {product_name}")

            except Exception as e:
                logger.error(f"상품명 추출 실패: {e}")

            # 각 프로필별로 처리
            for profile in self.test_profiles:
                try:
                    logger.info(f"프로필 처리 중: {profile}")

                    # 생년월일과 성별 입력
                    input_success = await self.input_birth_date_and_gender(
                        profile['birth_date'],
                        profile['gender']
                    )

                    if not input_success:
                        logger.warning(f"프로필 입력 실패: {profile}")
                        continue

                    # 보험료 계산
                    calc_success = await self.calculate_premium()
                    if not calc_success:
                        logger.warning("보험료 계산 실패")
                        continue

                    # 플랜별 데이터 수집
                    plans_data = await self.collect_plan_premiums()

                    profile_key = f"{profile['birth_date']}_{profile['gender']}"
                    product_data['profiles'][profile_key] = {
                        'profile_info': profile,
                        'plans': plans_data,
                        'collected_at': datetime.now().isoformat()
                    }

                    logger.info(f"프로필 {profile_key} 처리 완료")

                except Exception as e:
                    logger.error(f"프로필 처리 실패 {profile}: {e}")
                    continue

            return product_data

        except Exception as e:
            logger.error(f"상품 처리 실패 {url}: {e}")
            return product_data

    async def run_collection(self):
        """전체 수집 실행"""
        try:
            await self.setup_browser()
            logger.info("KB생명 완전 보험료 수집기 시작")

            for url in self.product_urls:
                try:
                    product_data = await self.process_product(url)
                    self.results['products'].append(product_data)

                    # 각 상품 처리 후 잠시 대기
                    await self.wait_random(5, 8)

                except Exception as e:
                    logger.error(f"상품 URL 처리 실패 {url}: {e}")
                    continue

            # 결과 저장
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"kb_complete_premium_collection_{timestamp}.json"

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)

            logger.info(f"수집 완료. 결과 파일: {filename}")
            print(f"수집된 상품 수: {len(self.results['products'])}")

        except Exception as e:
            logger.error(f"전체 수집 실패: {e}")

        finally:
            if self.browser:
                await self.browser.close()

async def main():
    collector = KBCompletePremiumCollector()
    await collector.run_collection()

if __name__ == "__main__":
    print("KB생명 완전 보험료 수집기 시작")
    print("=" * 60)
    print("기능:")
    print("- 생년월일/성별 입력으로 보험료 계산")
    print("- 4가지 플랜별 모든 특약 활성화")
    print("- 도움말(물음표) 정보 수집")
    print("- 상세 보험료 정보 수집")
    print("=" * 60)

    asyncio.run(main())