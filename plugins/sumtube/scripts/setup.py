"""
Preflight checks for the SumTube public plugin.

Run this script before invoking the summariser to verify that required
environment variables and binaries are present.

Usage:
    python scripts/setup.py --check

Exit codes:
    0 — all hard requirements met (GROQ_API_KEY warning does not block)
    1 — a hard requirement is missing (ANTHROPIC_API_KEY)
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # dotenv optional; env vars may be set directly

_FFMPEG_PATH = (
    shutil.which("ffmpeg")
    or ("/opt/homebrew/bin/ffmpeg" if os.path.isfile("/opt/homebrew/bin/ffmpeg") else "")
)


def run_checks() -> None:
    """Run environment preflight checks.

    Hard requirements:
        - SUMTUBE_API_KEY or ANTHROPIC_API_KEY must be set.
          (Also loaded from .env file in plugin root if present.)

    Soft requirements (warning only):
        - GROQ_API_KEY (Whisper fallback only).
        - ffmpeg binary (local video extraction only).
    """
    failed = False

    # --- Hard requirement: SUMTUBE_API_KEY or ANTHROPIC_API_KEY ---
    if not (os.environ.get("SUMTUBE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        print(
            "ERROR: No Anthropic API key found. Set SUMTUBE_API_KEY (preferred under "
            "Claude Code, since its sandbox overwrites ANTHROPIC_API_KEY) or "
            "ANTHROPIC_API_KEY in your shell, or place either in a .env file at the "
            "plugin root. See .env.example.",
            file=sys.stderr,
        )
        failed = True

    if failed:
        sys.exit(1)

    # --- Soft requirement: GROQ_API_KEY (Whisper fallback only) ---
    if not os.environ.get("GROQ_API_KEY"):
        print(
            "WARNING: GROQ_API_KEY is not set. "
            "The Whisper audio fallback will be unavailable for videos without captions.",
            file=sys.stderr,
        )

    # --- Soft requirement: ffmpeg binary ---
    if not _FFMPEG_PATH or not os.path.isfile(_FFMPEG_PATH):
        print(
            "WARNING: ffmpeg binary not found on PATH or at /opt/homebrew/bin/ffmpeg. "
            "Local video extraction requires ffmpeg. "
            "Install with: brew install ffmpeg (macOS) or apt-get install ffmpeg (Linux).",
            file=sys.stderr,
        )

    print("Preflight checks passed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SumTube preflight environment check."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run environment preflight checks.",
    )
    args = parser.parse_args()

    if args.check:
        run_checks()
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
