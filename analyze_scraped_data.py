"""
스크래핑된 데이터 분석 및 e-건강보험 특약 매핑
"""

import json
from pathlib import Path

def analyze_scraped_data():
    """스크래핑된 데이터 분석"""

    # 최신 스크래핑 파일 찾기
    files = list(Path('.').glob('kb_enhanced_*_남성_*.json'))
    if not files:
        print("스크래핑된 파일을 찾을 수 없습니다.")
        return

    latest_file = max(files, key=lambda f: f.stat().st_mtime)
    print(f"분석 대상 파일: {latest_file}")

    with open(latest_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("\n" + "="*80)
    print("KB 딱좋은 e-건강보험 무배당 (갱신형)(일반심사형)(해약환급금 미지급형)")
    print("스크래핑 데이터 분석 결과")
    print("="*80)

    # 기본 정보
    basic_info = data.get('basic_info', {})
    print(f"\n📋 기본 정보:")
    print(f"   나이: {basic_info.get('age', 'N/A')}세")
    print(f"   성별: {basic_info.get('gender', 'N/A')}")
    print(f"   생년월일: {basic_info.get('birthdate', 'N/A')}")
    print(f"   스크래핑 시점: {basic_info.get('scraped_at', 'N/A')}")

    # 플랜 정보 분석
    fixed_plans = data.get('fixed_plans', {})
    print(f"\n📊 발견된 플랜: {len(fixed_plans)}개")

    for plan_key, plan_data in fixed_plans.items():
        plan_info = plan_data.get('plan_info', {})
        current_premium = plan_data.get('current_premium', 'N/A')
        clause_count = plan_data.get('clause_count', 0)

        print(f"\n🔹 {plan_key}:")
        print(f"   플랜명: {plan_info.get('text', 'N/A')}")
        print(f"   현재 보험료: {current_premium}")
        print(f"   특약 개수: {clause_count}개")

        # 특약 상세 분석
        clauses = plan_data.get('fixed_clauses', [])
        print(f"\n   📝 주요 특약:")

        # e-건강보험 특약 분류
        cancer_clauses = []
        brain_heart_clauses = []
        surgery_clauses = []
        hospital_clauses = []
        other_clauses = []

        for clause in clauses[:10]:  # 처음 10개만 표시
            text = clause.get('text', '').strip()
            if '암' in text:
                cancer_clauses.append(text[:50])
            elif '뇌' in text or '심장' in text:
                brain_heart_clauses.append(text[:50])
            elif '수술' in text:
                surgery_clauses.append(text[:50])
            elif '입원' in text:
                hospital_clauses.append(text[:50])
            else:
                other_clauses.append(text[:50])

        if cancer_clauses:
            print(f"      🎗️  암 관련 특약:")
            for clause in cancer_clauses:
                print(f"         - {clause}")

        if brain_heart_clauses:
            print(f"      ❤️  뇌/심장 관련 특약:")
            for clause in brain_heart_clauses:
                print(f"         - {clause}")

        if surgery_clauses:
            print(f"      🏥 수술 관련 특약:")
            for clause in surgery_clauses:
                print(f"         - {clause}")

        if hospital_clauses:
            print(f"      🏨 입원 관련 특약:")
            for clause in hospital_clauses:
                print(f"         - {clause}")

        if other_clauses:
            print(f"      📋 기타 특약:")
            for clause in other_clauses[:3]:  # 최대 3개만
                print(f"         - {clause}")

    # 기존 e-건강보험 데이터와 비교
    print(f"\n" + "="*50)
    print("기존 레포지토리 e-건강보험 데이터와 비교")
    print("="*50)

    # 기존 e-건강보험 데이터 확인
    ehealth_file = Path("sanhak-hyeopryuk/data/premiums/e건강보험_일반심사_전체.jsonl")
    if ehealth_file.exists():
        print("✅ 기존 e-건강보험 일반심사 데이터 발견")

        with open(ehealth_file, 'r', encoding='utf-8') as f:
            first_line = f.readline()
            if first_line:
                sample_data = json.loads(first_line)

                print(f"\n📊 기존 데이터 샘플 (20세 남성):")
                print(f"   상품코드: {sample_data.get('prodCd', 'N/A')}")
                print(f"   플랜: {sample_data.get('planName', 'N/A')}")
                print(f"   총 보험료: {sample_data.get('totalPremium', 'N/A'):,}원")
                print(f"   특약 개수: {len(sample_data.get('riders', []))}개")

                print(f"\n   주요 특약들:")
                riders = sample_data.get('riders', [])[:5]  # 처음 5개만
                for rider in riders:
                    name = rider.get('name', '')
                    premium = rider.get('premium', 0)
                    print(f"      - {name}: {premium:,}원")
    else:
        print("❌ 기존 e-건강보험 데이터 파일을 찾을 수 없음")

    print(f"\n" + "="*80)
    print("분석 완료")
    print("="*80)

if __name__ == "__main__":
    analyze_scraped_data()