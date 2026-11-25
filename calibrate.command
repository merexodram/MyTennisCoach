#!/bin/bash
# Double-click and choose a video: click the court corners and yourself once per camera position.
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
pick_video "$1"
[ -n "$1" ] && [ -f "$1" ] && shift
"$PY" scripts/calibrate.py "$VIDEO" "$@"
finish 0
