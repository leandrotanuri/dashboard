@echo off
cd /d "%~dp0"
python tools\daily_clinica_prc.py >> output\log_clinica_prc.txt 2>&1
