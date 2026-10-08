@echo off
REM تشغيل اختبارات المشروع (unittest) مع ترميز UTF-8، والنتائج في data\testrun.log
cd /d "%~dp0.."
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set INST_PBKDF2_ITERATIONS=1000
echo ===== test run started ===== > data\testrun.log
python -m unittest discover -s tests -t . -v >> data\testrun.log 2>&1
echo ===== exit code %ERRORLEVEL% ===== >> data\testrun.log
