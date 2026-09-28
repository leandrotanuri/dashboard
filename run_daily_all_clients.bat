@echo off
set "DIR=%~dp0."
echo ===== %date% %time% ===== >> "%DIR%\output\log_all_clients.txt"

python "%DIR%\tools\fill_all_sheets.py" >> "%DIR%\output\log_all_clients.txt" 2>&1

for /f %%i in ('powershell -command "(Get-Date).DayOfWeek.value__"') do set DOW=%%i
if "%DOW%"=="1" (
    echo Gerando insights semanais... >> "%DIR%\output\log_all_clients.txt"
    python "%DIR%\tools\generate_insights.py" >> "%DIR%\output\log_all_clients.txt" 2>&1
)
