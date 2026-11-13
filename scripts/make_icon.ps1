<#
    make_icon.ps1 - Ricostruisce app.ico dall'icona master.

    Uso (dalla radice del pacchetto):
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_icon.ps1

    Sorgente: scripts\icon-master-256.png (pappagallo verde + barre audio,
    256x256 con trasparenza). Ogni misura viene ridimensionata dal master
    con interpolazione di alta qualita'.

    Produce app.ico con 10 misure (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
    nella radice del pacchetto e, con -Preview, le anteprime PNG in work/.

    Se app.ico esiste gia' non viene toccata: usare -Force per sostituirla.
    Nessuna dipendenza esterna: usa solo System.Drawing di Windows.
#>

param(
    [string]$OutDir = (Split-Path -Parent $PSScriptRoot),
    [string]$Master = (Join-Path $PSScriptRoot "icon-master-256.png"),
    [switch]$Preview,
    [switch]$Force
)

Add-Type -AssemblyName System.Drawing

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Master -PathType Leaf)) {
    "Master non trovato: $Master"
    exit 1
}

$icoPath = Join-Path $OutDir "app.ico"
if ((Test-Path -LiteralPath $icoPath) -and (-not $Force)) {
    "app.ico esiste gia': nessuna modifica (usare -Force per sostituirla)."
    exit 0
}

# Il master viene clonato subito: il file resta libero e si puo' chiudere.
$loaded = [System.Drawing.Bitmap]::FromFile((Resolve-Path -LiteralPath $Master).Path)
try {
    # Clone diretto: nessun passaggio nel pipeline grafico, pixel intatti.
    $clone = $loaded.Clone()
}
finally {
    $loaded.Dispose()
}

$sizes = @(16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
$images = [System.Collections.Generic.List[byte[]]]::new()
$previewDir = Join-Path $OutDir "work"

foreach ($sz in $sizes) {
    if (($sz -eq $clone.Width) -and ($sz -eq $clone.Height)) {
        # Misura nativa del master: copia esatta, senza ricampionare.
        $bmp = $clone.Clone()
    } else {
        $bmp = [System.Drawing.Bitmap]::new($sz, $sz)
        $bmp.SetResolution(96, 96)
        $g = [System.Drawing.Graphics]::FromImage($bmp)
        $g.SmoothingMode      = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
        $g.InterpolationMode  = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $g.PixelOffsetMode    = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
        $g.Clear([System.Drawing.Color]::Transparent)
        $g.DrawImage($clone, 0, 0, $sz, $sz)
        $g.Dispose()
    }

    $ms = [System.IO.MemoryStream]::new()
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $images.Add($ms.ToArray())
    $ms.Dispose()

    if ($Preview -and ($sz -in @(16, 24, 32, 48, 128, 256))) {
        if (-not (Test-Path -LiteralPath $previewDir)) {
            New-Item -ItemType Directory -Path $previewDir | Out-Null
        }
        $bmp.Save((Join-Path $previewDir "icon-$sz.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    }

    $bmp.Dispose()
}
$clone.Dispose()

$fs = [System.IO.File]::Create($icoPath)
$bw = [System.IO.BinaryWriter]::new($fs)
try {
    $bw.Write([UInt16]0)
    $bw.Write([UInt16]1)
    $bw.Write([UInt16]$sizes.Count)

    $offset = 6 + (16 * $sizes.Count)
    for ($i = 0; $i -lt $sizes.Count; $i++) {
        $sz = $sizes[$i]
        $data = $images[$i]
        $dim = if ($sz -ge 256) { 0 } else { $sz }
        $bw.Write([Byte]$dim)            # larghezza (0 = 256)
        $bw.Write([Byte]$dim)            # altezza (0 = 256)
        $bw.Write([Byte]0)               # palette
        $bw.Write([Byte]0)               # riservato
        $bw.Write([UInt16]1)             # piani colore
        $bw.Write([UInt16]32)            # bit per pixel
        $bw.Write([UInt32]$data.Length)
        $bw.Write([UInt32]$offset)
        $offset += $data.Length
    }
    foreach ($data in $images) { $bw.Write($data) }
}
finally {
    $bw.Close()
    $fs.Close()
}

$info = Get-Item $icoPath
"ICO creato: $($info.FullName) ($($info.Length) byte, $($sizes.Count) dimensioni)"
