@echo off
chcp 65001 >nul
title DeskCat App

echo ====================================
echo   DeskCat - Phone App Desktop Debug
echo ====================================
echo.

:: activate venv if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: check kivy
python -c "import kivy" 2>nul
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

:: launch
echo Starting DeskCat App...
python main.py

pause
