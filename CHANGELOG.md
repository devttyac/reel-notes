# Changelog

## v0.1.8 — 2026-05-03

Linux portability — `ffmpeg` binary path was hardcoded to `/opt/homebrew/bin/ffmpeg` (macOS Homebrew arm64), breaking the plugin entirely on Linux. Surfaced by the v0.1.7 CI run on Ubuntu where `ffmpeg` is at `/usr/bin/ffmpeg`.

- `transcript.py`: resolve `_FFMPEG_PATH` via `shutil.which("ffmpeg")` first, fall back to `/opt/homebrew/bin/ffmpeg`. Same pattern already used for `yt-dlp` resolution.
- `setup.py`: same resolution; updated warning message to mention both `brew install` and `apt-get install`.
- `transcript.py`: updated runtime FileNotFoundError message similarly.
- `sumtube` plugin bumped to v0.1.7.

## v0.1.7 — 2026-05-03

Two CI-discovered fixes from the first `test-live.yml` workflow run.

- `summariser.py`: add `from __future__ import annotations`. Functions used `Anthropic` as a type annotation but imported `anthropic.Anthropic` lazily inside their bodies, so module-level annotation evaluation raised `NameError: name 'Anthropic' is not defined` on Python 3.12 / clean CI environments. PEP 563 deferred annotation evaluation resolves this without changing the lazy-import pattern. Local plugin runs masked the bug because the test venv had `anthropic` already in scope from a prior import path.
- `tests/e2e/conftest.py` + `pytest.ini`: register `youtube` marker; auto-skip YouTube tests when `GITHUB_ACTIONS=true`. GitHub Actions runner IPs are flagged by YouTube as bot traffic (`Sign in to confirm you're not a bot`), making yt-dlp YouTube downloads non-functional in CI. YouTube-dependent tests now run locally only; CI relies on Vimeo + local fixtures.
- `sumtube` plugin bumped to v0.1.6.

## Unreleased — e2e test kit (infra) — published as part of v0.1.7

Adds a pytest-based e2e test kit covering everything validated through v0.1.6, plus a manual checklist for paths the runner cannot drive (slash commands, auto-visual offer).

- `tests/e2e/` — `conftest.py` (shared fixtures, auto-skip on missing keys/network/CI YouTube blocks), `test_smoke.py`, `test_sumtube_youtube.py`, `test_sumtube_whisper.py`, `test_sumtube_non_youtube.py`, `test_sumtube_flags.py`, `test_media_downloader.py`. Regression assertions reference the bug version that motivated the test (e.g. `regression: v0.1.4 webm-compression empty-file`).
- `tests/e2e/fixtures/zoo.mp4` — local mp4 (~600KB) for Whisper-path tests; `tests/e2e/fixtures/TEST_URLS.md` documents the canonical and backup URLs used by live tests.
- `pytest.ini` — registers `live`, `paid`, `slow`, `youtube` markers. Default `pytest tests/e2e` runs offline tests only; live/paid require `-m`.
- `MANUAL_CHECKLIST.md` — interactive verification for slash-command and auto-visual-offer paths.
- `.github/workflows/test-live.yml` — runs the full suite on tag push (and via `workflow_dispatch`); requires `SUMTUBE_API_KEY` and `GROQ_API_KEY` repo secrets.

## v0.1.6 — 2026-05-03

True fix for non-YouTube URLs (the v0.1.5 `bestaudio/best` selector change wasn't the actual root cause).

- `summarize.py`: `_download_audio_yt_dlp` now `os.unlink`s the temp stub created by `tempfile.mkstemp(suffix=".mp3")` before invoking yt-dlp. Without this, yt-dlp sees the empty file already exists, prints "already downloaded", skips the download entirely, then attempts postprocessing on the 0-byte stub — `ffprobe` fails to obtain the audio codec and the run errors out. Same root-cause family as the v0.1.3 ffmpeg `-y` fix (both caused by `mkstemp` pre-creating empty files), but yt-dlp lacks an `-y`-equivalent, so unlink is the correct remedy.
- `sumtube` plugin bumped to v0.1.5.

## v0.1.5 — 2026-05-03

Three sumtube fixes uncovered by extended TC-20 live verification (non-YouTube URLs, parens-in-filenames, Groq preflight noise).

- `summarize.py`: yt-dlp format selector changed from `bestaudio` to `bestaudio/best`. The `bestaudio`-only selector failed on Vimeo (and likely other non-YouTube sources) when yt-dlp picked a DASH stream that ffprobe couldn't read for postprocess. The fallback chain ensures yt-dlp downloads a full video container if the audio-only format is unreadable, then ffmpeg extracts the audio downstream.
- `transcript.py`: relaxed local-file path validator to allow parentheses. Original validator rejected `()` as shell metacharacters, but every subprocess call in the plugin uses `shell=False`, so parens cannot trigger shell injection. yt-dlp produces filenames with parens by default (e.g., `Title (Year)_compressed.mp4`), so rejecting them broke the download → summarise handoff for many real-world sources.
- `summarize.py`: added `User-Agent: sumtube-preflight/0.1` header to the Groq preflight HTTPS check. The Cloudflare 1010 error logged on every Whisper run was caused by Cloudflare blocking the default Python `urllib` user-agent. The preflight is non-blocking, so this was log noise rather than a functional defect, but it polluted every Whisper run output.
- `sumtube` plugin bumped to v0.1.4.

## v0.1.4 — 2026-05-03

Fix media-downloader compression for non-mp4 source containers.

- `media-downloader/scripts/download.py`: force `.mp4` output for the compressed file (was inheriting input suffix). Webm sources previously produced a 264-byte broken file because libx264/aac aren't valid in a webm container. Also adds `-movflags +faststart` so the moov atom is at the start of the file (better streaming/preview behaviour).
- `media-downloader` plugin bumped to v0.1.1.

## v0.1.3 — 2026-05-03

Fix Whisper transcription on local files — every Whisper run on a local video file failed with "file is empty".

- `transcript.py`: pass `-y` to ffmpeg so it overwrites the empty mp3 tempfile that `tempfile.mkstemp` pre-creates. Without `-y`, ffmpeg refused (silently in stderr), leaving a 0-byte file that Groq Whisper rejected.

## v0.1.2 — 2026-05-03

Fix Claude Code sandbox compatibility — v0.1.1 was unusable under Claude Code because its sandbox injects an empty `ANTHROPIC_API_KEY` into all child processes, silently overwriting the user's real key.

- Add `SUMTUBE_API_KEY` as the preferred env var name under Claude Code (sandbox does not overwrite this name).
- Lookup order in `summarize.py` is now: `--api-key` flag → `SUMTUBE_API_KEY` → `ANTHROPIC_API_KEY`.
- Load `.env` from plugin root (`plugins/sumtube/.env`) via `python-dotenv`; both var names are read.
- Add `plugins/sumtube/.env.example` documenting the variables.
- `setup.py --check` accepts either `SUMTUBE_API_KEY` or `ANTHROPIC_API_KEY` and reads `.env`.
- Update README (root + sumtube) to document Claude Code sandbox workaround and `.env` flow.

## v0.1.1 — 2026-05-03

Marketplace install fixes — v0.1.0 was uninstallable in Claude Code. v0.1.1 makes the documented install flow work end-to-end.

- Add required `name` and `owner` fields to `.claude-plugin/marketplace.json`; rename `path` → `source`; drop redundant `skills` array (auto-discovered).
- Add per-plugin `.claude-plugin/plugin.json` manifests for `sumtube` and `media-downloader` (previously missing — caused install failure).
- Move each plugin's `SKILL.md` into `skills/<name>/SKILL.md` to match Claude Code's auto-discovery convention.
- Fix `hooks.json` schema in both plugins: nested `hooks` array structure, and replace hardcoded `plugins/<name>/...` paths with `${CLAUDE_PLUGIN_ROOT}` for portability.
- Update README install instructions (root + both plugins) to use the marketplace flow: `claude plugin marketplace add .` then `claude plugin install <plugin>@reel-notes`.

## v0.1.0 — 2026-05-03

- Initial public release: `sumtube` and `media-downloader` plugins for Claude Code, with a two-step download-then-summarise workflow supporting YouTube and 1,000+ yt-dlp sources.
