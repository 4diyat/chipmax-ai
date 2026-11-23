@echo off
setlocal DisableDelayedExpansion
rem Jalankan dari direktori mana pun; tidak memasang dependensi otomatis.
pushd "%~dp0" || exit /b 1
set "PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Virtual environment belum tersedia. Jalankan perintah berikut di "%CD%":
    echo   py -3.11 -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    popd
    exit /b 1
)

"%PYTHON%" -m jarvis_hands %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
