# Build JARVIS Ring & Hands untuk Windows (one-folder PyInstaller).
# Jalankan dari PowerShell: powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv tidak ditemukan. Pasang uv dari https://docs.astral.sh/uv/ lalu ulangi."
}

uv sync --frozen --extra packaging
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run pyinstaller --noconfirm --clean packaging/jarvis-hands.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Build selesai: dist\jarvis-hands\jarvis-hands.exe"
Write-Host "Model Hand Landmarker sudah dibundel; tidak ada unduhan saat runtime."
