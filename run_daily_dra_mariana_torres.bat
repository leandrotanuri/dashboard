@echo off
set "DIR=%~dp0."
echo ===== %date% %time% ===== >> "%DIR%\output\log_dra_mariana_torres.txt"
python "%DIR%\tools\daily_dra_mariana_torres.py" >> "%DIR%\output\log_dra_mariana_torres.txt" 2>&1
