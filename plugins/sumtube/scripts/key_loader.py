"""
Shared key-file loader for the SumTube entry points (summarize.py, setup.py).

Keys load from exactly two places: the process environment, and the file
~/.config/sumtube/.env. A .env file inside the plugin folder is NOT read.
Variables already set in the environment win over the file (python-dotenv
default), so a key exported in the shell always takes priority.

This module never reads, prints, or logs key values. It only decides which
file to hand to python-dotenv.
"""

import os
from pathlib import Path
from typing import Optional

# Kept unexpanded so os.path.expanduser resolves HOME at call time.
ENV_PATH = "~/.config/sumtube/.env"


def load_sumtube_env() -> Optional[Path]:
    """Load ~/.config/sumtube/.env if it exists. Return the path loaded, or None.

    python-dotenv is optional here: without it, only the process environment
    is used, which is the same behaviour the plugin had before.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None

    path = Path(os.path.expanduser(ENV_PATH))
    if path.is_file():
        load_dotenv(path)
        return path
    return None
