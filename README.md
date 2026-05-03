# reel-notes

reel-notes — watch and summarise any video with Claude

---

## Plugins

**sumtube** — summarises a video into one structured plain markdown note. Accepts a local video file path or a direct YouTube URL.

**media-downloader** — downloads a video from any yt-dlp-supported URL (YouTube, Instagram, TikTok, X, and 1,000+ other sites) to a local file, ready for sumtube to process.

---

## Why two plugins instead of one?

reel-notes splits the workflow deliberately. Each plugin has one job, one dependency surface, and one failure mode:

| Concern | media-downloader | sumtube |
|---|---|---|
| Job | Fetch a video from a URL to local disk | Turn a video (URL or local file) into structured notes |
| External dependencies | yt-dlp, ffmpeg | Anthropic API, Groq API (optional), ffmpeg |
| API keys required | None | `SUMTUBE_API_KEY` (and optionally `GROQ_API_KEY`) |
| Risk surface | yt-dlp extractors break as sites change — updated frequently | LLM prompts and model versions evolve independently |
| Cost per run | Free (bandwidth only) | Paid (Anthropic tokens, Groq audio minutes) |

The split buys three concrete things:

1. **Independent reuse.** Want a clean local copy of a TikTok or a Vimeo lecture without paying for a summary? Use media-downloader on its own. Already have a local meeting recording? Skip the downloader and feed it straight into sumtube. Neither plugin assumes the other is installed.
2. **Isolated failure modes.** A yt-dlp extractor breaking (sites change weekly) doesn't disturb the summarisation path. A prompt or Anthropic SDK change doesn't risk the downloader. Diagnosing a failed run is easier when only one moving part can be at fault.
3. **Independent update cadence.** yt-dlp ships near-daily for site coverage; the LLM stack moves on its own schedule. Splitting them means a security or extractor update on one side never blocks an unrelated change on the other, and users can update each plugin without re-validating the full pipeline.

A monolithic plugin would force every user to install both dependency stacks, accept both risk surfaces, and update both code paths even when only one is needed. The two-plugin layout keeps the surface area each user installs proportional to what they actually use.

---

## Two-step workflow

Download, then summarise:

```
/media-downloader https://www.youtube.com/watch?v=dQw4w9WgXcQ
/sumtube /path/to/downloaded-video.mp4
```

That's it. The first command fetches the video; the second produces the summary notes.

---

## Installation

Clone the repository, register the local marketplace, then install each plugin:

```bash
git clone https://github.com/devttyac/reel-notes.git
cd reel-notes

claude plugin marketplace add .
claude plugin install sumtube@reel-notes
claude plugin install media-downloader@reel-notes
```

---

## Supported platforms

media-downloader uses yt-dlp under the hood, which supports 1,000+ sites including:

- YouTube (videos, shorts, playlists)
- Local video files passed directly to sumtube
- Non-YouTube URLs: Instagram, TikTok, X (Twitter), Vimeo, and any other yt-dlp-compatible source

---

## Requirements

| Dependency | Required | Purpose |
|---|---|---|
| [ffmpeg](https://ffmpeg.org/) | Yes | Audio extraction and format conversion |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Yes | Video downloading (media-downloader) |
| `SUMTUBE_API_KEY` *or* `ANTHROPIC_API_KEY` | Yes | Claude API access for sumtube summarisation. Use `SUMTUBE_API_KEY` under Claude Code (its sandbox overwrites `ANTHROPIC_API_KEY`). Either may also live in `.env` at the plugin root. |
| `GROQ_API_KEY` | No | Enables Whisper transcription fallback for caption-less videos |

Install system dependencies on macOS:

```bash
brew install ffmpeg yt-dlp
```

### Why Whisper matters

Captions are a fragile assumption. Whisper (via Groq) closes the gap:

- **Most non-YouTube platforms don't expose captions at all.** TikTok, X, Instagram, Vimeo, Facebook, Reddit — none surface a transcript through yt-dlp. Without Whisper, sumtube would silently fail on every one.
- **A large fraction of YouTube content has no captions either.** Newer uploads, shorter clips, non-English videos, and creator-disabled tracks all bypass YouTube's auto-caption pipeline.
- **Local recordings (meetings, screen captures, podcasts) have no captions by definition.** Whisper is the only path that lets sumtube handle them.
- **Graceful degradation.** Without `GROQ_API_KEY`, captioned videos still work — the Whisper fallback is opt-in, not required.
- **Cost stays low.** Groq's Whisper inference is sub-realtime and inexpensive; only the resulting transcript text reaches Anthropic, never raw audio.

In practice: Whisper is what turns sumtube from a YouTube-caption summariser into a general-purpose video summariser.

---

## Security

**No keys in this repository.** Never commit API keys or secrets to source control.

Set your credentials as environment variables before running either plugin:

```bash
# Under Claude Code (recommended) — its sandbox blocks ANTHROPIC_API_KEY
export SUMTUBE_API_KEY=your_anthropic_api_key_here
# Or, in a standalone shell:
export ANTHROPIC_API_KEY=your_anthropic_api_key_here

export GROQ_API_KEY=your_groq_api_key_here   # optional
```

Alternatively, copy `plugins/sumtube/.env.example` to `plugins/sumtube/.env` and fill in your keys (the `.env` file is gitignored).

**Data flow:**

- Video audio is sent to **Groq** only when `GROQ_API_KEY` is set and the video has no embedded captions. Groq processes the audio for transcription via Whisper.
- The transcript (or embedded captions, if available) is sent to **Anthropic** (Claude) for summarisation. No raw audio is sent to Anthropic.
- Nothing is stored remotely by reel-notes. Downloaded files stay on your local machine.

---

## License

MIT
