<#
.SYNOPSIS
Instala Auto HATS en Windows (usuario actual).

Uso:
  powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/Llop-Estepari/auto-hats/main/install.ps1 | iex"
  powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/Llop-Estepari/auto-hats/main/install.ps1 | iex" -ArgumentList "-Uninstall"
#>
param(
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$Repo = "Llop-Estepari/auto-hats"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Auto-HATS"
$StartMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$StartShortcut = Join-Path $StartMenuDir "Auto HATS.lnk"
$DesktopDir = [Environment]::GetFolderPath("Desktop")
$DesktopShortcut = Join-Path $DesktopDir "Auto HATS.lnk"

function Remove-FromUserPath([string]$dir) {
    $current = [Environment]::GetEnvironmentVariable("Path", "User")
    if (-not $current) { return }
    $parts = $current -split ";" | Where-Object { $_ -and ($_ -ne $dir) }
    [Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User")
}

if ($Uninstall) {
    if (Test-Path $InstallDir) { Remove-Item $InstallDir -Recurse -Force }
    if (Test-Path $StartShortcut) { Remove-Item $StartShortcut -Force }
    if (Test-Path $DesktopShortcut) { Remove-Item $DesktopShortcut -Force }
    Remove-FromUserPath $InstallDir
    Write-Host "Auto HATS desinstalado."
    exit 0
}

$apiUrl = "https://api.github.com/repos/$Repo/releases/latest"
$release = Invoke-RestMethod -Uri $apiUrl -Headers @{ "User-Agent" = "auto-hats-installer" }
$asset = $release.assets | Where-Object { $_.name -like "Auto-HATS-windows-x64.zip" } | Select-Object -First 1
if (-not $asset) {
    throw "No se encontró el ZIP de Windows en la última release."
}

$temp = Join-Path $env:TEMP "auto-hats-install"
if (Test-Path $temp) { Remove-Item $temp -Recurse -Force }
New-Item -ItemType Directory -Path $temp | Out-Null
$zip = Join-Path $temp $asset.name

Write-Host "==> Descargando $($asset.name)"
Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip

if (Test-Path $InstallDir) {
    Remove-Item $InstallDir -Recurse -Force
}
New-Item -ItemType Directory -Path $InstallDir | Out-Null
Write-Host "==> Extrayendo"
Expand-Archive -Path $zip -DestinationPath $InstallDir -Force

$exe = Join-Path $InstallDir "auto-hats.exe"
if (-not (Test-Path $exe)) {
    throw "No se encontró auto-hats.exe tras la extracción."
}

Write-Host "==> Creando acceso en el menú Inicio"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($StartShortcut)
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $InstallDir
$shortcut.IconLocation = "$exe,0"
$shortcut.Save()

# Acceso directo en el escritorio (opcional pero útil)
$dsc = $wsh.CreateShortcut($DesktopShortcut)
$dsc.TargetPath = $exe
$dsc.WorkingDirectory = $InstallDir
$dsc.IconLocation = "$exe,0"
$dsc.Save()

# Add to user PATH if missing
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if ($userPath -notlike "*$InstallDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$InstallDir", "User")
}

Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Auto HATS instalado correctamente."
Write-Host "Búscalo en el menú Inicio o ejecuta: auto-hats"
PY