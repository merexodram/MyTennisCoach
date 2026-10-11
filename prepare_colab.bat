@echo off
rem Drag a video onto this file to get it ready for tracking on a free Colab GPU.
rem It makes the 1080p working copy and puts it, with the court file, into
rem outputs\for_colab. Upload that folder's contents to Google Drive:
rem   My Drive\MyTennisCoach\in
rem Then run notebooks\track_on_colab.ipynb in Colab. See docs\COLAB.md.
cd /d "%~dp0"
if "%~1"=="" (
  echo Drag a video file onto prepare_colab.bat
  pause
  exit /b 1
)
set PYTHONPATH=%~dp0src
.venv\Scripts\python.exe -m mytenniscoach.process %* --prepare
pause
