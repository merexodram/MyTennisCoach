@echo off
rem Double-click to install everything MyTennisCoach needs on this machine.
rem Progress is shown here and saved to setup_log.txt in this folder.
cd /d "%~dp0"
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo == Installing ffmpeg with winget
  winget install --id Gyan.FFmpeg -e
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Transcript -Path setup_log.txt -Force | Out-Null; try { & .\scripts\setup_windows.ps1 } catch { Write-Host ('SETUP FAILED: ' + $_) } finally { Stop-Transcript | Out-Null }"
echo.
echo Finished. Log saved to %CD%\setup_log.txt
pause
