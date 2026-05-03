"""Unit tests for summariser._signal_scan.

The detector counts distinct visual-signal keywords in a transcript. When
the count reaches 3, summarize.py's _maybe_offer_visual_rerun prompts the
user to re-run with --visual. The interactive prompt itself is exercised
by MANUAL_CHECKLIST.md; this module pins the detector contract so the
gate doesn't silently regress.

regression: covers the 8-keyword set, threshold semantics, case
insensitivity, multi-word phrase matching, and per-keyword dedup.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_PLUGIN_ROOT = Path(__file__).parent.parent.resolve()
_SCRIPTS_DIR = _PLUGIN_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from summariser import _signal_scan, _VISUAL_SIGNAL_KEYWORDS  # noqa: E402


class TestSignalScan(unittest.TestCase):
    def test_empty_transcript_returns_zero(self):
        self.assertEqual(_signal_scan(""), 0)

    def test_no_keywords_returns_zero(self):
        text = "This is a normal conversation about cooking and gardening."
        self.assertEqual(_signal_scan(text), 0)

    def test_single_keyword_returns_one(self):
        text = "Let me explain the diagram on the page."
        self.assertEqual(_signal_scan(text), 1)

    def test_two_keywords_below_threshold(self):
        # Two distinct keywords — gate should not fire.
        text = "Look at the diagram. Then check the architecture overview."
        self.assertEqual(_signal_scan(text), 2)

    def test_three_keywords_at_threshold(self):
        # Three distinct keywords — gate fires (>=3 in summarize.py).
        text = (
            "Look at the diagram. The architecture is clear. "
            "Now I'll walk through the code."
        )
        self.assertEqual(_signal_scan(text), 3)

    def test_case_insensitive_match(self):
        text = "DIAGRAM and Architecture and CODE."
        self.assertEqual(_signal_scan(text), 3)

    def test_multi_word_phrase_keywords_counted(self):
        # 'let me show' and 'as you can see' are both phrase keywords.
        text = "Let me show you the slide. As you can see, this is the demo."
        # Matches: 'let me show', 'slide', 'as you can see', 'demo' = 4
        self.assertEqual(_signal_scan(text), 4)

    def test_repeated_keyword_counted_once(self):
        # 'diagram' repeated 5 times — still counts as 1 toward the score.
        text = "diagram diagram diagram diagram diagram"
        self.assertEqual(_signal_scan(text), 1)

    def test_all_keywords_capped_at_eight(self):
        text = " ".join(_VISUAL_SIGNAL_KEYWORDS)
        self.assertEqual(_signal_scan(text), len(_VISUAL_SIGNAL_KEYWORDS))
        self.assertEqual(_signal_scan(text), 8)

    def test_keyword_set_is_exactly_eight(self):
        # If this assertion ever fails, the threshold/docs need re-review.
        # The 3+ threshold and the "8 visual signal keywords" docstring
        # in summariser.py are coupled to this size.
        self.assertEqual(len(_VISUAL_SIGNAL_KEYWORDS), 8)


if __name__ == "__main__":
    unittest.main()
