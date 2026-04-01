import asyncio
from kb_insurance_scraper import KBInsuranceScraper

async def test_single_case():
    """단일 케이스 테스트"""
    scraper = KBInsuranceScraper()

    # 30세 남성으로 테스트
    result = await scraper.scrape_insurance_data(30, "남성")

    if result:
        print("테스트 성공!")
        print(f"수집된 데이터: {result}")
    else:
        print("테스트 실패!")

if __name__ == "__main__":
    asyncio.run(test_single_case())