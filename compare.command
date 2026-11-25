#!/bin/bash
# Compare two sessions in Obsidian: asks for two session numbers (see the dashboard).
source "$(dirname "$0")/scripts/mac_common.sh"
need_setup
A="$1"; B="$2"
[ -n "$A" ] || read -r -p "First session number: " A
[ -n "$B" ] || read -r -p "Second session number: " B
"$PY" scripts/update_stats.py --compare "$A" "$B"
finish 0
