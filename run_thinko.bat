@echo off
set KMP_DUPLICATE_LIB_OK=TRUE
title Thinko STEM Study Buddy
cd /d "%~dp0"

echo ========================================================
echo                 Thinko STEM Study Buddy
echo ========================================================
echo.

if not exist ".env" (
    echo [.env file not found!]
    echo Copying .env.example to .env ...
    copy .env.example .env >nul
    echo.
    echo Please open .env and add your GEMINI_API_KEY.
    notepad .env
    echo.
    pause
)

echo Starting Thinko Gemini Live Server...
echo Press Ctrl+C in this window to stop.
echo.
python main_live.py

pause
