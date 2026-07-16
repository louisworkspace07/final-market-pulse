@echo off
cd /d "%~dp0"
echo Dang dong cac instance FinPulse cu...
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*app_pyqt*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" 2>nul
echo Khoi dong FinPulse...
python app_pyqt.py
pause
