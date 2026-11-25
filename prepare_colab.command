#!/bin/bash
# Double-click and choose a video: makes the small working copy for the free Colab GPU (docs/COLAB.md).
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
n=$(count_videos "$@")
pick_video "$@"
shift "$n"
"$PY" -m mytenniscoach.process "${VIDEOS[@]}" "$@" --prepare
finish 0
