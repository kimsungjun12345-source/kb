/**
 * KB Life e-건강보험 수정된 스크래퍼 v3.0
 * - 올바른 API 파라미터 적용
 * - 생년월일 형식 수정
 */

(function () {
  'use strict';

  const BATCH_SIZE = 3;
  const BATCH_DELAY_MS = 3000;
  const PLAN_NAMES = ['든든', '실속', '뇌심', '입원'];

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

  function sKey(prodCd) { return `kb_health_fixed_${prodCd}`; }

  async function calcOneFixed(prodCd, birthday, genderCode, planName, insuranceTerm) {
    let data;
    try {
      // 수정된 파라미터 (성공한 형태)
      data = await ajax.post('INSURANCEPLAN', '/premium-calculate', null, {
        productCode: prodCd,
        birthday: birthday,  // YYYYMMDD 형식 사용
        genderCode: genderCode,
        planName: planName,
        isVariable: false,
        isAnnuity: false,
        pcOnline: true
      });
    } catch (e) {
      const txt = (e.responseText || '').substring(0, 200).toLowerCase();
      if (txt.includes('contrary') || txt.includes('firewall') || txt.includes('blocked')) {
        return { error: 'waf' };
      }
      return { error: String(e).substring(0, 100) };
    }

    console.log('API 응답:', data); // 디버깅용

    if (!data || !data.results || !data.results.length) {
      return { error: 'empty' };
    }

    const resultId = data.results[0];
    if (!resultId || !/^[0-9]+$/.test(String(resultId))) {
      return { error: 'no_resultId' };
    }

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

  async function scrapeHealthFixed(prodCd, productName) {
    if (typeof ajax === 'undefined') {
      console.error('ajax 없음! 먼저 수동으로 보험료 계산 1번 해주세요.');
      return;
    }

    if (!productName) productName = prodCd;

    console.log(`=== ${productName} 수정된 스크래핑 시작 ===`);

    const sk = sKey(prodCd);
    const saved = JSON.parse(localStorage.getItem(sk + '_done') || '{}');
    const savedResults = JSON.parse(localStorage.getItem(sk + '_results') || '[]');
    console.log(`이전: ${Object.keys(saved).length}건 완료, ${savedResults.length}건 저장`);

    // 작업 목록 생성 (테스트: 25-30세만)
    const items = [];
    for (let age = 25; age <= 30; age++) {
      const terms = getInsuranceTerms(age);
      for (const term of terms) {
        for (const plan of ['든든', '실속']) { // 2개 플랜만 테스트
          for (const [gc, gn] of [['1', '남'], ['2', '여']]) {
            const key = `${age}_${gn}_${plan}_${term}`;
            if (saved[key]) continue;
            items.push({
              key, age,
              birthday: `${2026 - age}0101`, // YYYYMMDD 형식
              gc, gn, plan, term,
            });
          }
        }
      }
    }

    console.log(`테스트 범위: ${items.length}건 (25-30세, 든든/실속)`);

    if (items.length === 0) {
      console.log('테스트 작업 완료!');
      return;
    }

    let success = 0, errors = 0, wafHit = false;
    const results = [...savedResults];
    const startTime = Date.now();

    for (let b = 0; b < items.length; b += BATCH_SIZE) {
      const batch = items.slice(b, b + BATCH_SIZE);
      const t0 = Date.now();

      console.log(`[배치 ${Math.floor(b/BATCH_SIZE)+1}/${Math.ceil(items.length/BATCH_SIZE)}] ${batch.length}개 처리 중...`);

      const batchResults = await Promise.all(
        batch.map(item => calcOneFixed(prodCd, item.birthday, item.gc, item.plan, item.term))
      );

      const dt = ((Date.now() - t0) / 1000).toFixed(1);

      for (let j = 0; j < batch.length; j++) {
        const item = batch[j];
        const result = batchResults[j];

        if (result.error === 'waf') {
          wafHit = true;
          console.error(`WAF! key=${item.key}`);
          continue;
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
          if (errors <= 5) console.log(`에러: ${item.key} - ${result.error}`);
        }
      }

      const elapsed = (Date.now() - startTime) / 1000;
      const batchNum = Math.floor(b / BATCH_SIZE) + 1;
      const totalBatches = Math.ceil(items.length / BATCH_SIZE);
      const remaining = Math.round((totalBatches - batchNum) * (elapsed / batchNum));

      console.log(`[${batchNum}/${totalBatches}] ${dt}s | 성공=${success} 에러=${errors}`);

      localStorage.setItem(sk + '_done', JSON.stringify(saved));
      localStorage.setItem(sk + '_results', JSON.stringify(results));

      if (wafHit) {
        console.error(`WAF 차단. 성공: ${success}건`);
        break;
      }

      if (b + BATCH_SIZE < items.length) {
        console.log(`다음 배치까지 ${BATCH_DELAY_MS/1000}초 대기...`);
        await new Promise(resolve => setTimeout(resolve, BATCH_DELAY_MS));
      }
    }

    console.log(`\n=== ${productName} 테스트 완료! 성공=${success} 에러=${errors} ===`);
    localStorage.setItem(sk + '_done', JSON.stringify(saved));
    localStorage.setItem(sk + '_results', JSON.stringify(results));

    if (results.length > 0) {
      const lines = results.map(r => JSON.stringify(r)).join('\n');
      downloadJSON(lines, `${productName}_테스트_${results.length}건_완료.jsonl`);
    }
  }

  window.__scrapeHealthFixed = scrapeHealthFixed;

  window.__healthStatusFixed = function () {
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

  console.log('=== 수정된 e-건강보험 스크래퍼 로드됨 ===');
  console.log('  window.__scrapeHealthFixed("337600104", "e건강보험_일반심사")');
  console.log('  window.__healthStatusFixed() → 진행 상태');

})();