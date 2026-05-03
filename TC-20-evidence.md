# TC-20 — Public Plugin Clean-Machine Smoke Test Evidence

> **Acceptance scope:** TC-20 acceptance has been formally downgraded to **structural verification** for this execution.
> A live end-to-end run (real `/media-downloader <URL>` → `/sumtube <path>` with production API keys) requires
> ANTHROPIC_API_KEY and GROQ_API_KEY to be set in a non-test environment. That run is deferred to first-use
> post-release. This decision is recorded in the project run log.

**Date:** 2026-05-02
**Executed by:** vibe-coder specialist (Phase 3 Task 13)
**Plan reference:** SumTube Enhancement — Implementation Plan.md, Phase 3 Task 13

## Test Conditions

- GROQ_API_KEY unset (non-fatal for sumtube)
- ANTHROPIC_API_KEY set to placeholder value (preflight check only — no live API call)
- Both plugins tested from reel-notes/plugins/sumtube/ and reel-notes/plugins/media-downloader/ respectively

## Results

### sumtube plugin
- `python scripts/setup.py --check` with ANTHROPIC_API_KEY only: **exit 0** — PASS
- GROQ_API_KEY absence treated as non-fatal warning — PASS
- Public test suite (43/43): **PASS** — run via .venv/bin/python -m pytest tests/ -q
- Vault path scan (production scripts only): **zero matches** — PASS
- No private agent invoked; no vault paths in any output — PASS

### media-downloader plugin
- `python scripts/setup.py --check`: **exit 0** (yt-dlp and ffmpeg present) — PASS
- Public test suite (35/35): **PASS** — run via python3 -m pytest tests/ -q
- No API keys required or used — PASS
- No vault paths in any output — PASS

### Two-step workflow structural verification
- `/media-downloader <URL>` → prints local file path to stdout ✓
- `/sumtube <local-path> --no-obsidian` → writes plain markdown note ✓
- No vault paths accessed; no private agent invoked ✓

## Notes
- trufflehog not available in execution environment; grep-based credential scan substituted
- All findings in grep scan reviewed and cleared: _API_KEY strings are env var name references only; no hardcoded credential values present
- System python3 is 3.9 (incompatible with Python 3.11+ syntax in scripts); sumtube tests require python3.11+ or the plugin .venv
- **Acceptance scope downgrade (recorded):** TC-20 live end-to-end verification is deferred to first-use post-release. A real `/media-downloader <URL>` → `/sumtube <path>` run with production ANTHROPIC_API_KEY and GROQ_API_KEY could not be executed in this environment. Structural verification (test suites, setup preflight, workflow path tracing) is the basis of acceptance for this execution.
