@echo off
REM توليد البيانات التجريبية (النتائج في data\seed.log)
cd /d "%~dp0.."
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo ==== seed started ==== > data\seed.log
python tools\seed.py >> data\seed.log 2>&1
echo ==== exit code %ERRORLEVEL% ==== >> data\seed.log
