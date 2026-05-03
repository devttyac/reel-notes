# reel-notes

reel-notes — watch and summarise any video with Claude

---

## Plugins

**sumtube** — summarises a video into one structured plain markdown note. Accepts a local video file path or a direct YouTube URL.

**media-downloader** — downloads a video from any yt-dlp-supported URL (YouTube, Instagram, TikTok, X, and 1,000+ other sites) to a local file, ready for sumtube to process.

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

Clone the repository, then install each plugin into your Claude Code environment:

```bash
git clone https://github.com/devttyac/reel-notes.git
cd reel-notes

claude plugin install plugins/sumtube
claude plugin install plugins/media-downloader
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
| `ANTHROPIC_API_KEY` | Yes | Claude API access for sumtube summarisation |
| `GROQ_API_KEY` | No | Enables Whisper transcription fallback for caption-less videos |

Install system dependencies on macOS:

```bash
brew install ffmpeg yt-dlp
```

---

## Security

**No keys in this repository.** Never commit API keys or secrets to source control.

Set your credentials as environment variables before running either plugin:

```bash
export ANTHROPIC_API_KEY=your_anthropic_api_key_here
export GROQ_API_KEY=your_groq_api_key_here   # optional
```

**Data flow:**

- Video audio is sent to **Groq** only when `GROQ_API_KEY` is set and the video has no embedded captions. Groq processes the audio for transcription via Whisper.
- The transcript (or embedded captions, if available) is sent to **Anthropic** (Claude) for summarisation. No raw audio is sent to Anthropic.
- Nothing is stored remotely by reel-notes. Downloaded files stay on your local machine.

---

## License

MIT
