<#
    make_release.ps1 - Prepara il pacchetto distribuibile di SubScrivo.

    Copia solo cio' che serve all'utente finale, escludendo i dati runtime
    (work/, build/, dist/), il collegamento .lnk con percorsi assoluti e le
    cache di Python. Produce:

        dist\SubScrivo-<versione>-win64\        cartella pronta all'uso
        dist\SubScrivo-<versione>-win64.zip     archivio da caricare in Release
        dist\SubScrivo-<versione>-win64.zip.sha256

    Uso (dalla radice del progetto):
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_release.ps1
        powershell ... -Version 1.0.0
        powershell ... -SkipZip          # solo la cartella, niente archivio

    Prerequisiti: python\, ffmpeg\, native\, models\ e native\silero-vad\
    gia' presenti (vedi docs\BUILD.md).
#>

param(
    [string]$Version = '1.0.0',
    [string]$Root = (Split-Path -Parent $PSScriptRoot),
    [string]$OutDir = '',
    [switch]$SkipZip
)

$ErrorActionPreference = 'Stop'

$rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
if (-not $OutDir) { $OutDir = Join-Path $rootPath 'dist' }
$outPath = [System.IO.Path]::GetFullPath($OutDir).TrimEnd('\')

$name = "SubScrivo-$Version-win64"
$stage = Join-Path $outPath $name
$zip = "$stage.zip"

# ---------------------------------------------------------------------------
# 1. Controlli: il pacchetto deve essere completo prima di copiarlo
# ---------------------------------------------------------------------------
$required = @(
    'SubScrivo.cmd',
    'SubScrivo-console.cmd',
    'app.ico',
    'LICENSE',
    'portable.ini',
    'app\main.py',
    'python\python.exe',
    'ffmpeg\bin\ffmpeg.exe',
    'ffmpeg\bin\ffprobe.exe',
    'native\transcribe.dll',
    'native\silero-vad\silero_encoder_v5.onnx',
    'native\silero-vad\silero_decoder_v5.onnx',
    'models\gguf\parakeet-ultra-Q8_0.gguf',
    'models\embeddings\wespeaker-voxceleb-resnet34-LM.onnx'
)

$missing = @(
    $required | Where-Object { -not (Test-Path -LiteralPath (Join-Path $rootPath $_) -PathType Leaf) }
)
if ($missing.Count -gt 0) {
    Write-Host 'ERRORE: pacchetto incompleto, mancano:' -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host 'Vedi docs\BUILD.md per preparare i componenti mancanti.'
    exit 1
}

# I launcher devono restare con fine riga CRLF.
foreach ($cmd in @('SubScrivo.cmd', 'SubScrivo-console.cmd', 'Test-drag-and-drop.cmd')) {
    $text = [System.IO.File]::ReadAllText((Join-Path $rootPath $cmd))
    $loneLf = ([regex]::Matches($text, "(?<!`r)`n")).Count
    if ($loneLf -gt 0) {
        Write-Host "ERRORE: $cmd contiene $loneLf righe con LF senza CR." -ForegroundColor Red
        Write-Host 'I file .cmd devono usare CRLF: convertili prima di creare la Release.'
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 2. Preparazione della cartella di destinazione
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $outPath | Out-Null
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }

Write-Host "Creo $stage ..."
$robocopyArgs = @(
    $rootPath, $stage,
    '/E', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS', '/NP',
    '/XD', 'work', 'build', 'dist', '.git', '__pycache__', '.pytest_cache',
    '/XF', 'Avvia SubScrivo.lnk', '*.pyc', '*.pyo', '.gitignore', '.gitkeep',
    'RIPRENDI-DA-QUI.md', 'RELEASE_NOTES.md'
)
& robocopy @robocopyArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    Write-Host "ERRORE: robocopy ha fallito (codice $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}

# work/ e build/ sono dati runtime: se un test li ha creati nella cartella di
# destinazione vanno tolti prima di comprimere.
foreach ($runtime in @('work', 'build')) {
    $stray = Join-Path $stage $runtime
    if (Test-Path -LiteralPath $stray) { Remove-Item -LiteralPath $stray -Recurse -Force }
}

# ---------------------------------------------------------------------------
# 3. Rapporto finale
# ---------------------------------------------------------------------------
$measure = Get-ChildItem -LiteralPath $stage -Recurse -File |
    Measure-Object -Property Length -Sum
$sizeMb = [math]::Round($measure.Sum / 1MB, 1)
Write-Host ("Cartella pronta: {0} ({1} MB, {2} file)" -f $stage, $sizeMb, $measure.Count)

if ($SkipZip) { exit 0 }

# ---------------------------------------------------------------------------
# 4. Archivio ZIP + checksum SHA-256
# ---------------------------------------------------------------------------
# Alcune DLL native hanno timestamp 1970 (epoch Unix), che il formato ZIP non
# supporta (minimo 1980): Compress-Archive fallirebbe. Si normalizza la copia.
$epochFloor = [datetime]::new(2026, 1, 1, 0, 0, 0, [System.DateTimeKind]::Utc)
Get-ChildItem -LiteralPath $stage -Recurse -File |
    Where-Object { $_.LastWriteTimeUtc.Year -lt 1980 } |
    ForEach-Object { $_.LastWriteTimeUtc = $epochFloor }

Write-Host "Comprimo in $zip ..."
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip -CompressionLevel Optimal
$zipMb = [math]::Round((Get-Item -LiteralPath $zip).Length / 1MB, 1)

$hash = (Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$zip.sha256" -Value "$hash  $name.zip" -Encoding ASCII

Write-Host ("Archivio pronto: {0} ({1} MB)" -f $zip, $zipMb)
Write-Host ("SHA-256: {0}" -f $hash)
exit 0
