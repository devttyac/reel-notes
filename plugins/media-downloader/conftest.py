"""
Pytest configuration for media-downloader public plugin tests.

Adds reel-notes/plugins/media-downloader to sys.path so that
`scripts.download` and `scripts.setup` are importable as a package.

Also asserts no vault paths are on sys.path (FR-6, SC-6 isolation guard).
"""

import sys
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).parent.resolve()

if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

# Isolation guard: no vault paths outside the plugin root should be on sys.path.
# We check that no path on sys.path is an ancestor vault directory that would
# expose private vault modules (e.g., youtube-summarizer/ private scripts).
_PRIVATE_MARKERS = ["youtube-summarizer"]
for _p in sys.path:
    for _marker in _PRIVATE_MARKERS:
        assert _marker not in str(_p), (
            f"Test isolation violated: private path found on sys.path: {_p!r}."
        )
