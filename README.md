# J. Cole Complete Discography Downloader

A fast, resumable Python tool that downloads every J. Cole song (including features and unreleased tracks) from YouTube.

## Features

- **Smart Scraping**: Pulls all songs from Genius API, filters to only songs where J. Cole actually performs (not producer-only credits)
- **Caching**: Song list is cached locally - won't re-scrape Genius on restart
- **Progress Tracking**: Checkmarks for completed downloads, resumes after crashes
- **Speed Optimized**: MP3 format, parallel fragment downloads, configurable quality
- **Retry Logic**: Automatically retries failed downloads

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Get a Genius API Token

1. Go to https://genius.com/api-clients
2. Create a new API client
3. Copy the "Client Access Token"
4. Edit `config.py` and paste your token:

```python
GENIUS_ACCESS_TOKEN = "your_token_here"
```

### 3. Run It

```bash
# Full download (scrape + download)
python main.py

# Check progress
python main.py --status

# Retry failed downloads
python main.py --retry-failed
```

## Commands

| Command | Description |
|---------|-------------|
| `python main.py` | Run full pipeline (scrape + download) |
| `python main.py --status` | Show download progress |
| `python main.py --scrape-only` | Just scrape Genius, don't download |
| `python main.py --retry-failed` | Retry failed downloads |
| `python main.py --parallel` | Use parallel downloads (faster, riskier) |
| `python main.py --clear-progress` | Reset all download progress |
| `python main.py --clear-cache` | Force re-scrape from Genius |

## Configuration

Edit `config.py` to customize:

```python
# Audio settings
AUDIO_FORMAT = "mp3"      # mp3 is fastest
AUDIO_QUALITY = "192"     # 128=fast, 192=balanced, 320=best

# Speed vs safety
CONCURRENT_DOWNLOADS = 3  # Parallel downloads
YOUTUBE_DELAY = 2.0       # Seconds between downloads

# Filtering
EXCLUDE_TERMS = ["(Remix)", "(Live)", "(Instrumental)"]
```

## File Structure

```
jcole-downloader/
├── main.py              # Run this
├── config.py            # Settings
├── requirements.txt
├── data/
│   ├── songs_cache.json     # Cached song list (don't delete!)
│   ├── progress.json        # Download checkmarks
│   └── failed_downloads.json
├── downloads/           # Your music goes here
└── src/
    ├── genius_scraper.py
    ├── progress_tracker.py
    └── downloader.py
```

## Progress Tracking

The `progress.json` file tracks every song with:
- ✅ `completed: true` - Downloaded successfully
- ❌ `failed: true` - Failed (with error message)
- ⏳ Neither - Pending download

When you restart, only pending songs are downloaded.

### Viewing Progress

```bash
python main.py --status
```

Output:
```
📊 DOWNLOAD PROGRESS
══════════════════════════════
   Total songs:     347
   ✅ Completed:    285
   ❌ Failed:       12
   ⏳ Pending:      50

   Progress: 82.1%
   [████████████████████░░░░░░░░░]
```

## Troubleshooting

### "No matching video found on YouTube"

Some songs (especially unreleased/rare tracks) may not be on YouTube. These are logged in `failed_downloads.json`.

### Downloads are slow

1. Use `--parallel` flag for concurrent downloads
2. Lower quality in config: `AUDIO_QUALITY = "128"`
3. Make sure you have good internet

### Rate limited by YouTube

1. Increase `YOUTUBE_DELAY` in config
2. Don't use `--parallel`
3. Wait a few hours and retry

### Progress not saving

Make sure `data/` directory exists and is writable.

## How It Works

1. **Genius Scraper**: Fetches all songs associated with J. Cole from Genius API
2. **Role Filter**: Checks each song's credits - only keeps songs where J. Cole is listed as primary artist OR featured artist (excludes producer-only)
3. **YouTube Matcher**: Searches YouTube for each song, scores results by relevance
4. **Downloader**: Uses yt-dlp to extract audio, converts to MP3

## Legal Note

This tool is for personal use only. Respect copyright laws in your jurisdiction.
