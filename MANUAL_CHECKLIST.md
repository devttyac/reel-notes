# Manual Verification Checklist

The pytest e2e kit exercises the underlying scripts via `subprocess`, but a few paths can only be verified inside an interactive Claude Code session because they require Claude Code's slash-command routing layer (skill activation, hook firing, `$ARGUMENTS` substitution) or interactive prompt surfaces.

Run this checklist before tagging any release that touches command files (`plugins/*/commands/`), hooks (`plugins/*/hooks/`), or skills (`plugins/*/skills/`).

## Setup

Inside a Claude Code session in a directory with the plugins installed via the marketplace flow:

```
git clone https://github.com/devttyac/reel-notes.git
cd reel-notes
claude plugin marketplace add .
claude plugin install sumtube@reel-notes
claude plugin install media-downloader@reel-notes
cp plugins/sumtube/.env.example plugins/sumtube/.env  # fill in real keys
```

Then start a fresh Claude Code session in that directory: `claude`.

## Slash-command path — sumtube

- [ ] **`/sumtube` recognised:** type `/sumtube` and confirm it appears in the slash command list.
- [ ] **YouTube URL invocation:** `/sumtube https://www.youtube.com/watch?v=jNQXAC9IVRw --compact` — note produced.
- [ ] **Local file invocation:** `/sumtube ./tests/e2e/fixtures/zoo.mp4 --compact` — note produced via Whisper.
- [ ] **Vimeo URL invocation:** `/sumtube https://vimeo.com/76979871 --compact` — note produced via yt-dlp + Whisper.
- [ ] **Setup hook fires:** observe `SessionStart` hook output (`check-setup.sh` runs once on session start).

## Slash-command path — media-downloader

- [ ] **`/media-downloader` recognised:** type `/media-downloader` and confirm it appears in the slash command list.
- [ ] **YouTube URL:** `/media-downloader https://www.youtube.com/watch?v=jNQXAC9IVRw` — `_compressed.mp4` written.
- [ ] **Vimeo URL:** `/media-downloader https://vimeo.com/76979871` — `_compressed.mp4` written.
- [ ] **Setup hook fires:** observe `SessionStart` hook output.

## Auto-visual offer

The auto-visual offer surfaces when sumtube detects 3+ visual-signal keywords in a transcript without `--visual`. The pytest suite cannot exercise this because it depends on the interactive prompt loop.

- [ ] **Trigger:** invoke `/sumtube <visual-heavy-tutorial-URL>` (e.g., a coding screencast or slide presentation walkthrough) without `--visual`.
- [ ] **Expected:** sumtube prints a one-line offer to re-run with `--visual` after the initial summary.

## Sandbox key resolution

- [ ] **Run from a fresh shell with no `ANTHROPIC_API_KEY`/`SUMTUBE_API_KEY` exported:** verify `/sumtube` still works because the key resolves from `plugins/sumtube/.env`.
- [ ] **Remove `.env` and try again:** verify `/sumtube` fails cleanly with the missing-key error message (not a confusing 401 from Anthropic).

## Reporting

If any item fails, capture:

- Claude Code version (`claude --version`)
- Reel-notes tag (`git describe --tags`)
- Slash command typed verbatim
- Output displayed in Claude Code (full, including stderr if visible)
- `~/.claude/logs/` excerpt if the failure looks runtime-level

Open a GitHub issue or attach to the relevant retrospective.
