@echo off
rem Double-click to download every new link listed in data\links.txt
rem (or drag-and-drop is not needed: just edit links.txt, one link per line).
rem You can also run: download.bat "https://..." "https://..."
rem Videos go to data\raw at up to 1080p. Log: outputs\download_log.txt
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup.bat first.
  pause
  exit /b 1
)
if not exist outputs mkdir outputs
if not exist data mkdir data
if not exist data\links.txt (
  echo # One video link per line. Lines starting with # are ignored.> data\links.txt
)
echo == Updating yt-dlp (video sites change often)
.venv\Scripts\python.exe -m pip install -q -U "yt-dlp[default]"
set PYTHONUNBUFFERED=1
echo == Downloading
.venv\Scripts\python.exe scripts\fetch_video.py %* > outputs\download_log.txt 2>&1
type outputs\download_log.txt
echo.
echo Log saved to outputs\download_log.txt
pause
