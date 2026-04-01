@echo off
echo ===================================
echo KB Life 스크래퍼 Chrome 확장 설치
echo ===================================
echo.

echo 1. 크롬 브라우저를 열고 다음 주소로 이동:
echo    chrome://extensions/
echo.

echo 2. 우측 상단의 "개발자 모드" 활성화
echo.

echo 3. "압축해제된 확장 프로그램을 로드합니다" 클릭
echo.

echo 4. 다음 폴더 선택:
echo    %~dp0sanhak-hyeopryuk\chrome_extension
echo.

echo 5. 확장 프로그램이 설치되면 KB Life 사이트 접속
echo.

echo 6. 개발자도구(F12) 열고 콘솔에서 스크래퍼 실행:
echo    window.__scrapeHealth('337600104', 'e건강보험_일반심사')
echo.

pause