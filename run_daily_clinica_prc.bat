@echo off
cd /d "C:\Users\leand\Downloads\MetaAds Relatórios"
python tools\daily_clinica_prc.py >> output\log_clinica_prc.txt 2>&1
