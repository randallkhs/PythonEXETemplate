#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

python_has_tk() {
  local candidate="$1"
  [[ -n "$candidate" && -x "$candidate" ]] || return 1
  "$candidate" -c "import tkinter" >/dev/null 2>&1
}

python_tk_is_modern() {
  local candidate="$1"
  python_has_tk "$candidate" || return 1
  "$candidate" -c "
import tkinter as tk

root = tk.Tk()
level = str(root.tk.call('info', 'patchlevel'))
root.destroy()
parts = level.split('.')
major = int(parts[0]) if parts and parts[0].isdigit() else 0
minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
raise SystemExit(0 if (major, minor) >= (8, 6) else 1)
" >/dev/null 2>&1
}

find_python_with_tk() {
  local candidates=(
    "${ACS_IMAGE_CONVERTER_PYTHON:-}"
    /opt/homebrew/bin/python3.14
    /opt/homebrew/bin/python3.13
    /opt/homebrew/bin/python3.12
    /opt/homebrew/bin/python3
    /usr/local/bin/python3.14
    /usr/local/bin/python3.13
    /usr/local/bin/python3.12
    /usr/local/bin/python3
    /usr/bin/python3
    python3
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if python_tk_is_modern "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  for candidate in "${candidates[@]}"; do
    if python_has_tk "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

venv_python_version() {
  .venv/bin/python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'
}

selected_python_version() {
  "$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))'
}

venv_needs_rebuild() {
  [[ ! -d .venv || ! -x .venv/bin/python ]] && return 0
  python_has_tk .venv/bin/python || return 0
  python_tk_is_modern .venv/bin/python || return 0
  [[ "$(venv_python_version)" == "$(selected_python_version)" ]] || return 0
  return 1
}

PYTHON_BIN="$(find_python_with_tk)" || {
  cat <<'EOF' >&2
No Python interpreter with Tkinter was found.
On macOS with Homebrew Python, install Tk support, for example:
  brew install python-tk@3.14
Then run this script again.
EOF
  exit 1
}

if ! python_tk_is_modern "$PYTHON_BIN"; then
  export TK_SILENCE_DEPRECATION=1
  echo "Warning: using a legacy macOS Tk build. Install Homebrew Tk support for a reliable GUI:" >&2
  echo "  brew install python-tk@3.14" >&2
fi

if venv_needs_rebuild; then
  rm -rf .venv
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python main.py
