# TransformerAI — demo verisini bilinen başlangıç durumuna döndürür.
#
# Kullanım (proje kökünden):
#     .\scripts\reset-demo.ps1            # yerel kurulum (start.ps1 ile çalışan)
#     .\scripts\reset-demo.ps1 -Docker    # docker compose kurulumu
#
# Neden? İki bilgisayarda çalışırken veritabanları git'e girmediği için
# ayrıştı: birinde test girilmiş, birinde parola değiştirilmiş, birinde
# iş emri kapatılmış. Demo ya da sunum öncesi "herkes aynı yerden başlasın"
# için tek komut.
#
# NE SİLİNİR: iki veritabanı (ölçümler, testler, iş emirleri, analizler,
# parolalar). NE SİLİNMEZ: kod, eğitilmiş model.
# Sonuç: 10 demo trafo, 9 demo hesap, geçici parolalar Demo-<sicil>.

param(
    [switch]$Docker,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent

if (-not $Force) {
    Write-Host "Bu islem demo veritabanlarini SILER (olcumler, testler, is emirleri, parolalar)." -ForegroundColor Yellow
    $answer = Read-Host "Devam etmek icin 'evet' yazin"
    if ($answer -ne "evet") { Write-Host "Iptal edildi."; exit 1 }
}

if ($Docker) {
    Push-Location $root
    try {
        # -v: birimleri de siler. Container açılınca Python demo filoyu,
        # .NET migration + demo hesapları yeniden kurar.
        docker compose down -v
        docker compose up -d --build
        Write-Host "Docker demo verisi sifirlandi: http://localhost:8080" -ForegroundColor Green
    } finally {
        Pop-Location
    }
    exit 0
}

# --- Yerel kurulum -----------------------------------------------------------
& (Join-Path $root "start.ps1") -Stop

$files = @(
    (Join-Path $root "backend\dga.db"),
    (Join-Path $root "maintenance\TransformerAI.Maintenance.Api\maintenance.db")
)
foreach ($f in $files) {
    foreach ($suffix in "", "-wal", "-shm") {
        if (Test-Path "$f$suffix") { Remove-Item "$f$suffix" -Force; Write-Host "silindi: $f$suffix" }
    }
}

Write-Host "Demo filo yukleniyor..." -ForegroundColor Cyan
Push-Location (Join-Path $root "backend")
try {
    & ".\.venv\Scripts\python.exe" -m app.ml.seed | Select-Object -Last 3
} finally {
    Pop-Location
}

# .NET veritabanını ayrıca kurmaya gerek yok: servis açılırken migration'ları
# uygular ve demo hesaplarına geçici parola atar.
& (Join-Path $root "start.ps1")
Write-Host "Yerel demo verisi sifirlandi. Gecici parolalar: Demo-<sicil> (ornegin Demo-10001)." -ForegroundColor Green
