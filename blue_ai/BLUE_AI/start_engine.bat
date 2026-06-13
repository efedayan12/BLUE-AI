@echo off
title BLUE_AI Engine
echo.
echo  ========================================
echo   BLUE_AI - Yapay Zeka Motoru
echo  ========================================
echo.
echo  Motor baslatiliyor...
echo  Tum plugin'ler aktif, kurallar otomatik.
echo  Durdurmak icin Ctrl+C basin.
echo.
cd /d "C:\BLUE_AI"
python -m blue_ai run
pause
