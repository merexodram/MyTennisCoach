@echo off
rem Double-click this file. It only reads system information and writes
rem prereq_report.txt in the repository root. Nothing is installed or changed.
cd /d "%~dp0.."
set R=prereq_report.txt
echo MyTennisCoach prerequisite report > %R%
echo %DATE% %TIME% >> %R%
for %%S in ("git --version" "where git" "python --version" "where python" "py -0p" "conda --version" "conda env list" "where ffmpeg" "ffmpeg -version" "where yt-dlp" "nvidia-smi" "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv" "wmic cpu get name" "wmic computersystem get TotalPhysicalMemory" "wmic logicaldisk get caption,freespace,size") do (
  echo. >> %R%
  echo ===== %%~S >> %R%
  cmd /c %%~S >> %R% 2>&1
)
echo Report written to %CD%\%R%
timeout /t 5
