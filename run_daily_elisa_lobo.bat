@echo off
cd /d "%~dp0"
python tools\daily_elisa_lobo.py >> output\log_elisa_lobo.txt 2>&1
