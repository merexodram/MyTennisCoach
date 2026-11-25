#!/bin/bash
# Double-click and choose a video: click the court corners and yourself once per camera position.
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
n=$(count_videos "$@")
pick_video "$@"
shift "$n"
"$PY" scripts/calibrate.py "$VIDEO" "$@"
finish 0
