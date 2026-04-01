"""
KB생명 ON_PD_YG_01 상세 보험료 스크래퍼

목표:
- 만 19세부터 만 65세까지(포함), 성별 남/여, 4개의 플랜 조합에 대해
  기본보험료 및 각 특약(활성화/비활성화)에 따른 보험료를 수집
- 특약 옆에 있는 '물음표' 툴팁(설명) 텍스트도 함께 수집

사용법(빠른 시작):
  python kb_yg01_detailed_scraper.py

주의사항:
 - 웹사이트 구조가 바뀌면 `SELECTORS` 딕셔너리의 값을 조정해야 합니다.
 - 실행 전 Chrome과 Python 패키지(requirements.txt)를 설치하세요. 디버깅용으로 기본은 headless=False입니다.
"""

import json
import time
import logging
import os
from datetime import datetime
from typing import List, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default selectors (heuristic). If they don't match the page you must update them.
SELECTORS = {
    'age_input': [
        'input[name*="age"]',
        'input[id*="age"]',
        'input[placeholder*="나이"]',
        'input[placeholder*="연령"]',
        'input[type="number"]',
        'input[class*="age"]',
        'input[aria-label*="나이"]',
        'select[name*="age"]',
        'input[role="spinbutton"]'
    ],
    'gender_male': [
        'input[value="M"]',
        'input[id*="male"]',
        'input[name*="gender"][value*="M"]',
        'select[name*="gender"] option[value*="M"]',
        'input[type="radio"][value*="남"]',
        'label:has(input[type="radio"])',
        'select[name*="gender"] option:has-text("남")'
    ],
    'gender_female': [
        'input[value="F"]',
        'input[id*="female"]',
        'input[name*="gender"][value*="F"]',
        'select[name*="gender"] option[value*="F"]',
        'input[type="radio"][value*="여"]',
        'select[name*="gender"] option:has-text("여")'
    ],
    'plan_options': [
        'input[name*="plan"]',
        '.plan-option input[type="radio"]',
        '.product-plan input[type="radio"]',
        'input[type="radio"][name*="prod"]',
        '.plan-list li input[type="radio"]',
        '.product-variant input[type="radio"]',
        '.plan-item',
        'button[data-plan]'
    ],
    'rider_items': [
        '.rider-item',
        '.rider-list li',
        '[class*="rider"] [type="checkbox"]',
        '.optional-list li',
        '.rider-row',
        '.input-check2',
        '.cdAs-slide',
        '.cdAsCon .cdSddList'
    ],
    'rider_checkbox': [
        'input[type="checkbox"][name*="rider"]',
        'input[type="checkbox"][id*="rider"]',
        '[data-rider] input[type="checkbox"]',
        'input[type="checkbox"]',
        'button.cdic_input',
        '.input-check2 button'
    ],
    'rider_label': [
        'label[for]',
        '.rider-label',
    ],
    'rider_tooltip': [
        '.rider-tooltip',
        '.tooltip',
        '[data-tooltip]',
        '[aria-describedby]',
        '[title]',
        '.ico-help',
        '.help-icon',
        '.question',
        '.btn-tooltip'
    ],
    'calc_button': [
        'button#calculateResult',
        'button[class*="calc"]',
        'button[class*="계산"]',
        '.calc-btn',
        'input[type="button"][value*="계산"]',
        'button:has-text("계산")',
        'button:has-text("보험료")',
        'button:has-text("조회")'
    ],
    'premium_result': [
        '.premium-result',
        '.calc-result',
        '.보험료',
        '.premium-amount',
        '[class*="premium"]',
        '[class*="result"]',
        'strong',
        'span',
        'div'
    ]
}

# A small list of common desktop user-agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:116.0) Gecko/20100101 Firefox/116.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edg/115.0.1901.183'
]


class KBYG01DetailedScraper:
    def __init__(self, headless: bool = False, delay: float = 0.8):
        self.headless = headless
        self.delay = delay
        self.driver = None
        self.wait = None
        # Rate limiting / politeness defaults
        self.rate_min = 1.5
        self.rate_max = 3.5
        self.long_pause_every = 10  # after this many requests take a longer break
        self.long_pause_seconds = (30, 90)

    def setup_driver(self, user_agent: str = None):
        opts = Options()
        if self.headless:
            opts.add_argument('--headless')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.add_argument('--window-size=1920,1080')
        # Use provided user-agent or default
        if user_agent:
            opts.add_argument(f'--user-agent={user_agent}')
        else:
            opts.add_argument(f'--user-agent={random.choice(USER_AGENTS)}')

        service = None
        try:
            service = webdriver.chrome.service.Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=opts)
        except Exception as e:
            logger.warning(f"ChromeDriverManager 실패: {e} - 기본 webdriver 시도")
            self.driver = webdriver.Chrome(options=opts)

        self.wait = WebDriverWait(self.driver, 15)
        # 자동화 감지 회피 시도
        try:
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        except Exception:
            pass

    def choose_user_agent(self) -> str:
        return random.choice(USER_AGENTS)

    def reset_session(self, user_agent: str = None):
        """Close and recreate the webdriver with a (possibly) new user-agent."""
        try:
            self.close_driver()
        except Exception:
            pass
        ua = user_agent or self.choose_user_agent()
        self.setup_driver(user_agent=ua)

        # blocking/backoff configuration
        self._block_checks = ['차단', '차단되었습니다', '접근 제한', 'captcha', '로봇', '비정상', '403', '403 Forbidden']
        self._backoff_attempt = 0
        self._max_backoff = 4

    def close_driver(self):
        if self.driver:
            self.driver.quit()

    def is_blocked(self) -> bool:
        """Detect common block/captcha/forbidden patterns in the loaded page."""
        try:
            body = self.driver.find_element(By.TAG_NAME, 'body').text
            if not body:
                return False
            low = body.lower()
            for kw in self._block_checks:
                if kw.lower() in low:
                    return True
        except Exception:
            return False
        return False

    def handle_block(self) -> bool:
        """Handle a detected block: exponential backoff, restart driver, return True if recovered."""
        try:
            self._backoff_attempt += 1
            import random
            # Exponential backoff base seconds
            wait = (2 ** (self._backoff_attempt)) * random.uniform(4, 8)
            # cap wait to a reasonable maximum
            if wait > 900:
                wait = 900
            logger.warning(f"차단 감지: 백오프 시도 {self._backoff_attempt}/{self._max_backoff}. {int(wait)}초 대기 후 재시작합니다.")
            time.sleep(wait)
            # restart driver/session
            try:
                self.close_driver()
            except Exception:
                pass
            try:
                self.setup_driver()
            except Exception as e:
                logger.warning(f"드라이버 재시작 실패: {e}")
                return False
            # if exceeded max attempts, give up
            if self._backoff_attempt >= self._max_backoff:
                logger.error('최대 재시도 횟수 초과 — 수동 개입 필요')
                return False
            return True
        except Exception as e:
            logger.debug(f'handle_block 실패: {e}')
            return False

    def _try_find(self, selectors: List[str]):
        for sel in selectors:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                return el
            except Exception:
                continue
        return None

    def _try_find_all(self, selectors: List[str]):
        for sel in selectors:
            try:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    return els
            except Exception:
                continue
        return []

    def set_age(self, age: int) -> bool:
        # The product page expects a 생년월일 (YYYYMMDD) input with id="birthday".
        # Compute a birthdate from the requested age (use Jan 1 of birth year) and
        # fill the birthday field. Fall back to existing age_input selectors if not found.
        try:
            birthday_el = self.driver.find_element(By.CSS_SELECTOR, '#birthday')
            # compute birth year so that (current_year - birth_year) == age
            # use fixed month/day 01/01 as requested (YYYY0101)
            birth_year = datetime.today().year - int(age)
            birthdate = f"{birth_year:04d}0101"  # YYYY0101
            birthday_el.clear()
            # send keys and blur to trigger input handlers
            birthday_el.send_keys(birthdate)
            try:
                birthday_el.send_keys(Keys.TAB)
            except Exception:
                pass
            time.sleep(self.delay)
            # ensure JS state (some pages use view.current.param.calBirth)
            try:
                self.driver.execute_script("if(window.view && view.current && typeof view.current.param !== 'undefined'){view.current.param.calBirth = arguments[0];}", birthdate)
                # dispatch input/change events on the field
                self.driver.execute_script(
                    "var e = new Event('input', {bubbles:true}); arguments[0].dispatchEvent(e); var c = new Event('change', {bubbles:true}); arguments[0].dispatchEvent(c);",
                    birthday_el,
                )
            except Exception:
                pass
            return True
        except Exception:
            # fallback to the heuristic selectors (some pages may expose age directly)
            el = self._try_find(SELECTORS['age_input'])
            if not el:
                logger.debug('나이 입력 필드 없음')
                return False
            try:
                el.clear()
                el.send_keys(str(age))
                time.sleep(self.delay)
                return True
            except Exception as e:
                logger.debug(f'나이 입력 실패: {e}')
                return False

    def set_gender(self, gender: str) -> bool:
        # gender: 'M' or 'F'
        # On this product page the radio inputs use name="genderCode" with
        # value="1" for 남자 and value="2" for 여자. Try those first.
        try:
            value = '1' if gender == 'M' else '2'
            el = self.driver.find_element(By.CSS_SELECTOR, f'input[name="genderCode"][value="{value}"]')
        except Exception:
            selectors = SELECTORS['gender_male'] if gender == 'M' else SELECTORS['gender_female']
            el = self._try_find(selectors)
        if not el:
            # try select element option
            try:
                sel_el = self._try_find(['select[name*="gender"]'])
                if sel_el:
                    from selenium.webdriver.support.ui import Select
                    s = Select(sel_el)
                    value = 'M' if gender == 'M' else 'F'
                    try:
                        s.select_by_value(value)
                        time.sleep(self.delay)
                        return True
                    except Exception:
                        pass
            except Exception:
                pass
            logger.debug('성별 요소 없음')
            return False
        # Try robust clicking strategies: label ancestor, direct click, sibling span, then JS fallback
        try:
            # ensure visible
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
            except Exception:
                pass
            time.sleep(0.15)

            # 1) If wrapped in a <label>, click the label
            try:
                label = el.find_element(By.XPATH, 'ancestor::label[1]')
                if label:
                    label.click()
                    time.sleep(self.delay)
                    return True
            except Exception:
                pass

            # 2) Try clicking the input itself
            try:
                el.click()
                time.sleep(self.delay)
                return True
            except Exception:
                pass

            # 3) Try clicking following sibling span (common pattern: <input/><span>남자</span>)
            try:
                span = el.find_element(By.XPATH, 'following-sibling::span[1]')
                span.click()
                time.sleep(self.delay)
                return True
            except Exception:
                pass

            # 4) Last resort: set checked via JS and dispatch change event
            try:
                self.driver.execute_script(
                    "arguments[0].checked = true; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    el,
                )
                time.sleep(self.delay)
                return True
            except Exception as e:
                logger.debug(f'성별 설정 실패(JS fallback): {e}')
                return False
        except Exception as e:
            logger.debug(f'성별 설정 실패: {e}')
            return False

    def list_plans(self):
        radios = self._try_find_all(SELECTORS['plan_options'])
        plans = []
        for r in radios:
            try:
                label = r.get_attribute('id') or r.get_attribute('name') or r.get_attribute('value') or r.get_attribute('outerText')
                plans.append({'element': r, 'label': label})
            except Exception:
                continue
        return plans

    def list_riders(self):
        # Robust rider discovery: the site uses both native checkboxes and
        # custom button toggles (e.g., <label class="input-check2"> or button.cdic_input).
        riders = []

        # 1) Try to find explicit checkbox inputs or toggle buttons
        cands = self._try_find_all(SELECTORS['rider_checkbox'])
        if cands:
            for cb in cands:
                try:
                    # derive a human-friendly label: look for nearest text nodes
                    label = ''
                    try:
                        # prefer aria-label or title
                        label = cb.get_attribute('aria-label') or cb.get_attribute('title') or ''
                        if not label:
                            # look for sibling span/text
                            try:
                                sib = cb.find_element(By.XPATH, 'following-sibling::*[1]')
                                label = sib.text.strip()
                            except Exception:
                                pass
                        if not label:
                            # look at parent container text
                            try:
                                p = cb.find_element(By.XPATH, 'ancestor::*[1]')
                                label = p.text.strip()
                            except Exception:
                                pass
                    except Exception:
                        label = ''
                    # try to normalize the label text a bit more
                    norm_label = label.strip() if label and label.strip() else self._normalize_label(cb)
                    riders.append({'element': cb, 'label': norm_label, 'container': None})
                except Exception:
                    continue
            return riders

        # 2) Fallback: find rider item containers and try to locate a toggle inside
        items = self._try_find_all(SELECTORS['rider_items'])
        for item in items:
            try:
                toggle = None
                # try common toggle/button inside item
                try:
                    toggle = item.find_element(By.CSS_SELECTOR, 'button.cdic_input')
                except Exception:
                    try:
                        toggle = item.find_element(By.CSS_SELECTOR, '.input-check2 button')
                    except Exception:
                        try:
                            toggle = item.find_element(By.CSS_SELECTOR, 'input[type="checkbox"]')
                        except Exception:
                            toggle = None

                label = item.text.strip()
                # clean up label by removing newline/extra whitespace
                if label:
                    label = ' '.join(label.split())

                riders.append({'element': toggle, 'label': label, 'container': item})
            except Exception:
                continue
        return riders

    def _normalize_label(self, el) -> str:
        """Try multiple heuristics to find a human-readable label near a checkbox/toggle element."""
        try:
            # 1) aria-label/title
            txt = el.get_attribute('aria-label') or el.get_attribute('title') or ''
            if txt and txt.strip():
                return txt.strip()
        except Exception:
            pass

        try:
            # 2) sibling text nodes (preceding or following)
            try:
                sib = el.find_element(By.XPATH, 'following-sibling::*[1]')
                stext = sib.text.strip()
                if stext:
                    return stext
            except Exception:
                pass
            try:
                sib2 = el.find_element(By.XPATH, 'preceding-sibling::*[1]')
                stext2 = sib2.text.strip()
                if stext2:
                    return stext2
            except Exception:
                pass
        except Exception:
            pass

        try:
            # 3) ancestor container text (li, label, div)
            try:
                anc = el.find_element(By.XPATH, 'ancestor::label[1]')
                if anc and anc.text and anc.text.strip():
                    return anc.text.strip()
            except Exception:
                pass
            try:
                anc2 = el.find_element(By.XPATH, 'ancestor::li[1]')
                if anc2 and anc2.text and anc2.text.strip():
                    return ' '.join(anc2.text.split())
            except Exception:
                pass
            try:
                anc3 = el.find_element(By.XPATH, 'ancestor::div[1]')
                if anc3 and anc3.text and anc3.text.strip():
                    return ' '.join(anc3.text.split())
            except Exception:
                pass
        except Exception:
            pass

        return ''

    def click_calc(self):
        btn = self._try_find(SELECTORS['calc_button'])
        clicked = False
        if not btn:
            # try pressing Enter
            try:
                body = self.driver.find_element(By.TAG_NAME, 'body')
                body.send_keys(Keys.ENTER)
                clicked = True
            except Exception:
                return False
        else:
            try:
                try:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                except Exception:
                    pass
                btn.click()
                clicked = True
            except Exception:
                # fallback: try JS click
                try:
                    self.driver.execute_script('arguments[0].click();', btn)
                    clicked = True
                except Exception:
                    return False

        # After triggering calculation, wait for result region to appear/contain text
        if clicked:
            try:
                # Wait up to a few seconds for the calculation result area or premium element
                def result_ready(d):
                    try:
                        # prefer visible calculation tab content
                        cr = d.find_element(By.CSS_SELECTOR, '#calculationResultContent')
                        if cr and cr.is_displayed():
                            # check for premium inside
                            try:
                                em = cr.find_element(By.CSS_SELECTOR, '.cdSddList dd em')
                                if em and em.text.strip():
                                    return True
                            except Exception:
                                pass
                            # or some top-level reCalculationPremium
                            try:
                                rp = d.find_element(By.CSS_SELECTOR, '#reCalculationPremium')
                                if rp and rp.text.strip():
                                    return True
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # fallback: any .cdSddList dd em visible with text
                    try:
                        els = d.find_elements(By.CSS_SELECTOR, '.cdSddList dd em')
                        for e in els:
                            if e.text.strip():
                                return True
                    except Exception:
                        pass
                    return False

                # Wait longer for the calculation result area or premium element to be populated.
                # Click only once above; then patiently wait (user requested no repeated clicks).
                try:
                    WebDriverWait(self.driver, 18).until(result_ready)
                except Exception:
                    # if timeout, continue to read_premium fallback logic
                    pass
                # after waiting, check for block
                if self.is_blocked():
                    logger.warning('계산 후 차단 감지')
                    recovered = self.handle_block()
                    if not recovered:
                        return False
                    # caller may need to retry calc after recovery
            except Exception:
                # if waiting failed, continue anyway; read_premium has its own fallbacks
                pass
            # small delay to allow UI settle
            time.sleep(self.delay)
            return True
        return False

    def read_premium(self) -> str:
        import re

        # 1) If calculation result container is visible, prefer values inside it
        try:
            cr = self.driver.find_element(By.CSS_SELECTOR, '#calculationResultContent')
            if cr and cr.is_displayed():
                # try structured selector first
                try:
                    em = cr.find_element(By.CSS_SELECTOR, '.cdSddList dd em')
                    if em and em.text.strip():
                        return em.text.strip()
                except Exception:
                    pass
                # try dt/dd pairing (dt contains '보험료')
                try:
                    dd_em = cr.find_element(By.XPATH, ".//dt[contains(normalize-space(.), '보험료')]/following-sibling::dd[1]//em")
                    if dd_em and dd_em.text.strip():
                        return dd_em.text.strip()
                except Exception:
                    pass
        except Exception:
            pass

        # 2) Search the whole page for nearby '보험료' labels and pick following em
        try:
            els = self.driver.find_elements(By.XPATH, "//dt[contains(normalize-space(.), '보험료')]/following-sibling::dd[1]//em")
            for e in els:
                try:
                    txt = e.text.strip()
                    if txt:
                        # validate candidate: prefer currency-like strings or 4+ digits
                        if '원' in txt:
                            return txt
                        digits = re.sub(r'[^0-9]', '', txt)
                        if len(digits) >= 4:
                            return txt
                        # otherwise ignore small numeric fragments
                except Exception:
                    continue
        except Exception:
            pass

        # 3) Try commonly used selectors (older fallback)
        for sel in ['#reCalculationPremium', '#rs-sticky #reCalculationPremium', '.cdSddList dd em', '#productMappingArea .cdSddList dd em']:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                txt = el.text.strip()
                if txt:
                    # filter out tiny numeric fragments
                    digits = re.sub(r'[^0-9]', '', txt)
                    if '원' in txt or len(digits) >= 4:
                        return txt
            except Exception:
                continue

        # 4) Fallback: generic selector list
        el = self._try_find(SELECTORS['premium_result'])
        if el:
            try:
                txt = el.text.strip()
                if txt:
                    # avoid obvious phone number extraction like '080' by checking context
                    if re.match(r'^0?80$', txt) or '고객센터' in txt:
                        pass
                    else:
                        # filter out very short numeric fragments
                        digits = re.sub(r'[^0-9]', '', txt)
                        if '원' in txt or len(digits) >= 4:
                            return txt
            except Exception:
                pass

        # 5) Last resort: search page text for currency-like pattern but avoid phone numbers
        try:
            txt = self.driver.find_element(By.TAG_NAME, 'body').text
            # first look for patterns with '원'
            m = re.search(r"([0-9,]+원)", txt)
            if m:
                candidate = m.group(1)
                # avoid matching phone-like '080'
                if '080' in candidate and '고객센터' in txt:
                    # ignore and keep searching below
                    pass
                else:
                    return candidate
            # then any 4+ digit number (to avoid small '080')
            m = re.search(r"[0-9]{4,}(?:[,0-9]*)", txt)
            if m:
                return m.group(0)
        except Exception:
            return ''

        return ''

    def read_tooltip(self, element) -> str:
        # Try title attribute
        try:
            t = element.get_attribute('title')
            if t:
                return t.strip()
        except Exception:
            pass

        # Hover and look for tooltip elements
        try:
            ActionChains(self.driver).move_to_element(element).perform()
            time.sleep(0.6)
            # look for common tooltip selectors
            for sel in SELECTORS['rider_tooltip']:
                try:
                    tooltip = self.driver.find_element(By.CSS_SELECTOR, sel)
                    text = tooltip.text.strip()
                    if text:
                        return text
                except Exception:
                    continue
        except Exception:
            pass

        # aria-describedby
        try:
            desc = element.get_attribute('aria-describedby')
            if desc:
                try:
                    el = self.driver.find_element(By.ID, desc)
                    return el.text.strip()
                except Exception:
                    pass
        except Exception:
            pass

        return ''

    def scrape(self, url: str) -> Dict[str, Any]:
        self.setup_driver()
        results = []
        try:
            self.driver.get(url)
            time.sleep(2)
            # detect initial block page
            if self.is_blocked():
                logger.warning('페이지 로드 후 차단 감지')
                recovered = self.handle_block()
                if not recovered:
                    logger.error('차단으로 인한 복구 실패 — 스크래핑 중단')
                    return {'filename': None, 'count': 0}
                # after recovery, reload
                self.driver.get(url)
                time.sleep(2)

            # detect plans and riders
            plans = self.list_plans()
            if not plans:
                logger.info('플랜 라디오를 못 찾았습니다. 전체 페이지에서 radio input 재수집 시도')
                plans = self._try_find_all(['input[type="radio"]'])

            riders = self.list_riders()

            # Determine plan elements: normalize to a list of elements
            plan_elements = []
            if plans and isinstance(plans[0], dict) and 'element' in plans[0]:
                plan_elements = [p['element'] for p in plans]
            else:
                plan_elements = plans

            # If no explicit plans found, we'll try to treat product variants as 4 repeated selections later

            for age in range(20, 65):
                for gender in ('M', 'F'):
                    # set age and gender
                    self.set_age(age)
                    self.set_gender(gender)

                    # iterate plans
                    if plan_elements:
                        plan_iter = plan_elements
                    else:
                        plan_iter = [None] * 4  # placeholder - attempt 4 times

                    for p_index, plan_el in enumerate(plan_iter, 1):
                        # select plan if element exists
                        plan_label = f'plan_{p_index}'
                        try:
                            if plan_el:
                                try:
                                    plan_el.click()
                                    time.sleep(self.delay)
                                    # attempt read label near element
                                    plan_label = plan_el.get_attribute('value') or plan_el.get_attribute('id') or plan_el.get_attribute('name') or plan_label
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # Baseline: ensure all riders are unchecked first
                        for r in riders:
                            try:
                                cb = r.get('element') or None
                                if cb:
                                    # if checked, uncheck
                                    try:
                                        if cb.is_selected():
                                            cb.click(); time.sleep(0.2)
                                    except Exception:
                                        pass
                            except Exception:
                                continue

                        # Read base premium (no riders)
                        self.click_calc()
                        base_premium = self.read_premium()

                        rider_details = {}

                        # For each rider: activate and read premium + tooltip
                        for r in riders:
                            label = r.get('label') or ''
                            cb = r.get('element')
                            if not cb:
                                # try find checkbox under container
                                cb = r.get('container') and r['container'].find_element(By.CSS_SELECTOR, 'input[type="checkbox"]') if r.get('container') else None

                            if not cb:
                                # can't toggle this rider
                                rider_details[label] = {'activated': False, 'premium': None, 'tooltip': ''}
                                continue

                            try:
                                # click to activate
                                cb.click()
                                time.sleep(self.delay)

                                # trigger calc
                                self.click_calc()
                                time.sleep(self.delay)

                                premium = self.read_premium()

                                # find tooltip: try element near checkbox (sibling .? or label with ?)
                                tooltip = self.read_tooltip(cb)

                                rider_details[label] = {'activated': True, 'premium': premium, 'tooltip': tooltip}

                                # uncheck to restore
                                try:
                                    cb.click(); time.sleep(0.2)
                                except Exception:
                                    pass
                            except Exception as e:
                                logger.debug(f'특약 처리 실패 {label}: {e}')
                                rider_details[label] = {'activated': False, 'premium': None, 'tooltip': ''}

                        entry = {
                            'age': age,
                            'gender': 'M' if gender == 'M' else 'F',
                            'plan': plan_label,
                            'base_premium': base_premium,
                            'riders': rider_details,
                            'scraped_at': datetime.now().isoformat()
                        }

                        results.append(entry)

                        # polite pause to avoid triggering automated defenses
                        try:
                            import random
                            time.sleep(random.uniform(self.rate_min, self.rate_max))
                            # periodic longer pause
                            if len(results) % self.long_pause_every == 0:
                                time.sleep(random.uniform(self.long_pause_seconds[0], self.long_pause_seconds[1]))
                        except Exception:
                            pass

            # save results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'kb_yg01_premiums_{timestamp}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump({'url': url, 'results': results}, f, ensure_ascii=False, indent=2)

            logger.info(f'저장 완료: {filename} (엔트리 수: {len(results)})')
            return {'filename': filename, 'count': len(results)}

        finally:
            self.close_driver()


def main():
    import argparse

    parser = argparse.ArgumentParser(description='KB ON_PD_YG_01 상세 보험료 스크래퍼')
    parser.add_argument('--url', type=str, default='https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_YG_01&productType=5', help='수집할 상품 URL')
    parser.add_argument('--headless', action='store_true', help='헤드리스 모드로 실행')
    parser.add_argument('--smoke', action='store_true', help='스모크 테스트 모드: 연령/플랜 샘플만 수집 (빠른 확인용)')
    parser.add_argument('--out', type=str, default=None, help='출력 파일명 (JSON)')
    args = parser.parse_args()

    # Adjust scraper behavior for smoke test
    if args.smoke:
        # create a lightweight wrapper around scrape that limits iterations
        class SmokeScraper(KBYG01DetailedScraper):
            def scrape(self, url: str):
                self.setup_driver()
                results = []
                try:
                    self.driver.get(url)
                    time.sleep(2)

                    plans = self.list_plans()
                    riders = self.list_riders()

                    # prepare debug screenshot folder
                    out_dir = os.path.join(os.getcwd(), 'outputs')
                    debug_dir = os.path.join(out_dir, 'debug')
                    try:
                        os.makedirs(debug_dir, exist_ok=True)
                    except Exception:
                        pass

                    # sample ages and genders (20 and 64 as requested)
                    sample_ages = [20, 64]
                    sample_genders = ('M', 'F')

                    plan_elements = [p['element'] for p in plans] if plans and isinstance(plans[0], dict) and 'element' in plans[0] else (plans or [None])

                    for age in sample_ages:
                        for gender in sample_genders:
                            # rotate session & UA per sample to reduce blocking
                                    try:
                                        self.reset_session()
                                    except Exception:
                                        pass
                                    try:
                                        self.driver.get(url)
                                        time.sleep(2)
                                    except Exception:
                                        pass

                                    # After recreating the session/driver we MUST re-discover plans and riders
                                    try:
                                        plans = self.list_plans()
                                        riders = self.list_riders()
                                        plan_elements = [p['element'] for p in plans] if plans and isinstance(plans[0], dict) and 'element' in plans[0] else (plans or [None])
                                    except Exception:
                                        plans = []
                                        riders = []
                                        plan_elements = [None]

                                    age_ok = self.set_age(age)
                                    gender_ok = self.set_gender(gender)
                                    logger.info(f"샘플 케이스: age={age} 설정됨={age_ok}, gender={gender} 설정됨={gender_ok}")
                                    # save page HTML when age or gender setting failed to help debugging
                                    if not age_ok or not gender_ok:
                                        try:
                                            html_name = f"yg01_age{age}_gender{gender}.html"
                                            html_path = os.path.join(debug_dir, html_name)
                                            with open(html_path, 'w', encoding='utf-8') as hf:
                                                hf.write(self.driver.page_source)
                                            logger.info(f"디버그 HTML 저장: {html_path}")
                                        except Exception as e:
                                            logger.debug(f"디버그 HTML 저장 실패: {e}")

                                    for p_index, plan_el in enumerate(plan_elements, 1):
                                        plan_label = f'plan_{p_index}'
                                        try:
                                            if plan_el:
                                                plan_el.click(); time.sleep(self.delay)
                                                plan_label = plan_el.get_attribute('value') or plan_el.get_attribute('id') or plan_el.get_attribute('name') or plan_label
                                        except Exception:
                                            pass

                                        # baseline
                                        for r in riders:
                                            try:
                                                cb = r.get('element')
                                                if cb and cb.is_selected():
                                                    cb.click(); time.sleep(0.1)
                                            except Exception:
                                                continue

                                        self.click_calc(); time.sleep(self.delay)
                                        base_premium = self.read_premium()

                                        # save a debug screenshot for this sample case
                                        try:
                                            shot_name = f"yg01_age{age}_gender{gender}_plan{p_index}.png"
                                            shot_path = os.path.join(debug_dir, shot_name)
                                            self.driver.save_screenshot(shot_path)
                                            logger.info(f"디버그 스크린샷 저장: {shot_path}")
                                        except Exception as e:
                                            logger.debug(f"스크린샷 저장 실패: {e}")

                                        rider_details = {}
                                        # test activating up to 2 riders for speed
                                        for r in riders[:2]:
                                            label = r.get('label') or ''
                                            cb = r.get('element')
                                            if not cb:
                                                rider_details[label] = {'activated': False, 'premium': None, 'tooltip': ''}
                                                continue
                                            try:
                                                cb.click(); time.sleep(self.delay)
                                                self.click_calc(); time.sleep(self.delay)
                                                premium = self.read_premium()
                                                tooltip = self.read_tooltip(cb)
                                                rider_details[label] = {'activated': True, 'premium': premium, 'tooltip': tooltip}
                                                # uncheck
                                                cb.click(); time.sleep(0.1)
                                            except Exception as e:
                                                rider_details[label] = {'activated': False, 'premium': None, 'tooltip': ''}

                    entry = {'age': age, 'gender': gender, 'plan': plan_label, 'base_premium': base_premium, 'riders': rider_details, 'scraped_at': datetime.now().isoformat()}
                    results.append(entry)

                    # write to file
                    fname = args.out or f'kb_yg01_premiums_smoke_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                    with open(fname, 'w', encoding='utf-8') as f:
                        json.dump({'url': url, 'results': results}, f, ensure_ascii=False, indent=2)
                    logger.info(f'SMOKE 저장 완료: {fname} (엔트리 수: {len(results)})')
                    return {'filename': fname, 'count': len(results)}
                finally:
                    self.close_driver()

        scraper = SmokeScraper(headless=args.headless)
        print('스모크 테스트 모드로 실행합니다...')
        res = scraper.scrape(args.url)
        print('스모크 완료:', res)
        return

    # normal full run
    scraper = KBYG01DetailedScraper(headless=args.headless)
    try:
        print('풀 스크래핑을 시작합니다. (주의: 오래 걸림)')
        result = scraper.scrape(args.url)
        print('완료:', result)
    except KeyboardInterrupt:
        print('사용자 중단')


if __name__ == '__main__':
    main()
