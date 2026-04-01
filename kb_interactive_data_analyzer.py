"""
KB라이프 인터랙티브 데이터 분석기
사용자 상호작용으로 수집한 동적 데이터를 분석하여 핵심 정보 추출
"""

import json
import re
from typing import Dict, List, Any
from datetime import datetime

class KBInteractiveDataAnalyzer:
    """KB라이프 인터랙티브 데이터 분석기"""

    def __init__(self, results_file: str):
        self.results_file = results_file
        self.data = self.load_data()
        self.analysis_results = {}

    def load_data(self) -> Dict:
        """수집된 데이터 로드"""
        with open(self.results_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def extract_premium_information(self) -> Dict[str, Any]:
        """보험료 관련 정보 추출"""
        premium_info = {
            'api_premiums': [],
            'displayed_premiums': [],
            'premium_table_data': []
        }

        # 1. API 응답에서 보험료 정보 추출
        network_captures = self.data.get('network_captures', [])
        for capture in network_captures:
            if 'insuranceplan-option' in capture.get('url', ''):
                api_data = capture.get('data', {})
                if 'products' in api_data:
                    for product in api_data['products']:
                        premium_info['api_premiums'].append({
                            'product_code': product.get('gsSpSpcd1'),
                            'product_name': product.get('gsBhir'),
                            'coverage_amount': product.get('gsCdgiga'),
                            'api_timestamp': capture.get('timestamp')
                        })

        # 2. 상호작용으로 나타난 보험료 표시 정보 추출
        interactions = self.data.get('interaction_results', {}).get('interactions', [])
        for interaction in interactions:
            if interaction.get('action') == 'button_click':
                changes = interaction.get('changes', {})
                for key, value in changes.items():
                    if '원' in value and ('보험료' in value or '납입' in value):
                        premium_info['displayed_premiums'].append({
                            'trigger': interaction.get('button_text'),
                            'element': key,
                            'content': value[:200],  # 처음 200자만
                            'full_content': value
                        })

        return premium_info

    def extract_age_gender_variations(self) -> Dict[str, Any]:
        """나이/성별 조합별 변화 추출"""
        age_gender_data = []

        interactions = self.data.get('interaction_results', {}).get('interactions', [])
        for interaction in interactions:
            if 'age' in interaction and 'gender' in interaction:
                age_gender_data.append({
                    'age': interaction['age'],
                    'gender': interaction['gender'],
                    'changes_detected': len(interaction.get('changes', [])),
                    'changes': interaction.get('changes', [])
                })

        return {
            'total_combinations_tested': len(age_gender_data),
            'age_gender_data': age_gender_data
        }

    def extract_dynamic_form_elements(self) -> Dict[str, Any]:
        """동적 폼 요소 변화 추출"""
        form_elements = []

        interactions = self.data.get('interaction_results', {}).get('interactions', [])
        for interaction in interactions:
            if interaction.get('action') in ['button_click', 'select_option', 'number_input']:
                form_elements.append({
                    'action_type': interaction.get('action'),
                    'trigger_text': interaction.get('button_text') or interaction.get('option_text'),
                    'selector': interaction.get('selector'),
                    'changes_count': len(interaction.get('changes', {})),
                    'significant_changes': self.find_significant_changes(interaction.get('changes', {}))
                })

        return {
            'total_form_interactions': len(form_elements),
            'form_elements': form_elements
        }

    def find_significant_changes(self, changes: Dict) -> List[str]:
        """중요한 변화 내용 필터링"""
        significant = []

        for key, value in changes.items():
            # 보험료, 금액, 혜택 관련 중요한 변화
            if any(keyword in value for keyword in ['원', '보험료', '만원', '천원', '%', '혜택', '보장']):
                # 너무 긴 텍스트는 요약
                if len(value) > 100:
                    significant.append(f"{key}: {value[:100]}...")
                else:
                    significant.append(f"{key}: {value}")

        return significant

    def extract_coverage_options(self) -> Dict[str, Any]:
        """보장 옵션 및 특약 정보 추출"""
        coverage_info = {
            'special_coverages': [],
            'coverage_amounts': [],
            'coverage_types': []
        }

        # 모든 텍스트에서 특약 및 보장 정보 추출
        all_text = json.dumps(self.data, ensure_ascii=False)

        # 특약 패턴 찾기
        special_patterns = [
            r'(간병\w*)', r'(입원\w*)', r'(수술\w*)', r'(진단\w*)',
            r'(\w*특약)', r'(\w*보장)', r'(\w*혜택)'
        ]

        for pattern in special_patterns:
            matches = re.findall(pattern, all_text)
            coverage_info['special_coverages'].extend(list(set(matches)))

        # 금액 패턴 찾기
        amount_patterns = [
            r'(\d+,?\d*)\s*만원',
            r'(\d+,?\d*)\s*원',
            r'(\d+,?\d*)\s*천원'
        ]

        for pattern in amount_patterns:
            matches = re.findall(pattern, all_text)
            coverage_info['coverage_amounts'].extend(matches[:10])  # 상위 10개만

        return coverage_info

    def generate_analysis_report(self) -> Dict[str, Any]:
        """종합 분석 보고서 생성"""
        print("KB라이프 인터랙티브 데이터 분석 중...")

        # 각 분석 실행
        premium_analysis = self.extract_premium_information()
        age_gender_analysis = self.extract_age_gender_variations()
        form_analysis = self.extract_dynamic_form_elements()
        coverage_analysis = self.extract_coverage_options()

        # 네트워크 API 분석
        api_calls = self.data.get('network_captures', [])
        api_summary = {
            'total_api_calls': len(api_calls),
            'unique_endpoints': list(set([call.get('url', '').split('?')[0] for call in api_calls])),
            'api_by_type': {}
        }

        for call in api_calls:
            url = call.get('url', '')
            if 'insuranceplan-option' in url:
                api_summary['api_by_type']['premium_calculation'] = api_summary['api_by_type'].get('premium_calculation', 0) + 1
            elif 'product-details' in url:
                api_summary['api_by_type']['product_details'] = api_summary['api_by_type'].get('product_details', 0) + 1
            elif 'product-mappings' in url:
                api_summary['api_by_type']['product_mappings'] = api_summary['api_by_type'].get('product_mappings', 0) + 1

        # 종합 보고서
        analysis_report = {
            'analysis_metadata': {
                'analyzed_at': datetime.now().isoformat(),
                'source_file': self.results_file,
                'original_url': self.data.get('interaction_results', {}).get('url'),
                'collection_timestamp': self.data.get('interaction_results', {}).get('timestamp')
            },
            'premium_analysis': premium_analysis,
            'age_gender_analysis': age_gender_analysis,
            'form_interaction_analysis': form_analysis,
            'coverage_analysis': coverage_analysis,
            'api_analysis': api_summary,
            'summary': {
                'total_interactions': len(self.data.get('interaction_results', {}).get('interactions', [])),
                'total_api_calls': len(api_calls),
                'button_clicks_captured': len([i for i in self.data.get('interaction_results', {}).get('interactions', []) if i.get('action') == 'button_click']),
                'age_gender_combinations': age_gender_analysis['total_combinations_tested'],
                'unique_coverage_types': len(coverage_analysis['special_coverages'])
            }
        }

        return analysis_report

    def save_analysis_report(self, report: Dict):
        """분석 보고서 저장"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'kb_interactive_analysis_{timestamp}.json'

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"분석 보고서 저장: {filename}")
        return filename

    def print_summary(self, report: Dict):
        """분석 결과 요약 출력"""
        print("\n" + "="*60)
        print("KB라이프 인터랙티브 데이터 분석 결과")
        print("="*60)

        summary = report['summary']
        print(f"총 상호작용: {summary['total_interactions']}개")
        print(f"API 호출: {summary['total_api_calls']}개")
        print(f"버튼 클릭: {summary['button_clicks_captured']}개")
        print(f"나이/성별 조합: {summary['age_gender_combinations']}개")

        print(f"\n📊 발견된 주요 API 엔드포인트:")
        for endpoint in report['api_analysis']['unique_endpoints'][:5]:
            print(f"- {endpoint}")

        print(f"\n💰 보험료 정보:")
        premium_data = report['premium_analysis']
        print(f"- API 보험료 데이터: {len(premium_data['api_premiums'])}개")
        print(f"- 화면 보험료 표시: {len(premium_data['displayed_premiums'])}개")

        if premium_data['api_premiums']:
            sample = premium_data['api_premiums'][0]
            print(f"- 샘플 상품: {sample.get('product_name')}")
            print(f"- 상품코드: {sample.get('product_code')}")

        print(f"\n🎯 보장 내용:")
        coverage = report['coverage_analysis']
        print(f"- 특약/보장 유형: {len(coverage['special_coverages'])}개")
        if coverage['special_coverages']:
            print(f"- 주요 특약: {', '.join(coverage['special_coverages'][:5])}")

        print(f"\n📱 동적 변화:")
        form_analysis = report['form_interaction_analysis']
        print(f"- 폼 상호작용: {form_analysis['total_form_interactions']}개")
        for element in form_analysis['form_elements'][:3]:
            if element['significant_changes']:
                print(f"- {element['action_type']}: {len(element['significant_changes'])}개 변화")

def main():
    """메인 함수"""
    # 가장 최근의 interactive 결과 파일 사용
    results_file = "kb_interactive_results_KB_착한암보험_20260327_173228.json"

    print("KB라이프 인터랙티브 데이터 분석기 시작...")

    try:
        analyzer = KBInteractiveDataAnalyzer(results_file)
        report = analyzer.generate_analysis_report()

        # 보고서 저장
        saved_file = analyzer.save_analysis_report(report)

        # 요약 출력
        analyzer.print_summary(report)

        print(f"\n✅ 분석 완료!")
        print(f"상세 분석 결과: {saved_file}")

    except Exception as e:
        print(f"❌ 분석 중 오류 발생: {e}")

if __name__ == "__main__":
    main()