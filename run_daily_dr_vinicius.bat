@echo off
cd /d "%~dp0"
python tools\daily_dr_vinicius.py >> output\log_dr_vinicius.txt 2>&1
