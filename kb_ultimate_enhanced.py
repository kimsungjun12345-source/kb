"""
KB생명 보험료 계산기 동적 스크래퍼
나이별, 성별별 보험료 및 특약 정보 수집

사용법:
    python kb_ultimate_enhanced.py --age-start 20 --age-end 60 --delay 2
"""

import asyncio
import argparse
import json
import time
import re
from pathlib import Path
from playwright.async_api import async_playwright

URL = "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5"

GENDERS = [
    {"value": "남자", "name": "남"},
    {"value": "여자", "name": "여"},
]

def get_filename(age, gender_name):
    return f"kb_insurance_{age}세_{gender_name}.json"

async def setup_browser(p):
    """브라우저 시작 + webdriver 제거 + 첫 로드"""
    browser = await p.chromium.launch(headless=False, channel="chrome")
    context = await browser.new_context(
        viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # navigator.webdriver 제거 - 봇 감지 우회
    await context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )

    page = await context.new_page()

    print("[*] KB생명 페이지 로드 중...")
    await page.goto(URL, timeout=60000, wait_until='load')
    await asyncio.sleep(5)  # 페이지 완전 로드 대기

    # 페이지가 정상 로드됐는지 확인
    content = await page.content()
    if len(content) < 10000:
        print("[!] 페이지 로드 실패 - 차단됐을 수 있습니다.")
        await browser.close()
        return None, None, None

    print("[+] 페이지 로드 완료")
    return browser, context, page

async def extract_insurance_data(page, age, gender):
    """특정 나이/성별에 대한 보험료 정보 추출"""
    print(f"[*] {age}세 {gender['name']} 데이터 추출 중...")

    try:
        # 보험료 계산 섹션으로 스크롤
        await page.evaluate("window.scrollTo(0, document.querySelector('.premium-calc, #calc, [class*=\"calc\"]')?.offsetTop || 1000)")
        await asyncio.sleep(2)

        # 생년월일 설정 (나이 기반)
        birth_year = 2026 - age
        birth_date = f"{birth_year}-01-01"

        # 생년월일 입력 필드 찾기 및 설정
        birth_selectors = [
            'input[name*="birth"]', 'input[id*="birth"]', 'input[class*="birth"]',
            '#insStartDtPicker', '.birth-input', '[placeholder*="생년월일"]'
        ]

        birth_set = False
        for selector in birth_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.fill(birth_date)
                    print(f"[+] 생년월일 설정: {birth_date} (selector: {selector})")
                    birth_set = True
                    break
            except:
                continue

        # 나이 직접 입력
        age_selectors = ['#age', 'input[name="age"]', '[id*="age"]', '.age-input']
        for selector in age_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.fill(str(age))
                    print(f"[+] 나이 설정: {age}")
                    break
            except:
                continue

        # 성별 설정
        gender_set = False
        gender_selectors = [
            f'input[value="{gender["value"]}"]',
            f'#{gender["name"]}',
            f'input[name*="sex"][value*="{gender["name"]}"]',
            f'input[name*="gender"]'
        ]

        for selector in gender_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    print(f"[+] 성별 설정: {gender['name']}")
                    gender_set = True
                    break
            except:
                continue

        # 성별을 라디오 버튼이나 드롭다운으로 설정
        if not gender_set:
            try:
                # 성별 라디오 버튼 찾기
                if gender["name"] == "남":
                    selectors = ['input[value="남자"]', 'input[value="M"]', 'input[value="male"]', '#sexM']
                else:
                    selectors = ['input[value="여자"]', 'input[value="F"]', 'input[value="female"]', '#sexL']

                for sel in selectors:
                    try:
                        element = await page.query_selector(sel)
                        if element:
                            await element.click()
                            print(f"[+] 성별 라디오 버튼 설정: {gender['name']}")
                            gender_set = True
                            break
                    except:
                        continue
            except:
                pass

        await asyncio.sleep(2)

        # 보험료 계산 버튼 클릭
        calc_selectors = [
            'button:has-text("계산")', 'button:has-text("보험료")',
            'button:has-text("산출")', '.btn-calc', '#calc-btn',
            'button.btn_type04', '[onclick*="calc"]'
        ]

        calc_clicked = False
        for selector in calc_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.click()
                    print("[+] 계산 버튼 클릭")
                    calc_clicked = True
                    await asyncio.sleep(3)  # 계산 완료 대기
                    break
            except:
                continue

        # 결과 데이터 추출
        await asyncio.sleep(2)

        # 보험료 정보 추출
        premium_data = await page.evaluate('''
            () => {
                const data = {};

                // 보험료 텍스트 추출
                const premiumSelectors = [
                    '[class*="premium"]', '[class*="price"]', '[class*="amount"]',
                    '.monthly-premium', '.premium-amount', '[id*="premium"]'
                ];

                premiumSelectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        const text = el.innerText || el.textContent;
                        if (text && text.match(/[0-9,]+원/)) {
                            data.premium_texts = data.premium_texts || [];
                            data.premium_texts.push(text.trim());
                        }
                    });
                });

                // 특약 정보 추출
                const specialSelectors = [
                    '[class*="special"]', '[class*="option"]', '[class*="add"]',
                    '.special-contract', '.additional', '[id*="special"]'
                ];

                specialSelectors.forEach(selector => {
                    const elements = document.querySelectorAll(selector);
                    elements.forEach(el => {
                        const text = el.innerText || el.textContent;
                        if (text && text.length > 5) {
                            data.special_contracts = data.special_contracts || [];
                            data.special_contracts.push(text.trim());
                        }
                    });
                });

                // 테이블에서 보험료 정보 추출
                const tables = document.querySelectorAll('table');
                data.tables = [];
                tables.forEach(table => {
                    const rows = [];
                    const tableRows = table.querySelectorAll('tr');
                    tableRows.forEach(row => {
                        const cells = [];
                        const tableCells = row.querySelectorAll('td, th');
                        tableCells.forEach(cell => {
                            cells.push(cell.innerText?.trim() || '');
                        });
                        if (cells.some(cell => cell.length > 0)) {
                            rows.push(cells);
                        }
                    });
                    if (rows.length > 0) {
                        data.tables.push(rows);
                    }
                });

                return data;
            }
        ''')

        # 현재 페이지의 모든 폼 데이터 수집
        form_data = await page.evaluate('''
            () => {
                const forms = document.querySelectorAll('form, [class*="form"]');
                const formData = {};

                forms.forEach((form, index) => {
                    const inputs = form.querySelectorAll('input, select, textarea');
                    const currentForm = {};

                    inputs.forEach(input => {
                        if (input.name || input.id) {
                            const key = input.name || input.id;
                            let value = input.value;

                            if (input.type === 'checkbox' || input.type === 'radio') {
                                value = input.checked ? input.value : '';
                            }

                            if (value) {
                                currentForm[key] = value;
                            }
                        }
                    });

                    if (Object.keys(currentForm).length > 0) {
                        formData[`form_${index}`] = currentForm;
                    }
                });

                return formData;
            }
        ''')

        return {
            'age': age,
            'gender': gender['name'],
            'premium_data': premium_data,
            'form_data': form_data,
            'extraction_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }

    except Exception as e:
        print(f"[!] 데이터 추출 중 오류: {e}")
        return {
            'age': age,
            'gender': gender['name'],
            'error': str(e),
            'extraction_timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
        }

async def scrape_age_gender_combination(page, age, gender, output_dir, delay):
    """단일 나이/성별 조합 스크래핑"""
    filename = get_filename(age, gender["name"])
    filepath = output_dir / filename

    # 이미 받은 파일 스킵
    if filepath.exists() and filepath.stat().st_size > 0:
        return "skip"

    try:
        # 페이지 새로고침으로 초기화
        await page.reload(wait_until='load')
        await asyncio.sleep(2)

        # 데이터 추출
        data = await extract_insurance_data(page, age, gender)

        # JSON으로 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        await asyncio.sleep(delay)
        return "ok"

    except Exception as e:
        return f"error: {str(e)[:80]}"

async def main():
    parser = argparse.ArgumentParser(description="KB생명 보험료 계산기 스크래퍼")
    parser.add_argument("--age-start", type=int, default=20, help="시작 나이 (기본: 20)")
    parser.add_argument("--age-end", type=int, default=60, help="끝 나이 (기본: 60)")
    parser.add_argument("--delay", type=float, default=2, help="요청 간 대기 초 (기본: 2)")
    parser.add_argument("--output", type=str, default="data/kb_insurance", help="저장 폴더")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    success, skipped, errors = 0, 0, 0

    async with async_playwright() as p:
        browser, context, page = await setup_browser(p)
        if not page:
            return

        total_combos = len(GENDERS) * (args.age_end - args.age_start + 1)
        done = 0

        try:
            for gender in GENDERS:
                for age in range(args.age_start, args.age_end + 1):
                    done += 1
                    label = f"{age}세 {gender['name']}"
                    print(f"[{done}/{total_combos}] {label}", end=" → ")

                    try:
                        result = await scrape_age_gender_combination(page, age, gender, output_dir, args.delay)
                    except Exception as e:
                        result = f"error: {str(e)[:80]}"

                    if result == "ok":
                        success += 1
                        print("데이터 수집 완료")
                    elif result == "skip":
                        skipped += 1
                        print("이미 있음 (스킵)")
                    else:
                        errors += 1
                        print(f"{result}")

        finally:
            elapsed = time.time() - start_time
            print(f"\n{'='*50}")
            print(f"완료! 소요시간: {elapsed:.0f}초")
            print(f"  성공: {success}건")
            print(f"  스킵: {skipped}건")
            print(f"  에러: {errors}건")
            print(f"{'='*50}")

            try:
                await browser.close()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(main())
