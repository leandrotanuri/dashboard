@echo off
set DIR=C:\Users\leand\DOWNLO~1\METAAD~1
echo ===== %date% %time% ===== >> "%DIR%\output\log_all_clients.txt"

C:\Python314\python.exe "%DIR%\tools\fill_all_sheets.py" >> "%DIR%\output\log_all_clients.txt" 2>&1

for /f %%i in ('powershell -command "(Get-Date).DayOfWeek.value__"') do set DOW=%%i
if "%DOW%"=="1" (
    echo Gerando insights semanais... >> "%DIR%\output\log_all_clients.txt"
    C:\Python314\python.exe "%DIR%\tools\generate_insights.py" >> "%DIR%\output\log_all_clients.txt" 2>&1
)
