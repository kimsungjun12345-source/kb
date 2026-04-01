"""
KB라이프 직접 API 호출 보험료 수집기
발견한 API를 활용해서 나이별(19-65세) 남녀 보험료 데이터 수집
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from datetime import datetime, date
import aiohttp

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('direct_api_scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class KBDirectAPIScraper:
    """KB라이프 직접 API 호출 스크래퍼"""

    def __init__(self):
        self.base_url = "https://www.kblife.co.kr"
        self.session = None

        # 발견한 주요 API 엔드포인트들
        self.api_endpoints = {
            "insurance_option": "/api/insuranceplan/insuranceplan-option/{product_code}",
            "product_details": "/api/product/product-details/{product_id}",
            "product_mapping": "/api/insuranceplan/product-mappings/{product_code}",
            "application": "/api/application/appl/putDgtlCnttInfo.do"
        }

        # 상품 정보
        self.products = {
            "316100104": {  # KB 착한암보험 무배당
                "name": "KB 착한암보험 무배당",
                "product_id": "501615946",
                "link_code": "ON_PD_KC_01"
            }
        }

        # 결과 저장
        self.premium_data = []

    async def setup_session(self):
        """HTTP 세션 설정"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01&productType=5',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin'
        }

        self.session = aiohttp.ClientSession(
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30)
        )

    def calculate_birth_date(self, age: int) -> str:
        """나이를 기준으로 생년월일 계산 (임의 월일)"""
        current_year = datetime.now().year
        birth_year = current_year - age
        # 임의로 7월 15일로 설정
        return f"{birth_year}-07-15"

    def get_insurance_age(self, age: int) -> int:
        """보험 나이 계산 (일반적으로 만 나이와 동일)"""
        return age

    async def get_premium_data(self, product_code: str, age: int, gender_code: int) -> Dict[str, Any]:
        """특정 나이와 성별에 대한 보험료 데이터 조회"""

        try:
            # API 파라미터 설정
            params = {
                'genderCode': gender_code,  # 1=남성, 2=여성
                'isVariable': 'false',
                'isAnnuity': 'false',
                'riskGrdCd': '3',  # 위험등급 (일반적으로 3)
                'insuranceAge': self.get_insurance_age(age),
                'channel': '1004'  # 온라인 채널
            }

            # API 호출
            url = f"{self.base_url}{self.api_endpoints['insurance_option'].format(product_code=product_code)}"

            logger.info(f"API 호출: {age}세 {'남성' if gender_code == 1 else '여성'}")

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    # 응답 데이터에서 보험료 정보 추출
                    premium_info = self.extract_premium_info(data, age, gender_code)

                    if premium_info:
                        logger.info(f"✅ 보험료 수집 성공: {age}세 {'남성' if gender_code == 1 else '여성'}")
                        return premium_info
                    else:
                        logger.warning(f"⚠️ 보험료 데이터 없음: {age}세 {'남성' if gender_code == 1 else '여성'}")
                else:
                    logger.error(f"❌ API 호출 실패: {response.status}")

        except Exception as e:
            logger.error(f"API 호출 중 오류: {e}")

        return None

    def extract_premium_info(self, api_response: Any, age: int, gender_code: int) -> Dict[str, Any]:
        """API 응답에서 보험료 정보 추출"""

        try:
            # API 응답 구조에 따라 보험료 정보 추출
            if isinstance(api_response, list) and len(api_response) > 0:
                # 배열 형태의 응답인 경우
                premium_data = api_response[0]
            elif isinstance(api_response, dict):
                # 객체 형태의 응답인 경우
                premium_data = api_response
            else:
                return None

            # 보험료 관련 필드들 찾기
            premium_fields = [
                'premium', 'premiumAmount', 'monthlyPremium', 'annualPremium',
                '보험료', 'prm', 'amt', 'amount', 'price'
            ]

            extracted_premium = None
            for field in premium_fields:
                if field in str(premium_data):
                    # 숫자 값 찾기
                    if isinstance(premium_data, dict):
                        for key, value in premium_data.items():
                            if field.lower() in key.lower() and isinstance(value, (int, float)):
                                extracted_premium = value
                                break
                    break

            # 추출된 정보 반환
            result = {
                'age': age,
                'gender': '남성' if gender_code == 1 else '여성',
                'gender_code': gender_code,
                'birth_date': self.calculate_birth_date(age),
                'insurance_age': self.get_insurance_age(age),
                'premium_amount': extracted_premium,
                'api_response_sample': str(premium_data)[:500],  # 디버깅용
                'collected_at': datetime.now().isoformat()
            }

            return result

        except Exception as e:
            logger.error(f"보험료 정보 추출 중 오류: {e}")
            return None

    async def collect_all_premiums(self, product_code: str):
        """모든 나이와 성별에 대한 보험료 수집"""

        logger.info(f"보험료 데이터 수집 시작: {self.products[product_code]['name']}")

        # 나이 범위: 19-65세
        ages = range(19, 66)
        # 성별: 1=남성, 2=여성
        genders = [1, 2]

        total_combinations = len(ages) * len(genders)
        collected_count = 0

        for age in ages:
            for gender_code in genders:
                try:
                    premium_info = await self.get_premium_data(product_code, age, gender_code)

                    if premium_info:
                        self.premium_data.append(premium_info)
                        collected_count += 1

                    # API 호출 간격 (너무 빠르게 호출하지 않도록)
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"데이터 수집 중 오류 - {age}세 {gender_code}: {e}")
                    continue

        logger.info(f"수집 완료: {collected_count}/{total_combinations} 개")
        return self.premium_data

    async def save_results(self, product_code: str):
        """수집 결과 저장"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        product_name = self.products[product_code]['name']

        # JSON 파일 저장
        result_data = {
            'metadata': {
                'product_code': product_code,
                'product_name': product_name,
                'collected_at': timestamp,
                'total_records': len(self.premium_data),
                'age_range': '19-65세',
                'genders': ['남성', '여성']
            },
            'premium_data': self.premium_data
        }

        filename = f'kb_premium_direct_{product_code}_{timestamp}.json'
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result_data, f, ensure_ascii=False, indent=2)

        logger.info(f"결과 저장: {filename}")

        # 요약 출력
        print(f"\n{'='*60}")
        print(f"KB라이프 직접 API 보험료 수집 결과")
        print(f"{'='*60}")
        print(f"상품: {product_name}")
        print(f"수집 데이터: {len(self.premium_data)}건")

        if self.premium_data:
            # 성공한 데이터 샘플 출력
            sample_data = self.premium_data[0]
            print(f"\n📊 샘플 데이터:")
            print(f"- 나이: {sample_data['age']}세")
            print(f"- 성별: {sample_data['gender']}")
            print(f"- 보험료: {sample_data.get('premium_amount', '정보없음')}")

            # 성별별 통계
            male_count = len([d for d in self.premium_data if d['gender'] == '남성'])
            female_count = len([d for d in self.premium_data if d['gender'] == '여성'])
            print(f"\n📈 수집 통계:")
            print(f"- 남성 데이터: {male_count}건")
            print(f"- 여성 데이터: {female_count}건")
        else:
            print("❌ 수집된 데이터가 없습니다.")

    async def run(self):
        """메인 실행"""

        try:
            await self.setup_session()

            # KB 착한암보험에 대해 데이터 수집
            product_code = "316100104"

            await self.collect_all_premiums(product_code)
            await self.save_results(product_code)

        except Exception as e:
            logger.error(f"실행 중 오류: {e}")
        finally:
            if self.session:
                await self.session.close()

async def main():
    """메인 함수"""

    print("KB라이프 직접 API 보험료 수집기를 시작합니다...")
    print("발견한 API를 활용해서 나이별 보험료 데이터를 수집합니다.")

    scraper = KBDirectAPIScraper()
    await scraper.run()

    print("\n수집 완료!")

if __name__ == "__main__":
    asyncio.run(main())