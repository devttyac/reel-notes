#!/bin/bash
# check-setup.sh for sumtube plugin
# Silent when fully configured. Prints one-line hints for missing dependencies.
# Exit 0 always (non-blocking — user can still try the plugin).

MISSING=0

# Keys come from the environment or ~/.config/sumtube/.env. For the file, grep -q
# only checks that a "SUMTUBE_API_KEY=" line with a non-empty value is present
# (a yes/no answer). The value is never captured, printed or logged.
KEY_FILE="$HOME/.config/sumtube/.env"
if [ -z "$SUMTUBE_API_KEY" ] && ! { [ -f "$KEY_FILE" ] && grep -q '^SUMTUBE_API_KEY=[^[:space:]]' "$KEY_FILE"; }; then
  echo "sumtube: SUMTUBE_API_KEY not set. Export it, or put SUMTUBE_API_KEY=... in ~/.config/sumtube/.env (chmod 600). ANTHROPIC_API_KEY is not read."
  MISSING=1
fi

if ! command -v ffmpeg &>/dev/null && [ ! -x "/opt/homebrew/bin/ffmpeg" ]; then
  echo "sumtube: ffmpeg not found. Install: brew install ffmpeg"
  MISSING=1
fi

if ! command -v yt-dlp &>/dev/null; then
  echo "sumtube: yt-dlp not found. Install: pip install yt-dlp"
fi

if [ -z "$GROQ_API_KEY" ]; then
  : # GROQ_API_KEY is optional — silent absence is expected
fi

exit 0
