@echo off
set DIR=C:\Users\leand\DOWNLO~1\METAAD~1
echo ===== %date% %time% ===== >> "%DIR%\output\log_dra_mariana_torres.txt"
C:\Python314\python.exe "%DIR%\tools\daily_dra_mariana_torres.py" >> "%DIR%\output\log_dra_mariana_torres.txt" 2>&1
