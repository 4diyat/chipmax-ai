@echo off
REM Build JARVIS Ring & Hands untuk Windows.
REM Memerlukan uv terpasang dan koneksi untuk sinkronisasi dependensi pertama kali.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows.ps1"
if errorlevel 1 exit /b %errorlevel%
