@echo off
rem Drag a video onto this file to mark the court by hand (fixed camera).
rem Click the court point named in the window title; S skips one you cannot see.
rem Enter saves. Needed once per camera position.
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a video file onto calibrate.bat
  pause
  exit /b 1
)
.venv\Scripts\python.exe scripts\calibrate.py %*
pause
