@echo off
chcp 65001 >nul
title Market Pulse — Stop All

echo ============================================================
echo   MARKET PULSE — Dung tat ca dich vu
echo ============================================================
echo.

echo [1/5] Dung EconoPulse-VN gateway (port 9999)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":9999 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [2/5] Dung data-crawler (port 5000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [3/5] Dung Bang gia realtime (port 5555)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5555 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [4/5] Dung EconoLens (port 3333)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3333 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [5/5] Dung FinPulse-AI (Electron + Python bridge)...
taskkill /IM electron.exe /F >nul 2>&1
taskkill /IM "FinPulse-AI.exe" /F >nul 2>&1
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*chrome_bridge*' -or $_.CommandLine -like '*app_pyqt*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1

echo.
echo Xong! Tat ca dich vu da dung.
pause
