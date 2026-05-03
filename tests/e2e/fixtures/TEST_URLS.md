# Test URLs

Stable public URLs used by the e2e suite. If any go dark, swap to the listed backup.

## YouTube — captions present, short

| Use | Video ID | URL | Notes |
|---|---|---|---|
| Primary | `jNQXAC9IVRw` | https://www.youtube.com/watch?v=jNQXAC9IVRw | "Me at the zoo", 19s, ~39-word transcript via captions. The first YouTube video; permanent. |
| Backup 1 | `dQw4w9WgXcQ` | https://www.youtube.com/watch?v=dQw4w9WgXcQ | "Never Gonna Give You Up", 3m33s. Also permanent, captions present. |

## Vimeo — non-YouTube URL, short

| Use | Video ID | URL | Notes |
|---|---|---|---|
| Primary | `76979871` | https://vimeo.com/76979871 | "The New Vimeo Player (You Know, For Videos)", ~3m. Producer-curated, stable. |
| Backup 1 | `148751763` | https://vimeo.com/148751763 | Vimeo Staff Pick. |

## YouTube — long transcript for chunking

| Use | Video ID | URL | Notes |
|---|---|---|---|
| Primary | `8jPQjjsBbIc` | https://www.youtube.com/watch?v=8jPQjjsBbIc | "How to stay calm when you know you'll be stressed" — Daniel Levitin TED, ~12m, ~2200-word transcript. |
| Backup 1 | `arj7oStGLkU` | https://www.youtube.com/watch?v=arj7oStGLkU | "Inside the mind of a master procrastinator" — Tim Urban TED, ~14m, ~2400-word transcript. |

## Local fixture

| File | Source | Notes |
|---|---|---|
| `zoo.mp4` | YouTube `jNQXAC9IVRw`, downloaded as mp4 | ~600KB, 19s. Used by Whisper path tests. To regenerate: `yt-dlp -f "best[ext=mp4][filesize<25M]/best[ext=mp4]" --max-filesize 25M -o zoo.%(ext)s "https://www.youtube.com/watch?v=jNQXAC9IVRw"`. |
