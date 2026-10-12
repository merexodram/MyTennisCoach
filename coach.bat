@echo off
rem Double-click after analyze.bat.
rem 1. Collects the latest session into outputs\coach\session_NNNN (the "coach pack").
rem 2. If a review has been written there (review.md, coach_input.json), stores it in the
rem    database, in data\reviews and, if configured, in your Obsidian file.
rem 3. Recomputes the metrics of all sessions and rewrites the Obsidian notes and
rem    outputs\dashboard.html.
rem The review itself is written by Claude from the pack: ask "review my last tennis session".
cd /d "%~dp0"
set PYTHONPATH=%~dp0src
.venv\Scripts\python.exe scripts\coach_pack.py %*
.venv\Scripts\python.exe scripts\save_review.py --auto
.venv\Scripts\python.exe scripts\update_stats.py
pause
