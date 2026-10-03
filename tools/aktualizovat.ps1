param(
  [string]$ZipUrl = "https://github.com/Peta01/election-monitor/archive/refs/heads/main.zip",
  [string]$ZipPath = "",
  [string]$Root = ""
)

$ErrorActionPreference = "Stop"
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$work = Join-Path $env:TEMP ("election-monitor-update-" + [guid]::NewGuid().ToString("N"))

try {
  if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
    Write-Host "Aplikace prave bezi. Zavrete okno SPUSTIT.bat a spustte aktualizaci znovu." -ForegroundColor Yellow
    exit 2
  }

  New-Item -ItemType Directory -Path $work | Out-Null
  $zip = $ZipPath
  if (-not $zip) {
    $zip = Join-Path $work "update.zip"
    Write-Host "Stahuji nejnovejsi verzi z GitHubu..."
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zip -UseBasicParsing
  }

  Write-Host "Rozbaluji..."
  $extract = Join-Path $work "x"
  Expand-Archive -Path $zip -DestinationPath $extract -Force
  $source = Get-ChildItem -Path $extract -Directory | Where-Object { Test-Path (Join-Path $_.FullName "pyproject.toml") } | Select-Object -First 1
  if (-not $source) { throw "Stazeny archiv neobsahuje projekt." }

  # Zaloha databaze pro pripad potizi
  $db = Join-Path $Root "data\election_monitor.sqlite3"
  if (Test-Path $db) {
    $backupDir = Join-Path $Root "data\zaloha"
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    Copy-Item $db (Join-Path $backupDir "election_monitor-$stamp.sqlite3")
    Write-Host "Zaloha databaze ulozena do data\zaloha."
  }

  # Data a virtualni prostredi zustavaji beze zmeny; AKTUALIZOVAT.bat se za behu neprepisuje
  Write-Host "Kopiruji nove soubory..."
  robocopy $source.FullName $Root /E /XD data .venv .git /XF AKTUALIZOVAT.bat /NFL /NDL /NJH /NJS /NP | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "Kopirovani souboru selhalo (robocopy $LASTEXITCODE)." }

  $python = Join-Path $Root ".venv\Scripts\python.exe"
  if (-not (Test-Path $python)) { throw "Aplikace neni nainstalovana. Spustte nejdriv INSTALOVAT.bat." }
  Write-Host "Aktualizuji knihovny..."
  & $python -m pip install -e $Root --quiet --disable-pip-version-check
  if ($LASTEXITCODE -ne 0) { throw "Aktualizace knihoven selhala." }

  Write-Host "Aktualizace dokoncena." -ForegroundColor Green
  exit 0
}
catch {
  Write-Host "CHYBA: $($_.Exception.Message)" -ForegroundColor Red
  exit 1
}
finally {
  if (Test-Path $work) { Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue }
}
