# sumtube

Summarise any video into structured notes.

---

## Why

Most video summarisation tools handle only YouTube URLs and only when captions are available. That leaves out a significant share of real-world content: YouTube videos without auto-generated captions, videos from other platforms (X, Instagram, TikTok, Vimeo), and local video files recorded from meetings or screen captures.

sumtube removes those gaps. It uses captions where they exist, falls back to Groq Whisper transcription when they do not, and accepts any local file path — so the same workflow handles the full range of video content without switching tools.

---

## How It Works

1. **Input detection** — sumtube identifies whether the input is a YouTube URL, a non-YouTube URL, or a local file path.
2. **Transcript acquisition** — YouTube URLs attempt caption download first; if captions are unavailable, audio is extracted and sent to Groq Whisper. Non-YouTube URLs are downloaded via yt-dlp before the same caption/Whisper path runs. Local files go directly to Whisper.
3. **Summarisation** — the transcript is sent to the Anthropic Claude API with a structured summarisation prompt.
4. **Output** — a markdown summary note is written to the configured output directory. Use `--no-obsidian` to write plain markdown (no YAML frontmatter, no wikilinks) to the `--output` directory (default: current working directory).

---

## Installation

From the reel-notes repository root:

```bash
claude plugin marketplace add .
claude plugin install sumtube@reel-notes
```

---

## First Run

Run the setup script once after installation to verify dependencies:

```bash
python scripts/setup.py
```

**Required:** an Anthropic API key. sumtube looks for it in this order:

1. `--api-key <key>` CLI flag
2. `SUMTUBE_API_KEY` environment variable
3. `ANTHROPIC_API_KEY` environment variable
4. `.env` file at the plugin root (either variable name)

> **Important — Claude Code users:** Claude Code's sandbox injects an empty `ANTHROPIC_API_KEY` into all child processes, overwriting any shell-level value. **Use `SUMTUBE_API_KEY` instead.** Either export it (`export SUMTUBE_API_KEY=...`) or copy `.env.example` to `.env` in the plugin root and fill in the key. Standalone shell users can use `ANTHROPIC_API_KEY` as before.

**Optional:** `GROQ_API_KEY` enables Whisper transcription for caption-less videos. Without it, sumtube cannot process videos that lack captions.

---

## Usage Examples

Summarise a YouTube video:

```bash
/sumtube https://www.youtube.com/watch?v=EXAMPLE
```

Summarise a local video file:

```bash
/sumtube /path/to/video.mp4
```

Compact output (shorter summary):

```bash
/sumtube https://www.youtube.com/watch?v=EXAMPLE --compact
```

Include visual frame analysis (higher API cost):

```bash
/sumtube https://www.youtube.com/watch?v=EXAMPLE --visual
```

Write plain markdown to the current working directory (no Obsidian frontmatter or wikilinks):

```bash
/sumtube https://www.youtube.com/watch?v=EXAMPLE --no-obsidian
```

---

## CLI Flags

| Flag | Description |
|---|---|
| `--compact` | Generate a shorter summary. Reduces token usage and output length. |
| `--no-obsidian` | Write plain markdown (no YAML frontmatter, no wikilinks) to the directory specified by `--output` (default: current working directory). |
| `--output <dir>` | Write the output note to the specified directory instead of the default. |
| `--model <id>` | Override the default Claude model. Accepts any valid Anthropic model ID. |
| `--visual` | Extract and analyse video frames alongside the transcript. Uses Claude's vision capability. Increases cost. |

---

## Limits

- **Whisper audio size:** Maximum 25 MB per audio file. Videos with larger audio tracks cannot be processed via Whisper.
- **Visual frame budget:** `--visual` extracts up to 100 frames. Videos with visual changes beyond that budget are sampled at the 100-frame cap.
- **No playlist support:** sumtube processes one video per invocation. Playlist URLs are not supported.

---

## Security

**Environment variables (NFR-11)**

Never embed API keys in configuration files committed to source control. Set them in your shell profile or in a gitignored `.env` file at the plugin root:

```bash
# Option A — shell export
export SUMTUBE_API_KEY="..."     # preferred under Claude Code
export GROQ_API_KEY="..."        # optional

# Option B — .env file (copy from .env.example)
cp .env.example .env
# then edit .env with your real keys
```

The `--api-key` CLI flag is supported but should be used only for one-off scripted runs — never in shared command history.

**Data flow**

- Transcript text (captions or Whisper output) is sent to Anthropic for summarisation. No video or audio content is uploaded to Anthropic.
- Audio files are sent to Groq Whisper for transcription only when captions are unavailable and `GROQ_API_KEY` is set. The audio is not retained by sumtube after the API call.
- No data is sent to any third party beyond Anthropic and Groq.

**Key revocation**

If a key is believed to be compromised:

1. Rotate the key immediately in the Anthropic Console or Groq Console.
2. Update the environment variable on all devices.
3. Audit recent API usage logs for unexpected activity.

---

## Contributing

Before opening a pull request:

1. Run the dependency vulnerability scan:

   ```bash
   pip-audit
   ```

2. Fix any findings before submitting. Pull requests with known CVEs in dependencies will not be merged. (NFR-15)

---

## License

MIT
