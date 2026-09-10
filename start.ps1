# TransformerAI — üç servisi birden başlatır.
#
# Kullanım (proje kökünden):
#     .\start.ps1              # üç servisi ayrı pencerelerde başlat
#     .\start.ps1 -Check       # sadece durum kontrolü yap, başlatma
#     .\start.ps1 -Stop        # çalışan servisleri durdur
#
# Neden betik? Her oturuma üç terminal açıp üç komut yazmakla başlıyorduk.
# Bu, hem zaman kaybı hem de "hangi servis kapalıydı?" hatalarının kaynağı.

param(
    [switch]$Check,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

$services = @(
    @{ Name = "Python / ML";      Port = 8000; Url = "http://localhost:8000/health" }
    @{ Name = ".NET / Bakim";     Port = 5080; Url = "http://localhost:5080/health" }
    @{ Name = "React / Arayuz";   Port = 5173; Url = "http://localhost:5173/" }
)

function Test-Service($url) {
    try {
        $r = Invoke-WebRequest -Uri $url -TimeoutSec 3 -UseBasicParsing
        return $r.StatusCode
    } catch {
        return $null
    }
}

function Show-Status {
    Write-Host ""
    Write-Host "Servis durumu:" -ForegroundColor Cyan
    foreach ($s in $services) {
        $code = Test-Service $s.Url
        if ($code) {
            Write-Host ("  [OK]    {0,-16} :{1}" -f $s.Name, $s.Port) -ForegroundColor Green
        } else {
            Write-Host ("  [KAPALI] {0,-15} :{1}" -f $s.Name, $s.Port) -ForegroundColor Yellow
        }
    }
    Write-Host ""
}

if ($Stop) {
    Write-Host "Servisler durduruluyor..." -ForegroundColor Cyan
    Get-Process -Name "TransformerAI.Maintenance.Api" -ErrorAction SilentlyContinue |
        Stop-Process -Force
    # Python ve node: yalnizca bu projenin portlarini dinleyenler
    foreach ($port in 8000, 5173) {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($conn) {
            Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Seconds 2
    Show-Status
    exit 0
}

if ($Check) {
    Show-Status
    exit 0
}

# --- Baslat ----------------------------------------------------------------
Write-Host "TransformerAI baslatiliyor..." -ForegroundColor Cyan

$venv = Join-Path $root "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venv)) {
    Write-Host "HATA: backend\.venv bulunamadi. Once kurulum yapin:" -ForegroundColor Red
    Write-Host "  cd backend; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt"
    exit 1
}

# 1) Python / ML  — --reload: kod degisince kendini yeniler
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 --reload"
) -WindowStyle Normal

# 2) .NET / Bakim
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\maintenance\TransformerAI.Maintenance.Api'; dotnet run --urls http://localhost:5080"
) -WindowStyle Normal

# 3) React / Arayuz
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\frontend'; npm run dev"
) -WindowStyle Normal

Write-Host "Uc pencere acildi. Servislerin ayaga kalkmasi ~20 saniye surer." -ForegroundColor Cyan
Start-Sleep -Seconds 22
Show-Status
Write-Host "Arayuz: http://localhost:5173" -ForegroundColor Green
Write-Host "API dokumantasyonu: http://localhost:8000/docs" -ForegroundColor Green
