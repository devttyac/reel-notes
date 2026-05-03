---
name: media-downloader
description: "Download any video from 1,000+ sites via yt-dlp + ffmpeg compression"
allowed-tools:
  - Bash
homepage: "https://github.com/devttyac/reel-notes"
author: "Aaron Chan"
license: MIT
---

# media-downloader

Download any video from 1,000+ sites via yt-dlp with optional ffmpeg compression. Designed as a companion step to `/sumtube` for non-YouTube sources and offline workflows.

---

## Setup preflight

Before invoking the skill, run the setup script to verify all required tools are present:

```
python scripts/setup.py --check
```

Exit codes:

| Code | Meaning | Fix |
|---|---|---|
| 0 | All dependencies present | Proceed |
| 2 | `yt-dlp` missing | `pip install yt-dlp` |
| 3 | `ffmpeg` missing | `brew install ffmpeg` |
| 4 | Both missing | Install both |

No API keys are required.

---

## When to use

Use this skill:

- Before `/sumtube` when the video is not directly accessible by URL from within sumtube (non-YouTube sources, age-gated content, or platforms requiring a local file input).
- For offline workflows where you want the file available locally before summarising.
- Standalone, when you want to save video content to disk without summarising.

If you are summarising a standard public YouTube video, `/sumtube` can handle the URL directly — `media-downloader` is not required.

---

## How to invoke

**Step 1 — Run setup preflight**

```
python scripts/setup.py --check
```

Confirm exit code 0 before continuing. If non-zero, install the missing dependency and re-run.

**Step 2 — Download the video**

```
python scripts/download.py <url> [--output <dir>] [--no-compress] [--quality <format>]
```

Example:

```
python scripts/download.py https://www.tiktok.com/@user/video/1234567890 --output ./downloads/
```

The script prints the local file path on completion.

**Step 3 — Pass the file path to /sumtube**

```
/sumtube ./downloads/video_1234567890.mp4
```

Use the exact file path printed in Step 2.

---

## Supported platforms and limitations

- Powered by yt-dlp — 1,000+ supported sites (YouTube, Twitter/X, TikTok, Instagram, Vimeo, Facebook, Reddit, Twitch, Dailymotion, and more).
- Single video per invocation. Playlist URLs are blocked (`--no-playlist` is enforced).
- HTTPS URLs only. HTTP and non-URL inputs are rejected before download begins.
- Geo-blocked, private, or subscriber-only content may fail — yt-dlp will report the error to stderr.

---

## Output

- The local file path is printed to stdout on successful download.
- Use the printed path directly as the argument to `/sumtube`.

Example output:

```
./media-downloader-output/video_1234567890.mp4
```

---

## Failure modes

| Failure | Behaviour |
|---|---|
| Unsupported site, geo-block, private video | yt-dlp error message printed to stderr; process exits non-zero; no file written |
| ffmpeg compression failure | Error printed to stderr; original (uncompressed) file path still reported to stdout |
| Disk space < 500 MB at download start | Warning printed before download begins; download proceeds unless explicitly cancelled |
| Non-HTTPS URL or non-URL input | Rejected immediately with error message; no download attempted |

---

## Security and permissions

- No API keys are required or used.
- All downloads write to the local output directory only.
- HTTPS scheme is enforced — HTTP URLs are rejected.
- `--no-playlist` is enforced unconditionally to prevent accidental bulk downloads.
- No data is sent to third parties beyond the yt-dlp download request to the source site.
- Output files may be large — ensure adequate disk space before downloading high-resolution video.

---

## Using with sumtube

The standard two-step workflow:

```
# Step 1: Download
python scripts/download.py https://www.tiktok.com/@creator/video/9876543210

# Output:
# ./media-downloader-output/video_9876543210.mp4

# Step 2: Summarise
/sumtube ./media-downloader-output/video_9876543210.mp4
```

Note: automatic handoff from `media-downloader` to `sumtube` without a manual path step is a private-layer integration feature and is not available in the public plugin. The two-step manual workflow above is the supported path.

---

## Bundled scripts

| Script | Purpose |
|---|---|
| `scripts/download.py` | Main download script — accepts URL and optional flags, invokes yt-dlp and ffmpeg |
| `scripts/setup.py` | Dependency preflight — checks for yt-dlp and ffmpeg, reports exit codes |
