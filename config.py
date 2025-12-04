"""
Configuration for J. Cole Discography Downloader
"""
import os
from pathlib import Path

# === PATHS ===
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DOWNLOADS_DIR = BASE_DIR / "downloads"
LOGS_DIR = BASE_DIR / "logs"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# === FILES ===
SONGS_CACHE_FILE = DATA_DIR / "songs_cache.json"      # All discovered songs
PROGRESS_FILE = DATA_DIR / "progress.json"            # Download progress tracking
FAILED_FILE = DATA_DIR / "failed_downloads.json"      # Failed downloads for retry

# === API ===
# Get your token from: https://genius.com/api-clients
GENIUS_ACCESS_TOKEN = os.getenv("GENIUS_ACCESS_TOKEN", "YOUR_TOKEN_HERE")

# J. Cole's Genius artist ID (pre-looked up for speed)
JCOLE_ARTIST_ID = 69985
JCOLE_NAME = "J. Cole"

# === DOWNLOAD SETTINGS ===
AUDIO_FORMAT = "mp3"           # mp3 is faster than flac
AUDIO_QUALITY = "192"          # 192kbps is good balance of speed/quality (use "320" for best, "128" for fastest)
CONCURRENT_DOWNLOADS = 3       # Parallel downloads (be careful, too high = rate limits)

# === RATE LIMITING (to avoid bans) ===
GENIUS_DELAY = 0.5             # Seconds between Genius API calls
YOUTUBE_DELAY = 2.0            # Seconds between YouTube downloads
MAX_RETRIES = 3                # Retry failed downloads

# === FILTERING ===
EXCLUDE_TERMS = [
    "(Remix)",
    "(Live)", 
    "(Instrumental)",
    "(Karaoke)",
    "(Cover)",
]

# Include these (even if they have exclude terms)
INCLUDE_IF_JCOLE_PRIMARY = True  # Always include if J. Cole is primary artist
