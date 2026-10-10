@echo off
rem Drag a video file onto this file to analyse it.
rem Result: outputs\<name>_annotated.mp4, a session in data\tennis.duckdb,
rem and a log in outputs\<name>_log.txt.
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a video file onto analyze.bat, or run: analyze.bat path\to\video.mp4 [options]
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist outputs mkdir outputs
set PYTHONPATH=%~dp0src
set PYTHONUNBUFFERED=1
.venv\Scripts\python.exe -m mytenniscoach.process %* > "outputs\%~n1_log.txt" 2>&1
type "outputs\%~n1_log.txt"
echo.
echo Log saved to outputs\%~n1_log.txt
pause
