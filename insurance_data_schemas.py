"""
KB 보험상품 데이터 구조 정의
Pydantic을 사용한 보험 상품 데이터 스키마 및 검증 시스템
"""

from datetime import datetime, date
from typing import Dict, List, Optional, Union, Any
from enum import Enum
from decimal import Decimal

try:
    from pydantic import BaseModel, Field, model_validator
    from pydantic.types import constr, conint, confloat
except ImportError:
    print("Pydantic 설치 필요: pip install pydantic")

# 기본 열거형들
class GenderType(str, Enum):
    MALE = "남성"
    FEMALE = "여성"

class InsuranceType(str, Enum):
    CANCER = "암보험"
    HEALTH = "건강보험"
    TERM = "정기보험"
    ANNUITY = "연금보험"
    ACCIDENT = "상해보험"

class PaymentMethod(str, Enum):
    MONTHLY = "월납"
    QUARTERLY = "분기납"
    SEMI_ANNUAL = "반기납"
    ANNUAL = "연납"
    LUMP_SUM = "일시납"

class PaymentPeriod(str, Enum):
    WHOLE_LIFE = "종신"
    FIXED_10 = "10년"
    FIXED_15 = "15년"
    FIXED_20 = "20년"
    FIXED_30 = "30년"
    AGE_60 = "60세"
    AGE_65 = "65세"
    AGE_70 = "70세"

class CoverageType(str, Enum):
    WHOLE_LIFE = "종신"
    TERM_10 = "10년"
    TERM_20 = "20년"
    TERM_30 = "30년"
    AGE_80 = "80세"
    AGE_100 = "100세"

# 기본 데이터 모델들
class PremiumData(BaseModel):
    """보험료 데이터"""
    age: conint(ge=19, le=85) = Field(..., description="가입 연령")
    gender: GenderType = Field(..., description="성별")
    premium_amount: confloat(ge=0) = Field(..., description="보험료 금액")
    payment_method: PaymentMethod = Field(..., description="납입 방법")
    currency: str = Field(default="KRW", description="통화")

class CoverageDetail(BaseModel):
    """보장 상세 정보"""
    coverage_name: str = Field(..., description="보장명")
    coverage_amount: confloat(ge=0) = Field(..., description="보장 금액")
    coverage_type: str = Field(..., description="보장 유형")
    description: Optional[str] = Field(None, description="보장 설명")
    conditions: List[str] = Field(default_factory=list, description="지급 조건")
    exclusions: List[str] = Field(default_factory=list, description="면책 사항")

class SpecialClause(BaseModel):
    """특약 정보"""
    clause_name: str = Field(..., description="특약명")
    clause_code: Optional[str] = Field(None, description="특약 코드")
    description: str = Field(..., description="특약 설명")
    premium_rate: Optional[float] = Field(None, description="특약 보험료율")
    coverage_details: List[CoverageDetail] = Field(default_factory=list, description="특약 보장 내용")

class AgeRange(BaseModel):
    """연령 범위"""
    min_age: conint(ge=0, le=100) = Field(..., description="최소 연령")
    max_age: conint(ge=0, le=100) = Field(..., description="최대 연령")

    @model_validator(mode='after')
    def validate_age_range(self):
        if self.min_age > self.max_age:
            raise ValueError('최소 연령이 최대 연령보다 클 수 없습니다.')
        return self

class ProductInfo(BaseModel):
    """보험상품 기본 정보"""
    product_code: str = Field(..., description="상품 코드")
    product_name: str = Field(..., description="상품명")
    insurance_type: InsuranceType = Field(..., description="보험 유형")
    company_name: str = Field(default="KB라이프생명", description="보험회사명")
    launch_date: Optional[date] = Field(None, description="출시일")
    sales_status: str = Field(default="판매중", description="판매 상태")

class EligibilityInfo(BaseModel):
    """가입 자격 정보"""
    age_range: AgeRange = Field(..., description="가입 가능 연령")
    gender_restriction: Optional[GenderType] = Field(None, description="성별 제한")
    health_requirements: List[str] = Field(default_factory=list, description="건강 요구사항")
    occupation_restrictions: List[str] = Field(default_factory=list, description="직업 제한")
    other_conditions: List[str] = Field(default_factory=list, description="기타 조건")

class ContractInfo(BaseModel):
    """계약 정보"""
    coverage_period: CoverageType = Field(..., description="보장 기간")
    payment_period: PaymentPeriod = Field(..., description="납입 기간")
    payment_methods: List[PaymentMethod] = Field(..., description="납입 방법")
    renewal_type: Optional[str] = Field(None, description="갱신 유형")
    conversion_options: List[str] = Field(default_factory=list, description="전환 옵션")

class DocumentInfo(BaseModel):
    """문서 정보"""
    document_type: str = Field(..., description="문서 유형")
    file_path: str = Field(..., description="파일 경로")
    processed_at: datetime = Field(..., description="처리 시각")
    extraction_method: Optional[str] = Field(None, description="추출 방법")
    text_length: Optional[int] = Field(None, description="추출된 텍스트 길이")

# 메인 보험상품 모델
class InsuranceProduct(BaseModel):
    """통합 보험상품 데이터 모델"""

    # 기본 정보
    product_info: ProductInfo = Field(..., description="상품 기본 정보")
    eligibility: EligibilityInfo = Field(..., description="가입 자격")
    contract_info: ContractInfo = Field(..., description="계약 정보")

    # 보장 정보
    main_coverage: List[CoverageDetail] = Field(..., description="주계약 보장")
    special_clauses: List[SpecialClause] = Field(default_factory=list, description="특약")

    # 보험료 정보
    premium_data: List[PremiumData] = Field(default_factory=list, description="보험료 데이터")
    premium_examples: Dict[str, Any] = Field(default_factory=dict, description="보험료 예시")

    # 추가 정보
    key_features: List[str] = Field(default_factory=list, description="주요 특징")
    benefits: List[str] = Field(default_factory=list, description="혜택")
    exclusions: List[str] = Field(default_factory=list, description="면책 사항")
    notes: List[str] = Field(default_factory=list, description="유의사항")

    # 메타데이터
    scraped_at: datetime = Field(..., description="스크래핑 시각")
    data_sources: List[DocumentInfo] = Field(default_factory=list, description="데이터 소스")
    urls: List[str] = Field(default_factory=list, description="관련 URL")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }

# 스크래핑 결과 통합 모델
class ScrapingResult(BaseModel):
    """스크래핑 결과 통합 모델"""

    metadata: Dict[str, Any] = Field(..., description="스크래핑 메타데이터")
    products: List[InsuranceProduct] = Field(..., description="보험상품 목록")

    # 품질 정보
    quality_metrics: Dict[str, Union[int, float]] = Field(default_factory=dict, description="데이터 품질 지표")
    validation_errors: List[str] = Field(default_factory=list, description="검증 오류")
    processing_logs: List[str] = Field(default_factory=list, description="처리 로그")

# 데이터 검증 및 변환 유틸리티
class DataValidator:
    """데이터 검증 및 변환 유틸리티"""

    @staticmethod
    def validate_product(data: Dict[str, Any]) -> InsuranceProduct:
        """원시 데이터를 검증된 InsuranceProduct로 변환"""
        try:
            return InsuranceProduct(**data)
        except Exception as e:
            raise ValueError(f"데이터 검증 실패: {e}")

    @staticmethod
    def normalize_premium_data(premium_list: List[Dict[str, Any]]) -> List[PremiumData]:
        """보험료 데이터 정규화"""
        normalized = []
        for premium in premium_list:
            try:
                # 성별 정규화
                if 'gender' in premium:
                    gender_map = {'male': '남성', 'female': '여성', 'M': '남성', 'F': '여성'}
                    premium['gender'] = gender_map.get(premium['gender'], premium['gender'])

                # 납입방법 정규화
                if 'payment_method' in premium:
                    method_map = {'monthly': '월납', 'annual': '연납'}
                    premium['payment_method'] = method_map.get(premium['payment_method'], premium['payment_method'])

                normalized.append(PremiumData(**premium))
            except Exception as e:
                print(f"보험료 데이터 정규화 실패: {e}")
                continue
        return normalized

    @staticmethod
    def extract_coverage_from_text(text: str) -> List[CoverageDetail]:
        """텍스트에서 보장 내용 추출 (간단한 패턴 매칭)"""
        import re

        coverages = []
        # 간단한 패턴으로 보장 내용 찾기
        patterns = [
            r'(\w+보장).*?(\d+(?:,\d+)*(?:\.\d+)?)(?:만원|원)',
            r'(\w+급여금).*?(\d+(?:,\d+)*(?:\.\d+)?)(?:만원|원)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                coverage_name, amount_str = match
                try:
                    amount = float(amount_str.replace(',', ''))
                    coverages.append(CoverageDetail(
                        coverage_name=coverage_name,
                        coverage_amount=amount,
                        coverage_type="기본보장"
                    ))
                except ValueError:
                    continue

        return coverages

# 데이터 변환기
class DataTransformer:
    """다양한 데이터 소스를 통합 스키마로 변환"""

    def __init__(self):
        self.validator = DataValidator()

    def transform_scraped_data(self, raw_data: Dict[str, Any]) -> InsuranceProduct:
        """스크래핑된 원시 데이터를 구조화된 모델로 변환"""

        # 기본 정보 변환
        product_info = ProductInfo(
            product_code=raw_data.get('product_code', ''),
            product_name=raw_data.get('product_name', ''),
            insurance_type=self._detect_insurance_type(raw_data.get('product_name', ''))
        )

        # 가입 자격 변환
        eligibility = EligibilityInfo(
            age_range=AgeRange(
                min_age=raw_data.get('min_age', 19),
                max_age=raw_data.get('max_age', 65)
            )
        )

        # 계약 정보 변환
        contract_info = ContractInfo(
            coverage_period=CoverageType.WHOLE_LIFE,
            payment_period=PaymentPeriod.WHOLE_LIFE,
            payment_methods=[PaymentMethod.MONTHLY]
        )

        # 보장 정보 변환
        main_coverage = []
        if 'coverage_details' in raw_data:
            for coverage in raw_data['coverage_details']:
                main_coverage.append(CoverageDetail(**coverage))

        # 보험료 정보 변환
        premium_data = []
        if 'premium_info' in raw_data:
            premium_data = self.validator.normalize_premium_data(raw_data['premium_info'])

        return InsuranceProduct(
            product_info=product_info,
            eligibility=eligibility,
            contract_info=contract_info,
            main_coverage=main_coverage,
            premium_data=premium_data,
            scraped_at=datetime.now(),
            urls=[raw_data.get('url', '')]
        )

    def _detect_insurance_type(self, product_name: str) -> InsuranceType:
        """상품명에서 보험 유형 추정"""
        name_lower = product_name.lower()

        if '암' in product_name:
            return InsuranceType.CANCER
        elif '건강' in product_name:
            return InsuranceType.HEALTH
        elif '정기' in product_name:
            return InsuranceType.TERM
        elif '연금' in product_name:
            return InsuranceType.ANNUITY
        else:
            return InsuranceType.HEALTH  # 기본값

def main():
    """스키마 테스트"""

    # 샘플 데이터로 테스트
    sample_data = {
        "product_code": "ON_PD_KC_01",
        "product_name": "KB 착한암보험 무배당",
        "insurance_type": InsuranceType.CANCER,
        "company_name": "KB라이프생명",
        "min_age": 19,
        "max_age": 65,
        "coverage_details": [
            {
                "coverage_name": "암진단급여금",
                "coverage_amount": 1000.0,
                "coverage_type": "주계약",
                "description": "암 진단 시 지급"
            }
        ],
        "premium_info": [
            {
                "age": 30,
                "gender": "남성",
                "premium_amount": 50000.0,
                "payment_method": "월납"
            }
        ],
        "scraped_at": datetime.now(),
        "url": "https://www.kblife.co.kr/insurance-product/productDetails.do?linkCd=ON_PD_KC_01"
    }

    try:
        transformer = DataTransformer()
        product = transformer.transform_scraped_data(sample_data)

        print("스키마 검증 성공!")
        print(f"상품명: {product.product_info.product_name}")
        print(f"보험 유형: {product.product_info.insurance_type}")
        print(f"보장 개수: {len(product.main_coverage)}")
        print(f"보험료 데이터: {len(product.premium_data)}개")

        # JSON 출력 테스트
        import json
        product_json = product.json(ensure_ascii=False, indent=2)
        print("\nJSON 출력 테스트 성공!")

    except Exception as e:
        print(f"스키마 테스트 실패: {e}")

if __name__ == "__main__":
    main()