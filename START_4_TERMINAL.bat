@echo off
chcp 65001 >nul
title Market Pulse - 4 Terminal Launcher
setlocal enabledelayedexpansion

:: ===========================================================================
::  Chay 4 app trong 4 CUA SO TERMINAL RIENG (ban goc - muot nhat cho bang gia).
:: ===========================================================================

set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "DIR_BANGGIA=%ROOT%price-board"

:: --- Chon Python CO Flask ---
set "PYEXE="
py -3.12 -c "import flask" >nul 2>&1 && set "PYEXE=py -3.12"
if not defined PYEXE ( python -c "import flask" >nul 2>&1 && set "PYEXE=python" )
if not defined PYEXE ( py -c "import flask" >nul 2>&1 && set "PYEXE=py" )
if not defined PYEXE (
    echo [LOI] Khong tim thay Python co Flask. Cai:
    echo    py -3.12 -m pip install -r "%ROOT%EconoPulse-VN\requirements.txt"
    pause
    exit /b 1
)
echo Interpreter: %PYEXE%
echo Bang gia dir: !DIR_BANGGIA!
echo.

:: --- Terminal 1: BANG GIA (:5555) - mo TRUOC ---
echo [1/4] Bang gia realtime  =^> http://localhost:5555
start "MP - BANG GIA 5555" /d "!DIR_BANGGIA!" cmd /k "chcp 65001 >nul & %PYEXE% server.py"
timeout /t 3 >nul

:: --- Terminal 2: CRAWL DATA (:5000) ---
echo [2/4] data-crawler         =^> http://localhost:5000
start "MP - CRAWL DATA 5000" /d "%ROOT%data-crawler" cmd /k "chcp 65001 >nul & %PYEXE% app.py"
timeout /t 2 >nul

:: --- Terminal 3: ECONOLENS (:3333) ---
echo [3/4] EconoLens AI chat  =^> http://localhost:3333
start "MP - ECONOLENS 3333" /d "%ROOT%econolens-chat" cmd /k "chcp 65001 >nul & npm start"
timeout /t 3 >nul

:: --- Terminal 4: GATEWAY (:9999) - MP_NO_SPAWN=1 (khong spawn trung) ---
echo [4/4] Gateway            =^> http://localhost:9999  (MP_NO_SPAWN=1)
start "MP - GATEWAY 9999" /d "%ROOT%EconoPulse-VN" cmd /k "chcp 65001 >nul & set MP_NO_SPAWN=1& %PYEXE% gateway\app.py"

echo.
echo ===========================================================================
echo  Da mo 4 cua so. Cho ~15-20s cho cac app len.
echo  BANG GIA muot nhat: mo tab trinh duyet RIENG  =^> http://localhost:5555
echo  Cong tong hop:                                =^> http://localhost:9999
echo ===========================================================================
echo.
pause
