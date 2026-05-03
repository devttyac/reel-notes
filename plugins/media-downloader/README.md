# media-downloader

Download any video from 1,000+ sites — companion plugin for sumtube.

---

## Two-step workflow

Use `media-downloader` to download a video locally, then pass the file path to `sumtube` for summarisation.

```
/media-downloader https://www.tiktok.com/@user/video/1234567890
# Output: Downloaded: ./media-downloader-output/video_1234567890.mp4 (18.4 MB)

/sumtube ./media-downloader-output/video_1234567890.mp4
```

That's it. The file path printed by `media-downloader` goes directly into `/sumtube` as the input argument.

---

## Supported sites

Powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp), which supports 1,000+ sites including:

- YouTube
- Twitter / X
- TikTok
- Instagram
- Vimeo
- Facebook
- Reddit
- Twitch (VODs and clips)
- Dailymotion
- And hundreds more — see the [full yt-dlp supported sites list](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)

---

## Installation

Install from the reel-notes repository:

```
claude plugin marketplace add .
claude plugin install media-downloader@reel-notes
```

---

## First run

On first use, run the setup script to verify dependencies:

```
python scripts/setup.py
```

No API keys are required. The script checks for `yt-dlp` and `ffmpeg` and reports any missing tools with install instructions.

---

## CLI flags

| Flag | Description | Default |
|---|---|---|
| `--output <dir>` | Output directory for downloaded files | `./media-downloader-output/` |
| `--no-compress` | Skip ffmpeg compression step | Compression enabled |
| `--quality <format>` | yt-dlp format selector (e.g. `bestvideo+bestaudio`) | `bestvideo+bestaudio` |

Examples:

```
# Download to a custom directory
python scripts/download.py https://vimeo.com/123456789 --output ~/Downloads/videos/

# Download without compression (keeps original file size)
python scripts/download.py https://twitter.com/user/status/9876543210 --no-compress

# Select a specific quality
python scripts/download.py https://www.youtube.com/watch?v=dQw4w9WgXcQ --quality "bestvideo[height<=720]+bestaudio"
```

---

## Limits

- **Single video per invocation.** Playlist URLs are blocked (`--no-playlist` is enforced).
- **HTTPS URLs only.** HTTP and non-URL inputs are rejected before download begins.
- No authentication or login flows are supported.

---

## Security

- No API keys are required or used.
- All downloads write to a local output directory. Clips can be large — ensure sufficient disk space before downloading high-resolution video (500 MB free recommended).
- No data is sent to external services beyond the yt-dlp download request to the source site.
- The `--no-playlist` flag is enforced unconditionally to prevent accidental bulk downloads.

---

## License

MIT
