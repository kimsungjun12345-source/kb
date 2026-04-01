/**
 * KB Life e-건강보험 초안전 스크래퍼 v2.0
 * - 강화된 보안 우회 기능
 * - 인간 행동 패턴 모방
 * - 랜덤 지연 및 배치 크기 조절
 */

(function () {
  'use strict';

  // 더 보수적인 설정
  const MIN_BATCH_SIZE = 1;
  const MAX_BATCH_SIZE = 2;
  const MIN_DELAY_MS = 3000;  // 3초
  const MAX_DELAY_MS = 8000;  // 8초
  const PLAN_NAMES = ['든든', '실속', '뇌심', '입원'];

  // 선택형 특약 이름 매핑
  const SELECTABLE_NAMES = {
    '837667104': '중환자실입원(1일이상 60일한도)(갱)(해약환급금 미지급형)',
    '837668104': '응급실내원(응급)(갱)(해약환급금 미지급형)',
    '837606104': '간암·폐암·췌장암진단(갱)(해약환급금 미지급형)',
    '837611104': '암(기타피부암 및 갑상선암 제외) 주요치료(갱)(해약환급금 미지급형)',
    '837612104': '기타피부암 및 갑상선암 주요치료(갱)(해약환급금 미지급형)',
    '831667104': '(간편355)중환자실입원(1일이상 60일한도)(갱)(해약환급금 미지급형)',
    '831668104': '(간편355)응급실내원(응급)(갱)(해약환급금 미지급형)',
    '831606104': '(간편355)간암·폐암·췌장암진단(갱)(해약환급금 미지급형)',
    '831611104': '(간편355)암(기타피부암 및 갑상선암 제외) 주요치료(갱)(해약환급금 미지급형)',
    '831612104': '(간편355)기타피부암 및 갑상선암 주요치료(갱)(해약환급금 미지급형)',
  };

  // 랜덤 지연 함수
  function randomDelay(min = MIN_DELAY_MS, max = MAX_DELAY_MS) {
    const delay = Math.floor(Math.random() * (max - min + 1)) + min;
    return new Promise(resolve => setTimeout(resolve, delay));
  }

  // 랜덤 배치 크기
  function getRandomBatchSize() {
    return Math.floor(Math.random() * (MAX_BATCH_SIZE - MIN_BATCH_SIZE + 1)) + MIN_BATCH_SIZE;
  }

  // 나이별 보험기간
  function getInsuranceTerms(age) {
    if (age >= 20 && age <= 34) return [30];
    if (age >= 35 && age <= 64) return [10, 20];
    return [];
  }

  function downloadJSON(data, filename) {
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function sKey(prodCd) { return `kb_health_ultra_${prodCd}`; }

  // 인간 행동 패턴 모방 - 요청 전 작은 지연
  async function humanLikeDelay() {
    await new Promise(resolve => setTimeout(resolve, Math.random() * 500 + 200));
  }

  async function calcOne(prodCd, birthday, genderCode, planName, insuranceTerm) {
    await humanLikeDelay(); // 인간처럼 약간의 지연

    let data;
    try {
      data = await ajax.post('INSURANCEPLAN', '/premium-calculate', null, {
        productCode: prodCd,
        birthday,
        genderCode,
        isVariable: false,
        isAnnuity: false,
        pcOnline: true,
        planName,
      });
    } catch (e) {
      const txt = (e.responseText || '').substring(0, 200).toLowerCase();
      if (txt.includes('contrary') || txt.includes('firewall') || txt.includes('blocked') || txt.includes('rate limit')) {
        return { error: 'waf' };
      }
      return { error: String(e).substring(0, 100) };
    }

    if (!data || !data.results || !data.results.length) return { error: 'empty' };

    const resultId = data.results[0];
    if (!resultId || !/^[0-9]+$/.test(String(resultId))) return { error: 'no_resultId' };

    // 선택형 특약 파싱
    const selectRiders = [];
    if (data.results.length > 1 && typeof data.results[1] === 'string') {
      try {
        const raw = data.results[1];
        const matches = [...raw.matchAll(/\{([^}]+)\}/g)];
        for (const m of matches) {
          const obj = {};
          m[1].split(',').forEach(pair => {
            const kv = pair.trim().split('=');
            if (kv.length === 2) obj[kv[0].trim()] = kv[1].trim();
          });
          if (obj.prodCd && obj.prodCd !== prodCd) {
            selectRiders.push({
              prodCd: obj.prodCd,
              premium: parseFloat(obj.prmum) || 0,
              entryAmount: parseFloat(obj.riderFaceamnt) || 0,
            });
          }
        }
      } catch (e) { }
    }

    await humanLikeDelay(); // 두 번째 요청 전 지연

    // 기본 특약 상세 조회
    let detail = null;
    try {
      detail = await ajax.get('INSURANCEPLAN', '/insuranceplans/' + resultId);
    } catch (e) {
      return { error: 'detail_fetch' };
    }

    // 데이터 구성
    const allRiders = [];
    let totalPremium = detail.mainPremium || 0;

    for (const r of (detail.riders || [])) {
      allRiders.push({
        prodCd: r.riderCode,
        name: r.riderName,
        premium: r.riderPremium || 0,
        entryAmount: r.entryAmount || 0,
      });
      totalPremium += r.riderPremium || 0;
    }

    const basicCodes = new Set(allRiders.map(r => r.prodCd));
    for (const sr of selectRiders) {
      if (!basicCodes.has(sr.prodCd)) {
        allRiders.push({
          prodCd: sr.prodCd,
          name: SELECTABLE_NAMES[sr.prodCd] || sr.prodCd,
          premium: sr.premium,
          entryAmount: sr.entryAmount,
        });
        totalPremium += sr.premium;
      }
    }

    return {
      results: {
        planFullName: detail.productName || '',
        insuranceTerm: detail.insuranceTerm,
        paymentTerm: detail.paymentTerm,
        mainPremium: detail.mainPremium || 0,
        totalPremium,
        riders: allRiders,
      }
    };
  }

  async function scrapeHealthUltraSafe(prodCd, productName) {
    if (typeof ajax === 'undefined') {
      console.error('ajax 없음! 먼저 수동으로 보험료 계산 1번 해주세요.');
      return;
    }

    if (!productName) productName = prodCd;

    console.log(`=== ${productName} 초안전 스크래핑 시작 ===`);
    console.log('설정: 배치 1-2개, 지연 3-8초, 인간 패턴 모방');

    const sk = sKey(prodCd);
    const saved = JSON.parse(localStorage.getItem(sk + '_done') || '{}');
    const savedResults = JSON.parse(localStorage.getItem(sk + '_results') || '[]');
    console.log(`이전: ${Object.keys(saved).length}건 완료, ${savedResults.length}건 저장`);

    // 작업 목록 생성 (일부만 먼저 테스트)
    const items = [];
    for (let age = 20; age <= 25; age++) { // 우선 20-25세만 테스트
      const terms = getInsuranceTerms(age);
      for (const term of terms) {
        for (const plan of PLAN_NAMES.slice(0, 2)) { // 든든, 실속만 우선
          for (const [gc, gn] of [['1', '남'], ['2', '여']]) {
            const key = `${age}_${gn}_${plan}_${term}`;
            if (saved[key]) continue;
            items.push({
              key, age,
              birthday: `${2026 - age}0101`,
              gc, gn, plan, term,
            });
          }
        }
      }
    }

    console.log(`테스트 범위: ${items.length}건 (20-25세, 든든/실속만)`);

    if (items.length === 0) {
      console.log('테스트 작업 완료!');
      return;
    }

    let success = 0, errors = 0, wafHit = false;
    const results = [...savedResults];
    const startTime = Date.now();

    for (let b = 0; b < items.length;) {
      const batchSize = getRandomBatchSize();
      const batch = items.slice(b, b + batchSize);
      const t0 = Date.now();

      console.log(`[배치 ${Math.floor(b/2)+1}] ${batchSize}개 처리 중...`);

      // 순차 처리 (병렬 대신)
      const batchResults = [];
      for (const item of batch) {
        const result = await calcOne(prodCd, item.birthday, item.gc, item.plan, item.term);
        batchResults.push(result);

        if (result.error === 'waf') {
          wafHit = true;
          break;
        }

        // 각 요청 사이에 작은 지연
        if (batch.length > 1) await humanLikeDelay();
      }

      const dt = ((Date.now() - t0) / 1000).toFixed(1);

      for (let j = 0; j < batchResults.length; j++) {
        const item = batch[j];
        const result = batchResults[j];

        if (result.error === 'waf') {
          console.error(`WAF 감지! 중단: ${item.key}`);
          break;
        }

        if (result.results) {
          results.push({
            _key: item.key,
            product: productName,
            prodCd,
            age: item.age,
            gender: item.gn,
            planName: item.plan,
            insuranceTerm: result.results.insuranceTerm,
            paymentTerm: result.results.paymentTerm,
            paymentMethod: '월납',
            totalPremium: result.results.totalPremium,
            riders: result.results.riders,
          });
          saved[item.key] = true;
          success++;
        } else {
          errors++;
          if (errors <= 3) console.log(`에러: ${item.key} - ${result.error}`);
        }
      }

      console.log(`${dt}s 완료 | 성공=${success} 에러=${errors}`);

      localStorage.setItem(sk + '_done', JSON.stringify(saved));
      localStorage.setItem(sk + '_results', JSON.stringify(results));

      if (wafHit) {
        console.error(`보안 차단 감지. 성공: ${success}건`);
        break;
      }

      b += batchSize;

      // 배치 간 랜덤 지연
      if (b < items.length) {
        const delay = Math.floor(Math.random() * (MAX_DELAY_MS - MIN_DELAY_MS + 1)) + MIN_DELAY_MS;
        console.log(`다음 배치까지 ${delay/1000}초 대기...`);
        await randomDelay(delay, delay);
      }
    }

    console.log(`\n=== 테스트 완료! 성공=${success} 에러=${errors} ===`);
    if (results.length > 0) {
      const lines = results.map(r => JSON.stringify(r)).join('\n');
      downloadJSON(lines, `${productName}_테스트_${results.length}건.jsonl`);
    }
  }

  // 전역 함수 등록
  window.__scrapeHealthUltraSafe = scrapeHealthUltraSafe;

  window.__healthStatusUltra = function () {
    const products = [
      { name: 'e건강보험_일반심사', prodCd: '337600104' },
      { name: 'e건강보험_간편심사355', prodCd: '331600104' },
    ];
    for (const p of products) {
      const done = Object.keys(JSON.parse(localStorage.getItem(sKey(p.prodCd) + '_done') || '{}')).length;
      const saved = JSON.parse(localStorage.getItem(sKey(p.prodCd) + '_results') || '[]').length;
      console.log(`${p.name}: ${done}건 완료, ${saved}건 저장`);
    }
  };

  if (location.href.includes('productDetails') || location.href.includes('product-detail')) {
    console.log('=== 초안전 e-건강보험 스크래퍼 로드됨 ===');
    console.log('  window.__scrapeHealthUltraSafe("337600104", "e건강보험_일반심사")');
    console.log('  window.__healthStatusUltra() → 진행 상태');
    console.log('⚠️  테스트 모드: 20-25세, 든든/실속만 수집');
  }

})();