@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo First run: py -3.12 setup_demo.py
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run_demo.py --open
if errorlevel 1 pause
