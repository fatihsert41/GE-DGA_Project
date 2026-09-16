# TransformerAI — üç servisi birden başlatır.
#
# Kullanım (proje kökünden):
#     .\start.ps1              # üç servisi ayrı pencerelerde başlat
#     .\start.ps1 -Check       # sadece durum kontrolü yap, başlatma
#     .\start.ps1 -Stop        # çalışan servisleri durdur
#
# Neden betik? Her oturuma üç terminal açıp üç komut yazmakla başlıyorduk.
# Bu, hem zaman kaybı hem de "hangi servis kapalıydı?" hatalarının kaynağı.
#
# Yerel çalışma GELİŞTİRME ortamındadır: .NET launch profili Development,
# Python TRANSFORMERAI_ENV tanımsız = development. Bu yüzden imza anahtarı
# gerekmez. Üretim/Docker kurulumu için bkz. .env.example.

param(
    [switch]$Check,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Arayuz TLS ile aciliyor mu? (certs/ varsa Vite https dinler)
$useTls = (Test-Path (Join-Path $root "certs\dev-cert.pem")) -and
          (Test-Path (Join-Path $root "certs\dev-key.pem"))
$uiUrl = if ($useTls) { "https://localhost:5173/" } else { "http://localhost:5173/" }

# Kendinden imzali sertifikayi KABUL ET. Bu yalnizca bu yerel baslatma
# betiginin kendi saglik yoklamasi icin; uygulama kodunda boyle bir sey YOK.
if ($useTls) {
    [System.Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }
    # Windows PowerShell 5.1 varsayilan olarak eski TLS surumlerini deniyor;
    # Vite yalnizca TLS 1.2/1.3 konusuyor, aradaki el sikisma dusuyordu.
    [System.Net.ServicePointManager]::SecurityProtocol =
        [System.Net.SecurityProtocolType]::Tls12 -bor [System.Net.SecurityProtocolType]::Tls11
}

$services = @(
    @{ Name = "Python / ML";      Port = 8000; Url = "http://localhost:8000/health" }
    @{ Name = ".NET / Bakim";     Port = 5080; Url = "http://localhost:5080/health" }
    @{ Name = "React / Arayuz";   Port = 5173; Url = $uiUrl }
)

function Test-Service($url) {
    # https icin curl.exe: Windows PowerShell 5.1'in Invoke-WebRequest'i
    # kendinden imzali sertifikali TLS baglantisinda el sikismayi
    # tamamlayamiyor (curl ayni adrese 200 donerken). curl.exe Windows 10'dan
    # beri isletim sistemiyle geliyor; -k sertifika dogrulamasini atlar ve
    # bu YALNIZCA bu yerel saglik yoklamasi icindir.
    if ($url -like "https://*") {
        $code = & curl.exe -k -s -o NUL -w "%{http_code}" --max-time 3 $url 2>$null
        if ($code -match '^[1-5]\d\d$' -and $code -ne "000") { return [int]$code }
        return $null
    }
    try {
        $r = Invoke-WebRequest -Uri $url -TimeoutSec 3 -UseBasicParsing
        return $r.StatusCode
    } catch {
        return $null
    }
}

# Bir portu dinleyen BÜTÜN süreçler. Get-NetTCPConnection bazen boş dönüyor
# (IPv4/IPv6 ayrımı), netstat her dinleyiciyi gösteriyor.
function Get-PortListeners($port) {
    netstat -ano | Select-String ":$port\s" | Where-Object { $_.Line -match "LISTENING" } |
        ForEach-Object { [int](($_.Line.Trim() -split "\s+")[-1]) } | Sort-Object -Unique
}

function Show-Status {
    Write-Host ""
    Write-Host "Servis durumu:" -ForegroundColor Cyan
    foreach ($s in $services) {
        $code = Test-Service $s.Url
        $listeners = @(Get-PortListeners $s.Port)
        if ($code) {
            Write-Host ("  [OK]    {0,-16} :{1}" -f $s.Name, $s.Port) -ForegroundColor Green
        } else {
            Write-Host ("  [KAPALI] {0,-15} :{1}" -f $s.Name, $s.Port) -ForegroundColor Yellow
        }
        # Aynı portta birden çok dinleyici: biri eski kodu çalıştıran yetim
        # süreçtir ve istekler ona da gider. Sessiz kalırsa "kod değişti ama
        # servis eski davranıyor" hatası saatlerce aranır (15 Eyl'de yaşandı).
        if ($listeners.Count -gt 1) {
            Write-Host ("          UYARI: :{0} portunu {1} surec dinliyor (PID {2}). " -f `
                $s.Port, $listeners.Count, ($listeners -join ", ")) -ForegroundColor Red
            Write-Host "          Biri eski kodla calisiyor olabilir. '.\start.ps1 -Stop' calistirin." -ForegroundColor Red
        }
    }
    Write-Host ""
}

function Stop-Tree($processId) {
    # /T: süreç AĞACINI durdurur. uvicorn --reload'da portu dinleyen süreç
    # yeniden başlatıcıdır; yalnız onu öldürmek işçi süreci yetim bırakır ve
    # yetim işçi portu tutmaya devam eder.
    taskkill /PID $processId /T /F 2>$null | Out-Null
}

if ($Stop) {
    Write-Host "Servisler durduruluyor..." -ForegroundColor Cyan
    Get-Process -Name "TransformerAI.Maintenance.Api" -ErrorAction SilentlyContinue |
        Stop-Process -Force

    # 1) Bu projenin uvicorn süreç ağaçları
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.CommandLine -match 'uvicorn\s+app\.main:app' } |
        ForEach-Object { Stop-Tree $_.ProcessId }

    # 2) Portları dinleyen ne kaldıysa (ağacıyla)
    foreach ($port in 8000, 5173) {
        foreach ($listenerPid in @(Get-PortListeners $port)) { Stop-Tree $listenerPid }
    }
    Start-Sleep -Seconds 2

    # 3) Yetim uvicorn işçileri: üst süreci ÖLMÜŞ multiprocessing çocukları.
    #    Yalnızca 8000 hâlâ dinleniyorsa ve yalnızca üst süreci gerçekten
    #    yoksa durdurulur — başka projelerin Python süreçlerine dokunmamak için.
    if (@(Get-PortListeners 8000).Count -gt 0) {
        Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
            Where-Object { $_.CommandLine -match 'spawn_main\(parent_pid=(\d+)' } |
            ForEach-Object {
                $parentId = [int]$Matches[1]
                if (-not (Get-Process -Id $parentId -ErrorAction SilentlyContinue)) {
                    Write-Host "  yetim uvicorn iscisi durduruluyor: PID $($_.ProcessId) (ust surec $parentId yok)" -ForegroundColor Yellow
                    Stop-Tree $_.ProcessId
                }
            }
        Start-Sleep -Seconds 2
    }

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

# Port zaten doluysa ikinci bir sunucu AÇMA: Windows aynı porta iki dinleyiciye
# izin verir ve istekler eski koda da gider. Önce durdur, sonra başlat.
$busy = @()
foreach ($s in $services) {
    if (@(Get-PortListeners $s.Port).Count -gt 0) { $busy += $s }
}
if ($busy.Count -gt 0) {
    Write-Host "Su portlar zaten kullanimda:" -ForegroundColor Yellow
    $busy | ForEach-Object { Write-Host ("  {0,-16} :{1}" -f $_.Name, $_.Port) -ForegroundColor Yellow }
    Write-Host "Ikinci bir sunucu acmak yerine once '.\start.ps1 -Stop' calistirin." -ForegroundColor Yellow
    Show-Status
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
# npm.cmd, npm DEGIL: "npm" aslinda npm.ps1 betigine gider ve betik
# politikasi Restricted olan bilgisayarlarda (yeni Windows kurulumlarinin
# varsayilani) engellenir.
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd '$root\frontend'; npm.cmd run dev"
) -WindowStyle Normal

Write-Host "Uc pencere acildi. Servislerin ayaga kalkmasi ~20 saniye surer." -ForegroundColor Cyan
Start-Sleep -Seconds 22
Show-Status
Write-Host "Arayuz: $uiUrl" -ForegroundColor Green
if ($useTls) {
    Write-Host "  (kendinden imzali sertifika: tarayici bir kez uyarir -> Gelismis, Devam et)" -ForegroundColor DarkGray
}
Write-Host "API dokumantasyonu: http://localhost:8000/docs" -ForegroundColor Green
