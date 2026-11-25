#!/bin/bash
# Double-click and choose a video: makes the small working copy for the free Colab GPU (docs/COLAB.md).
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
pick_video "$1"
[ -n "$1" ] && [ -f "$1" ] && shift
"$PY" -m mytenniscoach.process "$VIDEO" "$@" --prepare
finish 0
