# Shared by the .command launchers on macOS. Not run on its own.
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"
export PYTHONPATH="$ROOT/src"
export PYTHONUNBUFFERED=1
export PYTORCH_ENABLE_MPS_FALLBACK=1
# Homebrew tools (ffmpeg) when Terminal was opened without the login profile.
for d in /opt/homebrew/bin /usr/local/bin; do
  case ":$PATH:" in *":$d:"*) ;; *) [ -d "$d" ] && PATH="$d:$PATH" ;; esac
done
export PATH
PY="$ROOT/.venv/bin/python"

need_setup() {
  if [ ! -x "$PY" ]; then
    echo "Run setup.command first (double-click it)."
    finish 1
  fi
}

finish() {
  echo
  read -r -p "Press Return to close this window." _
  exit "${1:-0}"
}

# Videos from the command line, or picked in a Finder window (several parts of one
# recording can be selected together). Sets VIDEOS (array) and VIDEO (the first).
pick_video() {
  VIDEOS=()
  while [ -n "$1" ] && [ -f "$1" ]; do VIDEOS+=("$1"); shift; done
  if [ ${#VIDEOS[@]} -eq 0 ]; then
    local picked
    picked="$(osascript \
      -e 'set fs to choose file with prompt "Choose the video (a recording split into parts: select all parts)" of type {"public.movie"} with multiple selections allowed' \
      -e 'set out to ""' -e 'repeat with f in fs' -e 'set out to out & POSIX path of f & linefeed' -e 'end repeat' \
      -e 'return out' 2>/dev/null)"
    while IFS= read -r line; do [ -n "$line" ] && VIDEOS+=("$line"); done <<< "$picked"
  fi
  if [ ${#VIDEOS[@]} -eq 0 ]; then
    echo "No video chosen."
    finish 1
  fi
  VIDEO="${VIDEOS[0]}"
}

# How many leading arguments were video files (to shift them away).
count_videos() {
  local n=0
  while [ -n "$1" ] && [ -f "$1" ]; do n=$((n + 1)); shift; done
  echo $n
}
