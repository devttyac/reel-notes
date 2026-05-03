#!/bin/bash
# check-setup.sh for sumtube plugin
# Silent when fully configured. Prints one-line hints for missing dependencies.
# Exit 0 always (non-blocking — user can still try the plugin).

MISSING=0

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "sumtube: ANTHROPIC_API_KEY not set. Export it: export ANTHROPIC_API_KEY=your-key"
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
