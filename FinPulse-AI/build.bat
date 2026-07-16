@echo off
cd /d "%~dp0"
echo ==================================================
echo  Dong goi FinPulse AI thanh 1 file .exe (onefile)
echo ==================================================
python -m PyInstaller --noconfirm --onefile --windowed --name FinPulseAI ^
  --add-data "renderer;renderer" ^
  app_pyqt.py
echo.
echo Xong! File chay duy nhat: dist\FinPulseAI.exe
pause
