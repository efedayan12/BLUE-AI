@echo off
title BLUE_AI Kurulum
echo.
echo  ====================================
echo   BLUE_AI - Masaustu Kisayolu Olustur
echo  ====================================
echo.

:: EXE yolunu bul
set "EXE_PATH=%~dp0dist\BLUE_AI\BLUE_AI.exe"

if not exist "%EXE_PATH%" (
    echo [HATA] BLUE_AI.exe bulunamadi!
    echo Once "pyinstaller blue_ai.spec" ile build edin.
    pause
    exit /b 1
)

:: Masaustune kisayol olustur
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\BLUE_AI.lnk"

powershell -NoProfile -Command ^
    "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%SHORTCUT%'); $sc.TargetPath = '%EXE_PATH%'; $sc.WorkingDirectory = '%~dp0dist\BLUE_AI'; $sc.Description = 'BLUE AI - Akilli Bilgisayar Asistani'; $sc.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo [OK] Masaustune BLUE_AI kisayolu olusturuldu!
    echo.
    echo Cift tiklayarak BLUE_AI'yi baslatabilirsiniz.
) else (
    echo [HATA] Kisayol olusturulamadi.
)

echo.
pause
