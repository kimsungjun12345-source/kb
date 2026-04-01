# Helper PowerShell script to install Playwright and run the smoke test
# If Playwright installation or run fails (common on Windows when C build tools are missing),
# this script will fall back to running the Selenium-based smoke scraper so you still get results.
# Usage: Right-click -> Run with PowerShell, or from an activated PS you can run: .\run_playwright.ps1

# Activate venv if exists
if (Test-Path -Path ".\.venv\Scripts\Activate.ps1") {
    Write-Host "Activating venv..."
    . .\.venv\Scripts\Activate.ps1
} else {
    Write-Host "No .venv found - running in current environment"
}

function Ensure-Outputs {
    $outDir = Join-Path -Path (Get-Location) -ChildPath 'outputs'
    if (-not (Test-Path $outDir)) {
        New-Item -ItemType Directory -Path $outDir | Out-Null
    }
    return $outDir
}

$outDir = Ensure-Outputs

Write-Host "Upgrading pip/tools..."
python -m pip install --upgrade pip setuptools wheel

$playwrightSucceeded = $false
try {
    Write-Host "Installing Playwright only (lightweight)..."
    python -m pip install -r .\requirements_playwright.txt -q

    Write-Host "Installing Playwright browser binaries (chromium)..."
    python -m playwright install chromium -q

    Write-Host "Running smoke test (Playwright)..."
    python .\kb_yg01_playwright_scraper.py --smoke --out "$($outDir)\kb_yg01_smoke_test_playwright.json"
    $playwrightSucceeded = $true
    Write-Host "Playwright run completed. Output: $($outDir)\kb_yg01_smoke_test_playwright.json"
}
catch {
    Write-Host "Playwright install/run failed: $($_.Exception.Message)"
    Write-Host "Falling back to Selenium-based scraper..."
}

if (-not $playwrightSucceeded) {
    try {
        Write-Host "Ensuring Selenium requirements are installed..."
        # Install minimal selenium deps if not already present
        python -m pip install selenium webdriver-manager chromedriver-autoinstaller -q

        Write-Host "Running Selenium-based smoke test..."
        python .\kb_yg01_detailed_scraper.py --smoke --out "$($outDir)\kb_yg01_smoke_test_selenium.json"
        Write-Host "Selenium run completed. Output: $($outDir)\kb_yg01_smoke_test_selenium.json"
    }
    catch {
        Write-Host "Fallback Selenium run failed: $($_.Exception.Message)"
        Write-Host "Please share the console output here so I can diagnose further."
    }
}

Write-Host "All done. Check the outputs folder for generated JSON(s):"
Get-ChildItem -Path $outDir -Filter 'kb_yg01_smoke_test*' | Select-Object FullName, LastWriteTime | Format-Table -AutoSize
