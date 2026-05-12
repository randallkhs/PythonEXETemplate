#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

find_python() {
  local candidates=(
    "${ACS_AI_IMAGE_REPRODUCER_PYTHON:-}"
    /opt/homebrew/bin/python3.14
    /opt/homebrew/bin/python3.13
    /opt/homebrew/bin/python3.12
    /opt/homebrew/bin/python3
    /usr/local/bin/python3.14
    /usr/local/bin/python3.13
    /usr/local/bin/python3.12
    /usr/local/bin/python3
    python3
  )
  local candidate
  for candidate in "${candidates[@]}"; do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

venv_needs_rebuild() {
  [[ ! -d .venv || ! -x .venv/bin/python ]] && return 0
  .venv/bin/python -c "import PySide6, requests, keyring" >/dev/null 2>&1 || return 0
  return 1
}

PYTHON_BIN="$(find_python)" || {
  echo "No usable Python 3 interpreter found." >&2
  exit 1
}

if venv_needs_rebuild; then
  rm -rf .venv
  "$PYTHON_BIN" -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python main.py
