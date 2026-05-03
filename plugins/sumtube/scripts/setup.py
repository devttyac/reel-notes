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
import sys

_FFMPEG_PATH = "/opt/homebrew/bin/ffmpeg"


def run_checks() -> None:
    """Run environment preflight checks.

    Hard requirements:
        - ANTHROPIC_API_KEY must be set.

    Soft requirements (warning only):
        - GROQ_API_KEY (Whisper fallback only).
        - ffmpeg binary (local video extraction only).
    """
    failed = False

    # --- Hard requirement: ANTHROPIC_API_KEY ---
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY environment variable is not set. "
            "Set it before running the summariser.",
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
    if not os.path.isfile(_FFMPEG_PATH):
        print(
            f"WARNING: ffmpeg binary not found at {_FFMPEG_PATH!r}. "
            "Local video extraction requires ffmpeg. Install with: brew install ffmpeg",
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
