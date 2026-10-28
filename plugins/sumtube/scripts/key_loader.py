"""
Shared key-file loader for the SumTube entry points (summarize.py, setup.py).

Keys load from exactly two places: the process environment, and the file
~/.config/sumtube/.env. A .env file inside the plugin folder is NOT read.
Variables already set in the environment win over the file (python-dotenv
default), so a key exported in the shell always takes priority.

If the operating system refuses to read the key folder or file
(PermissionError), the program prints one line to stderr and exits with code 4.
It does this even when keys are set in the environment, so a blocked folder
never falls back to another key source. Some AI tools sandbox this folder
(for example Codex CLI or Antigravity); run SumTube from Claude Code or a
normal terminal.

This module never reads, prints, or logs key values. It only decides which
file to hand to python-dotenv.
"""

import os
import stat
import sys
from pathlib import Path
from typing import Optional

# Kept unexpanded so os.path.expanduser resolves HOME at call time.
ENV_PATH = "~/.config/sumtube/.env"

# Exit code for "the key folder is blocked" (0 ok, 1 hard requirement missing,
# 2 argparse).
EXIT_KEY_FOLDER_BLOCKED = 4

BLOCKED_MESSAGE = (
    "SumTube cannot read its key folder ~/.config/sumtube: the operating system "
    "refused access. Inside an AI tool whose sandbox blocks this folder (for "
    "example Codex CLI or Antigravity) this is expected: run SumTube from "
    "Claude Code or a normal terminal. Elsewhere, check the folder's or "
    "file's permissions."
)


def load_sumtube_env() -> Optional[Path]:
    """Load ~/.config/sumtube/.env if it exists. Return the path loaded, or None.

    python-dotenv is optional here: without it, only the process environment
    is used, which is the same behaviour the plugin had before.

    Exits with code 4 if the OS refuses the read.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None

    path = Path(os.path.expanduser(ENV_PATH))
    try:
        if not stat.S_ISREG(os.stat(path).st_mode):
            return None
        load_dotenv(path)
    except PermissionError:
        print(BLOCKED_MESSAGE, file=sys.stderr)
        raise SystemExit(EXIT_KEY_FOLDER_BLOCKED)
    except OSError:
        return None
    return path
