#!/bin/bash
# check-setup.sh for media-downloader plugin
# Silent when fully configured. Prints one-line hints for missing dependencies.
# No API key checks — media-downloader requires none.
# Exit 0 always (non-blocking).

if ! command -v yt-dlp &>/dev/null; then
  echo "media-downloader: yt-dlp not found. Install: pip install yt-dlp"
fi

if ! command -v ffmpeg &>/dev/null && [ ! -x "/opt/homebrew/bin/ffmpeg" ]; then
  echo "media-downloader: ffmpeg not found. Install: brew install ffmpeg"
fi

exit 0
