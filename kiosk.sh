#!/usr/bin/env bash
# Launch the dashboard in Chromium kiosk mode, pointing at the shell.
# Usage:  ./kiosk.sh http://192.168.1.10:30080
#   or:   SHELL_URL=http://192.168.1.10:30080 ./kiosk.sh
set -euo pipefail
SHELL_URL="${1:-${SHELL_URL:-http://localhost:30080}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# Pick whichever Chromium binary the Pi has.
CHROMIUM="$(command -v chromium-browser || command -v chromium || command -v google-chrome || true)"
[ -n "$CHROMIUM" ] || { echo "chromium not found — apt install chromium"; exit 1; }
exec "$CHROMIUM" --kiosk --noerrdialogs --no-first-run --disable-translate \
  --disable-features=TranslateUI "file://${HERE}/index.html?shell=${SHELL_URL}"
