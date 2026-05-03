---
name: sumtube
description: "Summarise any video (YouTube URL, local file, or non-YouTube URL) into structured markdown notes"
allowed-tools:
  - Bash
homepage: "https://github.com/devttyac/reel-notes"
author: "Aaron Chan"
license: MIT
---

# sumtube

Summarise any video (YouTube URL, local file, or non-YouTube URL) into structured markdown notes.

---

## Setup Preflight

Before invoking the skill, verify the environment is ready:

```bash
python scripts/setup.py
```

Exit codes:

| Code | Meaning |
|---|---|
| 0 | All required dependencies present — ready to run |
| 1 | `ANTHROPIC_API_KEY` not set — skill cannot proceed; stop and report the missing key |
| 2 | `yt-dlp` not installed — warn the user; caption-only YouTube URLs will still work |
| 3 | `ffmpeg` not installed — warn the user; Whisper transcription will not be available |

`GROQ_API_KEY` is **not** validated at preflight. It is checked lazily only when Whisper transcription is needed (caption-less video or local file). If Whisper is triggered and the key is absent, the skill raises `MissingAPIKeyError` and halts.

---

## When to Use

Use sumtube whenever the input is a video reference (URL or file path) and a structured markdown summary is the desired output.

Input routing:

| Input type | Transcript path | Whisper fallback |
|---|---|---|
| YouTube URL | Caption download attempt first | Yes — if captions unavailable and `GROQ_API_KEY` set |
| Non-YouTube URL | yt-dlp download → caption attempt | Yes — if captions unavailable and `GROQ_API_KEY` set |
| Local file path | No caption path | Always uses Whisper — requires `GROQ_API_KEY` |

---

## How to Invoke

Follow these steps in order:

**Step 1 — Run setup preflight**

```bash
python scripts/setup.py
```

Stop if exit code is 1 (missing API key). Warn and continue if exit code is 2 or 3.

**Step 2 — Detect input type**

Classify the argument as one of: YouTube URL, non-YouTube URL, or local file path.

**Step 3 — Run the summariser**

```bash
python scripts/summarize.py <input> [flags]
```

Replace `<input>` with the URL or file path. Append flags as needed (see CLI Flags Reference below).

**Step 4 — Exit code 0: display output**

Read the output note from the configured output directory and display it to the user.

**Step 5 — Exit code non-zero: surface the error**

Read stderr and display the error message. Do not retry automatically. Report the failure mode and the corrective action if one is defined in the Failure Modes section below.

---

## Transcription Methods

sumtube uses two transcription paths:

1. **Captions** — yt-dlp downloads the auto-generated or manual caption track for YouTube and some other platforms. No Groq API key required. Used first whenever available.
2. **Groq Whisper** — audio is extracted from the video using ffmpeg and sent to the Groq Whisper API. Requires `GROQ_API_KEY`. Used when captions are unavailable and always for local files.

If neither path is available (captions absent and `GROQ_API_KEY` not set), the skill raises `MissingAPIKeyError` and halts.

---

## Failure Modes

| Error | Cause | Corrective action |
|---|---|---|
| `TranscriptUnavailableError` | No captions found for the video | Whisper fallback fires automatically if `GROQ_API_KEY` is set; if key is absent, report `MissingAPIKeyError` |
| `AudioFileTooLargeError` | Extracted audio exceeds 25 MB | Report to user; no workaround available in current version |
| `AudioExtractionError` | ffmpeg failed to extract audio | Verify ffmpeg is installed and the file is a valid video; report stderr output |
| `MissingAPIKeyError` | `GROQ_API_KEY` not set when Whisper is required | Instruct user to set `GROQ_API_KEY` as an environment variable |
| `GroqQuotaExhaustedError` | Groq API rate limit or quota exceeded | Report to user; retry after quota reset or upgrade Groq plan |

---

## CLI Flags Reference

| Flag | Description |
|---|---|
| `--compact` | Generate a shorter summary. Reduces token usage and output length. |
| `--no-obsidian` | Write plain markdown (no YAML frontmatter, no wikilinks) to the directory specified by `--output` (default: current working directory). |
| `--output <dir>` | Write the output note to the specified directory instead of the default. |
| `--model <id>` | Override the default Claude model. Accepts any valid Anthropic model ID. |
| `--visual` | Extract and analyse video frames alongside the transcript. Uses Claude's vision capability. Increases cost. |

---

## Token Efficiency

- Use `--compact` to reduce output length when a brief summary is sufficient. This lowers token consumption on both the Claude API call and the output.
- `--visual` enables frame analysis using Claude Sonnet. This increases cost due to vision token usage. The skill will automatically offer `--visual` when the input appears to be visual-heavy content (e.g., tutorial screencasts, slide presentations). Do not enable it by default.

---

## Security and Permissions

- The public plugin writes one plain markdown note to the `--output` directory (default: current working directory). No vault paths, no Obsidian frontmatter. Use `--no-obsidian` to write plain markdown without YAML frontmatter or wikilinks.
- API keys must be set as environment variables. Never pass them as command-line arguments or embed them in configuration.
- The `$ARGUMENTS` value from the skill invocation is passed as a positional argument to `scripts/summarize.py`. It is not interpolated into any shell command string and is not subject to shell injection.
- No API keys appear in process arguments, log output, or stdout.

---

## Output Format

sumtube produces plain markdown only. Output does not contain:

- Wikilinks or internal link syntax
- Obsidian YAML frontmatter
- Application-specific metadata

The output is portable and can be used in any markdown editor or piped to any downstream tool.

---

## Bundled Scripts

| Script | Purpose |
|---|---|
| `scripts/summarize.py` | Main entry point; orchestrates input detection, transcription, and summarisation |
| `scripts/transcript.py` | Handles caption download and Whisper transcription |
| `scripts/summariser.py` | Builds the Claude API prompt and parses the response |
| `scripts/output.py` | Formats and writes the final markdown note |
| `scripts/setup.py` | Dependency and environment preflight check |
