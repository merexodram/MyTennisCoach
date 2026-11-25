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

# A video from the command line, or picked in a Finder window.
pick_video() {
  if [ -n "$1" ] && [ -f "$1" ]; then
    VIDEO="$1"
    return 0
  fi
  VIDEO="$(osascript -e 'POSIX path of (choose file with prompt "Choose the video" of type {"public.movie"})' 2>/dev/null)"
  if [ -z "$VIDEO" ]; then
    echo "No video chosen."
    finish 1
  fi
}
