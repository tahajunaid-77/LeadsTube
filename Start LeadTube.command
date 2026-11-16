#!/bin/bash
# Double-click this file in Finder to open LeadTube.
# The first time, it sets everything up by itself (about 2-3 minutes).
# Keep this window open while you use the dashboard; close it to stop.

cd "$(dirname "$0")" || exit 1
URL="http://localhost:3030"

echo ""
echo "  LeadTube"
echo "  --------"

if ! command -v node >/dev/null 2>&1; then
  echo "  Node.js is missing. Install it from https://nodejs.org (LTS), then double-click this file again."
  read -r -p "  Press Enter to close." _; exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "  Python 3 is missing. Install it from https://www.python.org/downloads/, then double-click this file again."
  read -r -p "  Press Enter to close." _; exit 1
fi

# One-time setup: a private Python environment with the extra libraries
# (browser for JavaScript websites, email domain check, domain matching).
if [ -f .venv/.ready ] && [ finder/requirements.txt -nt .venv/.ready ]; then
  # New libraries were added since the last setup: install just those.
  echo "  Updating libraries..."
  .venv/bin/python -m pip install --quiet -r finder/requirements.txt && touch .venv/.ready
fi
if [ ! -f .venv/.ready ]; then
  echo "  First start: setting things up (one time, 2-3 minutes)..."
  python3 -m venv .venv \
    && .venv/bin/python -m pip install --quiet --upgrade pip \
    && .venv/bin/python -m pip install --quiet -r finder/requirements.txt \
    && .venv/bin/python -m playwright install chromium \
    && touch .venv/.ready \
    && echo "  Setup done." \
    || echo "  Setup didn't fully finish (check your internet). The tool still works with basic features; it will try again next time."
fi

# API keys live in .env (copy .env.example the first time).
if [ ! -f .env ]; then
  cp .env.example .env && chmod 600 .env
  echo "  Created .env: open it and paste your YouTube API key (YOUTUBE_API_KEYS=...)."
fi

# Already running? Just open it.
if curl -s -o /dev/null "$URL/api/run"; then
  echo "  Already running. Opening $URL"
  open "$URL"
  exit 0
fi

# Dashboard (Next.js): install its packages and build it when something changed.
cd dashboard || exit 1
if [ ! -d node_modules ] || [ package.json -nt node_modules ]; then
  echo "  Installing dashboard packages (one time, about a minute)..."
  npm install --no-fund --no-audit --silent && touch node_modules || { echo "  Couldn't install (check your internet)."; read -r -p "  Press Enter to close." _; exit 1; }
fi
if [ ! -f .next/BUILD_ID ] || [ -n "$(find app components lib public package.json next.config.mjs -newer .next/BUILD_ID 2>/dev/null | head -1)" ]; then
  echo "  Preparing the dashboard (takes about 20 seconds)..."
  NEXT_TELEMETRY_DISABLED=1 npx next build >/dev/null 2>&1 || { echo "  The dashboard didn't build. Run 'npm run build' in the dashboard folder to see why."; read -r -p "  Press Enter to close." _; exit 1; }
fi

echo "  Starting... the dashboard opens in your browser."
echo "  Keep this window open while you use it. Close it to stop."
(for i in 1 2 3 4 5 6 7 8 9 10; do sleep 1; curl -s -o /dev/null "$URL/api/run" && break; done; open "$URL") &
NEXT_TELEMETRY_DISABLED=1 exec npx next start -p 3030 -H 127.0.0.1
