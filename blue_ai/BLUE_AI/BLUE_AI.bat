@echo off
title BLUE_AI
cd /d "C:\BLUE_AI"
pythonw -m blue_ai.app 2>nul || python -m blue_ai.app
