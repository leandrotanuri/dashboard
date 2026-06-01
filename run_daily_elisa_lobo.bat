@echo off
cd /d "C:\Users\leand\Downloads\MetaAds Relatórios"
python tools\daily_elisa_lobo.py >> output\log_elisa_lobo.txt 2>&1
