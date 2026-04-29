#!/usr/bin/env bash
# Gate 0 — verify required tooling. Prints install commands for anything missing.
# Does NOT install automatically. The skill should ask the user before installing.

set -u

VENV_HINT="${HOME}/.venv-pitch"
MISSING=()
HINTS=()

# python
if ! command -v python3 >/dev/null 2>&1; then
  MISSING+=("python3")
  HINTS+=("Install Python 3.9+: https://www.python.org/downloads/")
fi

# Resolve which python to check pip packages against
if [ -x "${VENV_HINT}/bin/python" ]; then
  PY="${VENV_HINT}/bin/python"
  PIP="${VENV_HINT}/bin/pip"
else
  PY="$(command -v python3 || echo python3)"
  PIP="$(command -v pip3 || echo pip3)"
fi

# Check pip packages via importable modules
need_module() {
  local mod="$1"
  local pip_name="$2"
  local hint="$3"
  if ! "$PY" -c "import ${mod}" >/dev/null 2>&1; then
    MISSING+=("${pip_name}")
    HINTS+=("${hint}")
  fi
}

need_module "imageio_ffmpeg"  "imageio-ffmpeg"  "ffmpeg via pip — bundled binary, no system install"
need_module "playwright"       "playwright"      "Playwright — browser automation (also need: playwright install chromium)"
need_module "faster_whisper"   "faster-whisper"  "Whisper transcription"
# python-docx is optional — only flagged if the user wants a submission .docx

# Playwright browser is separate from the pip package
if "$PY" -c "import playwright" >/dev/null 2>&1; then
  if ! ls "${HOME}/Library/Caches/ms-playwright/chromium"* >/dev/null 2>&1 \
   && ! ls "${HOME}/.cache/ms-playwright/chromium"* >/dev/null 2>&1; then
    MISSING+=("chromium-browser")
    HINTS+=("Run: ${PY} -m playwright install chromium")
  fi
fi

if [ "${#MISSING[@]}" -eq 0 ]; then
  echo "ok — all tooling present"
  echo "  python: $PY"
  exit 0
fi

echo "missing tooling:"
for i in "${!MISSING[@]}"; do
  echo "  - ${MISSING[$i]}"
  echo "      ${HINTS[$i]}"
done

echo ""
echo "Recommended install (isolated venv at ${VENV_HINT}):"
echo "  python3 -m venv ${VENV_HINT}"
echo "  source ${VENV_HINT}/bin/activate"
echo "  pip install playwright imageio-ffmpeg faster-whisper python-docx"
echo "  playwright install chromium"
echo ""
echo "Or via system pip (not recommended on macOS with system python):"
echo "  pip install --user playwright imageio-ffmpeg faster-whisper python-docx"

exit 1
