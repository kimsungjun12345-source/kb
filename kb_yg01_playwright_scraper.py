"""
Playwright 기반 KB ON_PD_YG_01 상세 보험료 스크래퍼

기능:

사용법 (PowerShell):
    python ./kb_yg01_playwright_scraper.py --smoke
    python ./kb_yg01_playwright_scraper.py        # 전체 실행(오래 걸림)

사전 준비:
  pip install -r requirements.txt
  python -m playwright install chromium

"""

import asyncio
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Any

try:
    from playwright.async_api import async_playwright, Page
except ModuleNotFoundError:
    print('\nERROR: Playwright is not installed in this Python environment.')
    print('Install dependencies and browsers with the following commands:')
    print('  pip install -r requirements.txt')
    print('  python -m playwright install chromium')
    import sys
    sys.exit(1)


SELECTORS = {
    'age_input': [
        'input[name*="age"]',
        'input[id*="age"]',
        'input[placeholder*="나이"]',
        'input[type="number"]'
    ],
    'gender_male': [
        'input[value="M"]',
        'input[id*="male"]',
        'input[name*="gender"][value*="M"]',
        'select[name*="gender"] option[value*="M"]'
    ],
    'gender_female': [
        'input[value="F"]',
        'input[id*="female"]',
        'input[name*="gender"][value*="F"]',
        'select[name*="gender"] option[value*="F"]'
    ],
    'plan_options': [
        'input[name*="plan"]',
        '.plan-option input[type="radio"]',
        '.product-plan input[type="radio"]',
        'input[type="radio"]'
    ],
    'rider_checkbox': [
        'input[type="checkbox"][name*="rider"]',
        'input[type="checkbox"][id*="rider"]',
        '[data-rider] input[type="checkbox"]',
        'input[type="checkbox"]'
    ],
    'rider_container': [
        '.rider-item',
        '.rider-list li',
        '[class*="rider"]'
    ],
    'rider_tooltip': [
        '.rider-tooltip',
        '.tooltip',
        '[data-tooltip]',
        '[aria-describedby]',
        '[title]'
    ],
    'calc_button': [
        'button[class*="calc"]',
        '.calc-btn',
        'button[type="submit"]',
        'input[type="button"][value*="계산"]'
    ],
    'premium_result': [
        '.premium-result',
        '.calc-result',
        '.보험료',
        '.premium-amount',
        '[class*="premium"]',
        '[class*="result"]'
    ]
}


class PlaywrightYG01Scraper:
    def __init__(self, headless: bool = False, delay: float = 0.6):
        self.headless = headless
        self.delay = delay

    async def _find_first(self, page: Page, selectors: List[str]):
        for sel in selectors:
            try:
                loc = page.locator(sel)
                count = await loc.count()
                if count > 0:
                    return loc
            except Exception:
                continue
        return None

    async def list_plans(self, page: Page):
        loc = await self._find_first(page, SELECTORS['plan_options'])
        if not loc:
            return []
        plans = []
        count = await loc.count()
        for i in range(count):
            el = loc.nth(i)
            try:
                label = await el.get_attribute('value') or await el.get_attribute('id') or await el.get_attribute('name') or f'plan_{i+1}'
            except Exception:
                label = f'plan_{i+1}'
            plans.append({'locator': el, 'label': label})
        return plans

    async def list_riders(self, page: Page):
        # prefer explicit checkbox selectors
        loc = await self._find_first(page, SELECTORS['rider_checkbox'])
        riders = []
        if loc:
            count = await loc.count()
            for i in range(count):
                el = loc.nth(i)
                # try to get nearby label text
                label = ''
                try:
                    parent = el.locator('xpath=..')
                    label = (await parent.inner_text()).strip()
                except Exception:
                    try:
                        label = (await el.get_attribute('aria-label')) or (await el.get_attribute('title')) or ''
                    except Exception:
                        label = ''
                riders.append({'locator': el, 'label': label})
            return riders

        # fallback: find rider containers and extract checkbox inside
        cont = await self._find_first(page, SELECTORS['rider_container'])
        if not cont:
            return []
        cnt = await cont.count()
        for i in range(cnt):
            item = cont.nth(i)
            try:
                cb = item.locator('input[type="checkbox"]')
                ccount = await cb.count()
                cb_el = cb.nth(0) if ccount>0 else None
                label = (await item.inner_text()).strip()
                riders.append({'locator': cb_el, 'label': label})
            except Exception:
                continue
        return riders

    async def set_age(self, page: Page, age: int) -> bool:
        loc = await self._find_first(page, SELECTORS['age_input'])
        if not loc:
            return False
        try:
            el = loc.nth(0)
            await el.fill(str(age))
            await page.wait_for_timeout(int(self.delay*1000))
            return True
        except Exception:
            return False

    async def set_gender(self, page: Page, gender: str) -> bool:
        selectors = SELECTORS['gender_male'] if gender=='M' else SELECTORS['gender_female']
        loc = await self._find_first(page, selectors)
        if loc:
            try:
                el = loc.nth(0)
                await el.click()
                await page.wait_for_timeout(int(self.delay*1000))
                return True
            except Exception:
                return False
        # try select element
        sel = await self._find_first(page, ['select[name*="gender"]'])
        if sel:
            try:
                val = 'M' if gender=='M' else 'F'
                await sel.select_option(value=val)
                await page.wait_for_timeout(int(self.delay*1000))
                return True
            except Exception:
                return False
        return False

    async def click_calc(self, page: Page) -> bool:
        loc = await self._find_first(page, SELECTORS['calc_button'])
        if loc:
            try:
                await loc.nth(0).click()
                await page.wait_for_timeout(int(self.delay*1000))
                return True
            except Exception:
                return False
        # fallback: press Enter
        try:
            await page.keyboard.press('Enter')
            await page.wait_for_timeout(int(self.delay*1000))
            return True
        except Exception:
            return False

    async def read_premium(self, page: Page) -> str:
        loc = await self._find_first(page, SELECTORS['premium_result'])
        if loc:
            try:
                txt = (await loc.nth(0).inner_text()).strip()
                return txt
            except Exception:
                pass
        # fallback: search body text for Korean currency pattern
        try:
            body = await page.locator('body').inner_text()
            import re
            m = re.search(r'[0-9,]+원', body)
            return m.group(0) if m else ''
        except Exception:
            return ''

    async def read_tooltip(self, page: Page, locator) -> str:
        if not locator:
            return ''
        try:
            t = await locator.get_attribute('title')
            if t:
                return t.strip()
        except Exception:
            pass
        # hover and look for visible tooltip elements
        try:
            await locator.hover()
            await page.wait_for_timeout(500)
            for sel in SELECTORS['rider_tooltip']:
                try:
                    tip = page.locator(sel)
                    cnt = await tip.count()
                    for i in range(cnt):
                        txt = (await tip.nth(i).inner_text()).strip()
                        if txt:
                            return txt
                except Exception:
                    continue
        except Exception:
            pass
        # aria-describedby
        try:
            desc = await locator.get_attribute('aria-describedby')
            if desc:
                try:
                    el = page.locator(f'#{desc}')
                    return (await el.inner_text()).strip()
                except Exception:
                    pass
        except Exception:
            pass
        return ''

    async def scrape(self, url: str, smoke: bool = False, out: str | None = None) -> Dict[str, Any]:
        results = []
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=self.headless, args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width':1920,'height':1080})
        page = await context.new_page()

        try:
            await page.goto(url, wait_until='networkidle')
            await page.wait_for_timeout(1000)

            plans = await self.list_plans(page)
            riders = await self.list_riders(page)

            # if no plans detected, provide placeholders for 4 plans
            if not plans:
                plan_slots = [None]*4
            else:
                plan_slots = plans[:4]

            ages = [19,65] if smoke else list(range(19,66))
            genders = ['M','F']

            for age in ages:
                for gender in genders:
                    await self.set_age(page, age)
                    await self.set_gender(page, gender)

                    for p_index, plan in enumerate(plan_slots, 1):
                        plan_label = f'plan_{p_index}'
                        if plan:
                            try:
                                await plan['locator'].click()
                                await page.wait_for_timeout(int(self.delay*1000))
                                plan_label = plan.get('label') or plan_label
                            except Exception:
                                pass

                        # ensure all riders are unchecked first
                        for r in riders:
                            try:
                                loc = r['locator']
                                if loc:
                                    checked = await loc.is_checked() if hasattr(loc,'is_checked') else False
                                    if checked:
                                        await loc.click(); await page.wait_for_timeout(200)
                            except Exception:
                                continue

                        await self.click_calc(page)
                        base_premium = await self.read_premium(page)

                        rider_details = {}
                        # limit riders in smoke
                        rider_iter = riders if not smoke else riders[:2]
                        for r in rider_iter:
                            label = r.get('label') or ''
                            loc = r.get('locator')
                            if not loc:
                                rider_details[label] = {'activated': False, 'premium': None, 'tooltip': ''}
                                continue
                            try:
                                await loc.click()
                                await page.wait_for_timeout(int(self.delay*1000))
                                await self.click_calc(page)
                                await page.wait_for_timeout(int(self.delay*1000))
                                premium = await self.read_premium(page)
                                tooltip = await self.read_tooltip(page, loc)
                                rider_details[label] = {'activated': True, 'premium': premium, 'tooltip': tooltip}
                                # uncheck
                                await loc.click(); await page.wait_for_timeout(200)
                            except Exception:
                                rider_details[label] = {'activated': False, 'premium': None, 'tooltip': ''}

                        entry = {
                            'age': age,
                            'gender': gender,
                            'plan': plan_label,
                            'base_premium': base_premium,
                            'riders': rider_details,
                            'scraped_at': datetime.now().isoformat()
                        }
                        results.append(entry)

            # write JSON into outputs/ by default
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            default_name = f'kb_yg01_playwright_{"smoke_" if smoke else "full_"}{timestamp}.json'
            if out:
                fname = out
            else:
                out_dir = os.path.join(os.getcwd(), 'outputs')
                try:
                    os.makedirs(out_dir, exist_ok=True)
                except Exception:
                    pass
                fname = os.path.join(out_dir, default_name)

            with open(fname, 'w', encoding='utf-8') as f:
                json.dump({'url': url, 'results': results}, f, ensure_ascii=False, indent=2)

            return {'filename': fname, 'count': len(results)}

        finally:
            await context.close()
            await browser.close()
            await playwright.stop()


async def _main_async(args):
    scraper = PlaywrightYG01Scraper(headless=args.headless)
    res = await scraper.scrape(args.url, smoke=args.smoke, out=args.out)
    print('완료:', res)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Playwright KB ON_PD_YG_01 상세 스크래퍼')
    parser.add_argument('--url', type=str, default='https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5')
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--out', type=str, default=None)
    args = parser.parse_args()

    asyncio.run(_main_async(args))


if __name__ == '__main__':
    main()
