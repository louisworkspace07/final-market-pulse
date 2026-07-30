@echo off
chcp 65001 >nul
title Market Pulse — Launcher

:: Chi mot lenh: gateway :9999 tu spawn 3 app con (crawl :5000, banggia :5555,
:: econolens :3333). Tat bang Ctrl+C -> app con do gateway spawn chet theo (atexit).

:: Chon interpreter CO flask. Tren may nay 'python' tren PATH la 3.11/3.14 KHONG
:: co flask; flask nam o Python 3.12 (py -3.12). Thu lan luot roi fallback 'python'.
set "PYEXE="
py -3.12 -c "import flask" >nul 2>&1 && set "PYEXE=py -3.12"
if not defined PYEXE ( python -c "import flask" >nul 2>&1 && set "PYEXE=python" )
if not defined PYEXE ( py -c "import flask" >nul 2>&1 && set "PYEXE=py" )
if not defined PYEXE (
    echo [LOI] Khong tim thay Python co Flask. Cai bang:  py -3.12 -m pip install -r market-pulse\requirements.txt
    pause
    exit /b 1
)
echo Dung interpreter: %PYEXE%
%PYEXE% "%~dp0market-pulse\gateway\app.py"

pause
