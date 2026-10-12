@echo off
rem Compare two sessions in Obsidian: compare.bat 3 7  (session numbers from the dashboard)
rem Writes Compare\S0003 vs S0007.md in the Tennis notes. Any pair can also be compared
rem in outputs\dashboard.html without this.
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
if "%~2"=="" (
  set /p A=First session number: 
  set /p B=Second session number: 
) else (
  set A=%~1
  set B=%~2
)
.venv\Scripts\python.exe scripts\update_stats.py --compare %A% %B%
pause
