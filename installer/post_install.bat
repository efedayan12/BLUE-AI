@echo off
chcp 65001 >nul 2>&1
title BLUE AI - Kurulum Sonrasi Yapilandirma

echo.
echo =========================================================
echo   BLUE AI - Sistem Yapilandirmasi
echo =========================================================
echo.

REM -- 1. Ollama Kontrolu --
echo [1/3] Ollama kontrol ediliyor...

set OLLAMA_FOUND=0
set OLLAMA_EXE=

where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama PATH de bulundu.
    set OLLAMA_FOUND=1
    set OLLAMA_EXE=ollama
    goto start_ollama
)

if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
    echo     [OK] Ollama bulundu: LocalAppData
    set OLLAMA_FOUND=1
    set OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
    goto start_ollama
)

if exist "%ProgramFiles%\Ollama\ollama.exe" (
    echo     [OK] Ollama bulundu: Program Files
    set OLLAMA_FOUND=1
    set OLLAMA_EXE=%ProgramFiles%\Ollama\ollama.exe
    goto start_ollama
)

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama sureci calisiyor.
    set OLLAMA_FOUND=1
    set OLLAMA_EXE=ollama
    goto start_ollama
)

echo.
echo     Ollama bulunamadi. Otomatik kurulum baslatiliyor...
echo     Ollama indiriliyor... Lutfen bekleyin.
echo.

set DOWNLOAD_DIR=%TEMP%\blue_ai_ollama
if not exist "%DOWNLOAD_DIR%" mkdir "%DOWNLOAD_DIR%"
set OLLAMA_INSTALLER=%DOWNLOAD_DIR%\OllamaSetup.exe

powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try{Import-Module BitsTransfer -EA Stop;Start-BitsTransfer -Source 'https://ollama.com/download/OllamaSetup.exe' -Destination '%DOWNLOAD_DIR%\OllamaSetup.exe'}catch{$ProgressPreference='SilentlyContinue';Invoke-WebRequest 'https://ollama.com/download/OllamaSetup.exe' -OutFile '%DOWNLOAD_DIR%\OllamaSetup.exe' -UseBasicParsing}"

if not exist "%OLLAMA_INSTALLER%" (
    echo     HATA: Indirme basarisiz. Manuel: https://ollama.com/download
    goto finish
)

echo     Ollama kuruluyor...
start /wait "" "%OLLAMA_INSTALLER%" /VERYSILENT /NORESTART /SUPPRESSMSGBOXES

set INSTALL_OK=0
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set INSTALL_OK=1
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 set INSTALL_OK=1

if %INSTALL_OK% EQU 1 (
    echo     [OK] Ollama basariyla kuruldu!
    set OLLAMA_FOUND=1
) else (
    echo     Ollama kurulumu tamamlanamadi. Manuel: https://ollama.com/download
)

del /f /q "%OLLAMA_INSTALLER%" >nul 2>&1

:start_ollama
echo.
echo [2/3] Ollama servisi kontrol ediliyor...

if %OLLAMA_FOUND% EQU 0 goto finish

tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | find /I "ollama.exe" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     [OK] Ollama zaten calisiyor.
    goto pull_model
)

echo     Ollama baslatiliyor...
if exist "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe" (
    start "" "%LOCALAPPDATA%\Programs\Ollama\ollama app.exe"
) else (
    start "" ollama serve
)

echo     Servis bekleniyor...
timeout /t 8 /nobreak >nul

:pull_model
echo.
echo [3/3] LLM model kontrol ediliyor...

set OLL_CMD=
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 set OLL_CMD=ollama
if "%OLL_CMD%"=="" (
    if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set OLL_CMD=%LOCALAPPDATA%\Programs\Ollama\ollama.exe
)
if "%OLL_CMD%"=="" (
    echo     Ollama komutu bulunamadi. BLUE AI baslatilinca model indirilecek.
    goto finish
)

"%OLL_CMD%" list 2>nul | find /I "gemma3:1b" >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo     [OK] gemma3:1b modeli zaten mevcut.
    goto finish
)

echo     gemma3:1b modeli indiriliyor (~815 MB)...
"%OLL_CMD%" pull gemma3:1b
if %ERRORLEVEL% EQU 0 (
    echo     [OK] gemma3:1b modeli indirildi!
) else (
    echo     Model indirilemedi. BLUE AI baslatilinca tekrar denenecek.
)

:finish
echo.
echo =========================================================
echo   Kurulum tamamlandi!
echo   BLUE AI yi Masaustu kisayolundan baslatabilirsiniz.
echo =========================================================
echo.
pause