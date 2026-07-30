@echo off
chcp 65001 >nul
title Market Pulse — Stop All

echo ============================================================
echo   MARKET PULSE — Dung tat ca dich vu
echo ============================================================
echo.

echo [1/4] Dung market-pulse gateway (port 9999)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":9999 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [2/4] Dung data-crawler (port 5000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [3/4] Dung Bang gia realtime (port 5555)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5555 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo [4/4] Dung EconoLens (port 3333)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3333 "') do (
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo Xong! Tat ca dich vu da dung.
pause
