"""
Pytest configuration for sumtube public plugin tests.

Adds the reel-notes/plugins/sumtube directory to sys.path so that
`scripts.transcript`, `scripts.summariser`, `scripts.output`, and
`scripts.summarize` are importable as a package.

Also asserts that the private youtube-summarizer/ path is NOT on sys.path,
confirming test isolation (FR-6, SC-6).
"""

import sys
from pathlib import Path

# The directory containing conftest.py is reel-notes/plugins/sumtube/
_PLUGIN_ROOT = Path(__file__).parent.resolve()

# Add the plugin root so 'scripts' is importable as a package
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

# Isolation guard: confirm no private youtube-summarizer path is on sys.path
_PRIVATE_MARKER = "youtube-summarizer"
for _p in sys.path:
    assert _PRIVATE_MARKER not in str(_p), (
        f"Test isolation violated: private path found on sys.path: {_p!r}. "
        "Remove youtube-summarizer/ from sys.path before running these tests."
    )
