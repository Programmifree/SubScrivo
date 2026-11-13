<#
    make_shortcut.ps1 - Crea o ripara "Avvia SubScrivo.lnk".

    Un file .lnk contiene percorsi assoluti: se il pacchetto viene copiato
    su un altro PC (o spostato in un'altra cartella), il vecchio
    collegamento punterebbe a un percorso inesistente e mostrerebbe
    l'icona vuota. Questo script verifica target, cartella di lavoro e
    icona, e ricrea il collegamento solo quando non corrispondono.

    Uso (dalla radice del pacchetto):
        powershell -NoProfile -ExecutionPolicy Bypass -File scripts\make_shortcut.ps1
        powershell ... -Root "C:\percorso\SubScrivo"

    Non fa nulla se nella cartella non c'e' SubScrivo.cmd.
    Silenzioso e senza errori bloccanti: viene chiamato a ogni avvio.
#>

param(
    [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$ErrorActionPreference = 'Stop'

try {
    $rootPath = [System.IO.Path]::GetFullPath($Root).TrimEnd('\')
} catch {
    exit 0
}

$lnkPath = Join-Path $rootPath 'Avvia SubScrivo.lnk'
$target  = Join-Path $rootPath 'SubScrivo.cmd'
$icon    = Join-Path $rootPath 'app.ico'

# Se il launcher non c'e', non e' il pacchetto giusto: non toccare nulla.
if (-not (Test-Path -LiteralPath $target -PathType Leaf)) {
    exit 0
}

$hasIcon = Test-Path -LiteralPath $icon -PathType Leaf
$expectedIcon = if ($hasIcon) { "$icon,0" } else { $null }

$shell = New-Object -ComObject WScript.Shell
$needsFix = $true

if (Test-Path -LiteralPath $lnkPath -PathType Leaf) {
    try {
        $shortcut = $shell.CreateShortcut($lnkPath)

        $sameTarget = [string]::Equals(
            $shortcut.TargetPath,
            $target,
            [System.StringComparison]::OrdinalIgnoreCase)

        $sameWorkDir = [string]::Equals(
            ($shortcut.WorkingDirectory).TrimEnd('\'),
            $rootPath,
            [System.StringComparison]::OrdinalIgnoreCase)

        # Se l'icona non c'e' non ha senso pretendere un IconLocation.
        $sameIcon = $true
        if ($hasIcon) {
            $sameIcon = [string]::Equals(
                $shortcut.IconLocation,
                $expectedIcon,
                [System.StringComparison]::OrdinalIgnoreCase)
        }

        $needsFix = -not ($sameTarget -and $sameWorkDir -and $sameIcon)
    } catch {
        $needsFix = $true
    }
}

if (-not $needsFix) {
    exit 0
}

$shortcut = $shell.CreateShortcut($lnkPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $rootPath
$shortcut.Description = 'SubScrivo - Speech to Text'
if ($hasIcon) {
    $shortcut.IconLocation = $expectedIcon
}
$shortcut.Save()
exit 0
