@echo off
cd /d "C:\Users\leand\Downloads\MetaAds Relatórios"
python tools\daily_dr_vinicius.py >> output\log_dr_vinicius.txt 2>&1
