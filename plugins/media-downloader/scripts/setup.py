"""
Preflight checks for the media-downloader public plugin.

Run this script before invoking download.py to verify that required
binaries are present.

No API keys required — media-downloader uses only yt-dlp and ffmpeg.

Usage:
    python scripts/setup.py --check
    python scripts/setup.py --json

Exit codes:
    0 — all requirements met
    2 — yt-dlp not found
    3 — ffmpeg not found
    4 — both yt-dlp and ffmpeg not found
"""

import argparse
import json
import os
import shutil
import sys
from typing import Optional

_FFMPEG_HOMEBREW = "/opt/homebrew/bin/ffmpeg"


# ---------------------------------------------------------------------------
# Binary resolution helpers
# ---------------------------------------------------------------------------

def _find_ytdlp() -> Optional[str]:
    """Return the path to yt-dlp, or None if not found."""
    return shutil.which("yt-dlp")


def _find_ffmpeg() -> Optional[str]:
    """Return the path to ffmpeg, or None if not found.

    Tries /opt/homebrew/bin/ffmpeg first, then falls back to shutil.which.
    """
    if os.path.isfile(_FFMPEG_HOMEBREW):
        return _FFMPEG_HOMEBREW
    return shutil.which("ffmpeg")


# ---------------------------------------------------------------------------
# Check runners
# ---------------------------------------------------------------------------

def run_checks() -> None:
    """Run preflight checks and exit with appropriate code on failure.

    Silent on success (no stdout output).
    Prints one-line actionable hints to stderr on failure.

    Exit codes:
        0 — both tools present
        2 — yt-dlp missing
        3 — ffmpeg missing
        4 — both missing
    """
    ytdlp_ok = _find_ytdlp() is not None
    ffmpeg_ok = _find_ffmpeg() is not None

    if ytdlp_ok and ffmpeg_ok:
        return  # Exit 0, no output

    hints = []
    if not ytdlp_ok:
        hints.append("yt-dlp not found. Install: pip install yt-dlp")
    if not ffmpeg_ok:
        hints.append("ffmpeg not found. Install: brew install ffmpeg")

    for hint in hints:
        print(hint, file=sys.stderr)

    if not ytdlp_ok and not ffmpeg_ok:
        sys.exit(4)
    elif not ytdlp_ok:
        sys.exit(2)
    else:
        sys.exit(3)


def run_checks_json() -> None:
    """Run preflight checks and print structured JSON to stdout.

    Output format:
        {"yt_dlp": true/false, "ffmpeg": true/false, "ready": true/false}

    Always exits 0 — exit codes are not used in JSON mode (caller reads the JSON).
    """
    ytdlp_ok = _find_ytdlp() is not None
    ffmpeg_ok = _find_ffmpeg() is not None
    ready = ytdlp_ok and ffmpeg_ok

    result = {
        "yt_dlp": ytdlp_ok,
        "ffmpeg": ffmpeg_ok,
        "ready": ready,
    }
    print(json.dumps(result))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="media-downloader preflight check."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Run preflight checks. Silent on success (exit 0). "
            "Prints actionable hints to stderr on failure "
            "(exit 2: yt-dlp missing, exit 3: ffmpeg missing, exit 4: both missing)."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON: {yt_dlp, ffmpeg, ready}.",
    )
    args = parser.parse_args()

    if args.json:
        run_checks_json()
    elif args.check:
        run_checks()
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
