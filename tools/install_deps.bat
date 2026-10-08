@echo off
REM تثبيت متطلبات المرحلة 1 (يُشغَّل مرة واحدة)
cd /d "%~dp0.."
echo ==== install started ==== > data\install.log
python -m pip install --disable-pip-version-check tornado user-agents pywebio==1.8.4 >> data\install.log 2>&1
echo ==== install finished with code %ERRORLEVEL% ==== >> data\install.log
