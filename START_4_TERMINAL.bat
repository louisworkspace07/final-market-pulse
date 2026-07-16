@echo off
chcp 65001 >nul
title Market Pulse - 4 Terminal Launcher
setlocal enabledelayedexpansion

:: ===========================================================================
::  Chay 4 app trong 4 CUA SO TERMINAL RIENG (ban goc - muot nhat cho bang gia).
::  File nay THUAN ASCII: thu muc "Test tool dua an" co dau tieng Viet nen KHONG
::  go truc tiep (cmd doc .bat theo codepage he thong -> hong path). Thay vao do
::  tu DO thu muc bang wildcard "Test*".
:: ===========================================================================

set "ROOT=%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

:: --- Tu do thu muc "Test tool dua an" (tranh go ky tu tieng Viet trong .bat) ---
set "DIR_BANGGIA="
for /d %%D in ("%ROOT%Test*") do set "DIR_BANGGIA=%%D"
if not defined DIR_BANGGIA (
    echo [LOI] Khong tim thay thu muc bang gia ^(Test tool ...^) trong %ROOT%
    pause
    exit /b 1
)

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
echo [2/4] Crawl Data         =^> http://localhost:5000
start "MP - CRAWL DATA 5000" /d "%ROOT%Crawl Data" cmd /k "chcp 65001 >nul & %PYEXE% app.py"
timeout /t 2 >nul

:: --- Terminal 3: ECONOLENS (:3333) ---
echo [3/4] EconoLens AI chat  =^> http://localhost:3333
start "MP - ECONOLENS 3333" /d "%ROOT%AI Analyze Economic" cmd /k "chcp 65001 >nul & npm start"
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
