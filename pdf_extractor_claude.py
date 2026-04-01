"""
KB 보험상품 PDF 텍스트 추출 및 Claude API 분석기
다운로드한 PDF 문서에서 텍스트를 추출하고 Claude API를 활용하여 구조화된 정보로 변환
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

try:
    import PyPDF2
    import pdfplumber
    import fitz  # PyMuPDF
except ImportError:
    print("PDF 라이브러리 설치 필요: pip install PyPDF2 pdfplumber PyMuPDF")

try:
    import anthropic
except ImportError:
    print("Claude API 라이브러리 설치 필요: pip install anthropic")

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_extractor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PDFTextExtractor:
    """PDF 텍스트 추출기"""

    def __init__(self, pdf_dir: str = "downloads"):
        self.pdf_dir = Path(pdf_dir)

    def extract_with_pypdf2(self, pdf_path: str) -> str:
        """PyPDF2를 사용한 텍스트 추출"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
                return text
        except Exception as e:
            logger.error(f"PyPDF2 추출 실패: {e}")
            return ""

    def extract_with_pdfplumber(self, pdf_path: str) -> Dict[str, Any]:
        """pdfplumber를 사용한 고급 텍스트 추출 (테이블 포함)"""
        try:
            text_data = {
                "text": "",
                "tables": [],
                "metadata": {}
            }

            with pdfplumber.open(pdf_path) as pdf:
                text_data["metadata"] = {
                    "pages": len(pdf.pages),
                    "title": pdf.metadata.get('Title', ''),
                    "author": pdf.metadata.get('Author', ''),
                    "subject": pdf.metadata.get('Subject', '')
                }

                for page_num, page in enumerate(pdf.pages, 1):
                    # 텍스트 추출
                    page_text = page.extract_text()
                    if page_text:
                        text_data["text"] += f"\n--- 페이지 {page_num} ---\n"
                        text_data["text"] += page_text

                    # 테이블 추출
                    tables = page.extract_tables()
                    for table_num, table in enumerate(tables, 1):
                        text_data["tables"].append({
                            "page": page_num,
                            "table_num": table_num,
                            "data": table
                        })
                        logger.info(f"테이블 발견: 페이지 {page_num}, 테이블 {table_num}")

            return text_data
        except Exception as e:
            logger.error(f"pdfplumber 추출 실패: {e}")
            return {"text": "", "tables": [], "metadata": {}}

    def extract_with_pymupdf(self, pdf_path: str) -> str:
        """PyMuPDF를 사용한 텍스트 추출"""
        try:
            text = ""
            doc = fitz.open(pdf_path)
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
            return text
        except Exception as e:
            logger.error(f"PyMuPDF 추출 실패: {e}")
            return ""

    def extract_all_methods(self, pdf_path: str) -> Dict[str, Any]:
        """모든 방법으로 텍스트 추출하여 최상의 결과 선택"""
        logger.info(f"PDF 텍스트 추출: {pdf_path}")

        # pdfplumber (가장 고급 기능)
        plumber_result = self.extract_with_pdfplumber(pdf_path)

        # PyPDF2
        pypdf2_text = self.extract_with_pypdf2(pdf_path)

        # PyMuPDF
        pymupdf_text = self.extract_with_pymupdf(pdf_path)

        # 최상의 결과 선택 (가장 긴 텍스트)
        texts = {
            "pdfplumber": plumber_result["text"],
            "pypdf2": pypdf2_text,
            "pymupdf": pymupdf_text
        }

        best_method = max(texts.keys(), key=lambda k: len(texts[k]))
        best_text = texts[best_method]

        logger.info(f"최적 추출 방법: {best_method} ({len(best_text)} 글자)")

        return {
            "text": best_text,
            "tables": plumber_result.get("tables", []),
            "metadata": plumber_result.get("metadata", {}),
            "extraction_methods": {
                "best_method": best_method,
                "text_lengths": {k: len(v) for k, v in texts.items()}
            }
        }

class ClaudeAnalyzer:
    """Claude API를 사용한 PDF 내용 분석기"""

    def __init__(self, api_key: Optional[str] = None):
        # API 키 설정 (환경변수에서 가져오거나 직접 설정)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("Claude API 키가 설정되지 않았습니다. ANTHROPIC_API_KEY 환경변수를 설정하세요.")
            self.client = None
        else:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Claude 클라이언트 초기화 실패: {e}")
                self.client = None

    def analyze_insurance_document(self, text: str, doc_type: str = "보험약관") -> Dict[str, Any]:
        """보험 문서 분석"""
        if not self.client:
            logger.error("Claude API 클라이언트가 초기화되지 않았습니다.")
            return {"error": "Claude API 클라이언트 없음"}

        # 문서 유형별 프롬프트
        prompts = {
            "약관": """다음은 보험 약관 문서입니다. 아래 내용을 JSON 형태로 구조화해서 추출해주세요:

1. 보험상품명
2. 보험료 납입 관련 정보 (납입방법, 납입주기 등)
3. 보장내용 (주요 보장항목과 보장금액)
4. 보험금 지급 조건
5. 특약 정보 (있는 경우)
6. 계약자의 의무사항
7. 중요한 제외사항
8. 보험료 할인 조건 (있는 경우)

문서 내용:
""",
            "상품설명서": """다음은 보험 상품설명서입니다. 아래 내용을 JSON 형태로 구조화해서 추출해주세요:

1. 상품명과 상품코드
2. 상품의 주요 특징
3. 가입 가능 연령
4. 보장기간 및 납입기간
5. 주요 보장내용과 보장금액
6. 보험료 정보 (예시금액이 있다면)
7. 특약 정보
8. 유의사항

문서 내용:
""",
            "요약서": """다음은 보험 상품요약서입니다. 핵심 정보를 JSON 형태로 구조화해서 추출해주세요:

1. 상품명
2. 핵심 보장내용 요약
3. 보험료 정보
4. 중요 특징 및 혜택
5. 주요 제외사항
6. 가입 시 주의사항

문서 내용:
"""
        }

        prompt = prompts.get(doc_type, prompts["약관"]) + text[:10000]  # 텍스트 길이 제한

        try:
            logger.info(f"{doc_type} 문서 Claude 분석 시작...")

            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4000,
                temperature=0.1,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            analysis_result = response.content[0].text
            logger.info(f"Claude 분석 완료: {len(analysis_result)} 글자")

            # JSON 파싱 시도
            try:
                if analysis_result.strip().startswith('{'):
                    structured_data = json.loads(analysis_result)
                else:
                    # JSON이 아닌 경우 텍스트로 저장
                    structured_data = {"analysis": analysis_result}
            except json.JSONDecodeError:
                structured_data = {"analysis": analysis_result}

            return {
                "success": True,
                "structured_data": structured_data,
                "raw_analysis": analysis_result,
                "tokens_used": response.usage.input_tokens + response.usage.output_tokens if hasattr(response, 'usage') else 0
            }

        except Exception as e:
            logger.error(f"Claude API 분석 실패: {e}")
            return {"success": False, "error": str(e)}

class PDFProcessorPipeline:
    """PDF 처리 파이프라인 - 추출부터 분석까지 통합"""

    def __init__(self, pdf_dir: str = "downloads", output_dir: str = "extracted_data"):
        self.extractor = PDFTextExtractor(pdf_dir)
        self.analyzer = ClaudeAnalyzer()
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """단일 PDF 처리"""
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            logger.error(f"PDF 파일 없음: {pdf_path}")
            return {"error": "파일 없음"}

        logger.info(f"PDF 처리 시작: {pdf_path.name}")

        # 1. 텍스트 추출
        extraction_result = self.extractor.extract_all_methods(str(pdf_path))

        if not extraction_result["text"]:
            logger.warning(f"텍스트 추출 실패: {pdf_path}")
            return {"error": "텍스트 추출 실패"}

        # 2. 문서 유형 추정
        doc_type = "약관"
        if "상품설명서" in pdf_path.name or "guide" in pdf_path.name.lower():
            doc_type = "상품설명서"
        elif "요약서" in pdf_path.name or "summary" in pdf_path.name.lower():
            doc_type = "요약서"

        # 3. Claude 분석
        analysis_result = self.analyzer.analyze_insurance_document(
            extraction_result["text"], doc_type
        )

        # 4. 결과 통합
        processed_data = {
            "pdf_file": str(pdf_path),
            "processed_at": datetime.now().isoformat(),
            "document_type": doc_type,
            "extraction": extraction_result,
            "analysis": analysis_result
        }

        # 5. 결과 저장
        output_file = self.output_dir / f"{pdf_path.stem}_analyzed.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, ensure_ascii=False, indent=2)

        logger.info(f"처리 완료: {output_file}")
        return processed_data

    def process_all_pdfs(self) -> List[Dict[str, Any]]:
        """모든 PDF 처리"""
        pdf_files = list(self.extractor.pdf_dir.glob("*.pdf"))

        if not pdf_files:
            logger.warning("처리할 PDF 파일이 없습니다.")
            return []

        logger.info(f"총 {len(pdf_files)}개 PDF 파일 처리 시작")

        results = []
        for pdf_file in pdf_files:
            try:
                result = self.process_pdf(pdf_file)
                results.append(result)
            except Exception as e:
                logger.error(f"PDF 처리 중 오류 {pdf_file}: {e}")
                results.append({"pdf_file": str(pdf_file), "error": str(e)})

        # 전체 결과 요약 저장
        summary_file = self.output_dir / f"processing_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        summary_data = {
            "processed_at": datetime.now().isoformat(),
            "total_files": len(pdf_files),
            "successful": len([r for r in results if "error" not in r]),
            "failed": len([r for r in results if "error" in r]),
            "results": results
        }

        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

        logger.info(f"전체 처리 완료: {summary_file}")
        return results

def main():
    """메인 실행 함수"""
    try:
        print("KB 보험상품 PDF 텍스트 추출 및 분석을 시작합니다...")

        # 파이프라인 초기화
        processor = PDFProcessorPipeline()

        # 모든 PDF 처리
        results = processor.process_all_pdfs()

        if results:
            successful = len([r for r in results if "error" not in r])
            failed = len([r for r in results if "error" in r])

            print(f"\n처리 완료!")
            print(f"성공: {successful}개")
            print(f"실패: {failed}개")
            print(f"결과는 extracted_data 폴더에 저장되었습니다.")
        else:
            print("\n처리할 PDF 파일이 없습니다.")
            print("downloads 폴더에 PDF 파일을 확인해주세요.")

    except Exception as e:
        print(f"실행 중 오류: {e}")
        logger.error(f"메인 실행 중 오류: {e}")

if __name__ == "__main__":
    main()