@echo off
title BLUE_AI Dashboard
echo.
echo  ========================================
echo   BLUE_AI - Bilgisayar Yonetim Paneli
echo  ========================================
echo.
echo  Dashboard baslatiliyor...
echo  Tarayicinizda acin: http://127.0.0.1:8484
echo.
echo  Durdurmak icin bu pencereyi kapatin.
echo.
start http://127.0.0.1:8484
cd /d "C:\BLUE_AI"
python -m blue_ai dashboard
