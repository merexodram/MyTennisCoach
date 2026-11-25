#!/bin/bash
# Double-click after analyze.command:
# 1. collects the latest session into outputs/coach/session_NNNN (the coach pack),
# 2. stores a written review (review.md, coach_input.json) if there is one,
# 3. recomputes the metrics of all sessions and rewrites the Obsidian notes and outputs/dashboard.html.
# The review itself is written by Claude from the pack: ask "review my last tennis session".
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
"$PY" scripts/coach_pack.py "$@"
"$PY" scripts/save_review.py --auto
"$PY" scripts/update_stats.py
finish 0
