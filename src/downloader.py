"""
YouTube downloader using yt-dlp with speed optimizations.
Handles searching, downloading, and error recovery.
"""
import os
import re
import time
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import (
    DOWNLOADS_DIR,
    AUDIO_FORMAT,
    AUDIO_QUALITY,
    YOUTUBE_DELAY,
    MAX_RETRIES,
    CONCURRENT_DOWNLOADS
)

# Check if yt-dlp is available
def check_ytdlp() -> bool:
    """Check if yt-dlp is installed."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def sanitize_filename(name: str) -> str:
    """Make a string safe for use as a filename."""
    # Remove or replace problematic characters
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Limit length
    if len(name) > 200:
        name = name[:200]
    return name


def search_youtube(query: str, max_results: int = 5) -> list:
    """
    Search YouTube and return video info.
    Returns list of dicts with: id, title, duration, url
    """
    try:
        result = subprocess.run(
            [
                "yt-dlp",
                f"ytsearch{max_results}:{query}",
                "--dump-json",
                "--no-download",
                "--no-warnings",
                "--quiet"
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            return []
        
        videos = []
        for line in result.stdout.strip().split('\n'):
            if line:
                import json
                try:
                    data = json.loads(line)
                    videos.append({
                        "id": data.get("id"),
                        "title": data.get("title"),
                        "duration": data.get("duration", 0),
                        "url": f"https://www.youtube.com/watch?v={data.get('id')}",
                        "uploader": data.get("uploader", "")
                    })
                except json.JSONDecodeError:
                    continue
        
        return videos
    
    except subprocess.TimeoutExpired:
        return []
    except Exception as e:
        print(f"Search error: {e}")
        return []


def score_video(video: dict, artist: str, title: str) -> int:
    """Score a video for how likely it's the right one."""
    score = 0
    video_title = video.get("title", "").lower()
    
    # Artist name present: +3
    if artist.lower() in video_title:
        score += 3
    
    # Song title present: +3
    if title.lower() in video_title:
        score += 3
    
    # "Official" in title: +2
    if "official" in video_title:
        score += 2
    
    # "Audio" in title (official audio): +1
    if "audio" in video_title:
        score += 1
    
    # VEVO or official channel: +2
    uploader = video.get("uploader", "").lower()
    if "vevo" in uploader or artist.lower() in uploader:
        score += 2
    
    # Avoid covers/remixes/live: -3
    bad_terms = ["cover", "remix", "karaoke", "live", "instrumental", "reaction"]
    if any(term in video_title for term in bad_terms):
        score -= 3
    
    # Reasonable duration (1.5-10 min): +1
    duration = video.get("duration", 0)
    if 90 <= duration <= 600:
        score += 1
    
    return score


def find_best_match(artist: str, title: str) -> Optional[dict]:
    """Search YouTube and return the best matching video."""
    # Build search query
    query = f"{artist} {title} official audio"
    
    videos = search_youtube(query, max_results=5)
    
    if not videos:
        # Try simpler query
        query = f"{artist} {title}"
        videos = search_youtube(query, max_results=5)
    
    if not videos:
        return None
    
    # Score and pick best
    scored = [(score_video(v, artist, title), v) for v in videos]
    scored.sort(key=lambda x: x[0], reverse=True)
    
    best_score, best_video = scored[0]
    
    # Minimum score threshold
    if best_score < 3:
        return None
    
    return best_video


def download_audio(url: str, output_path: Path, 
                   format: str = AUDIO_FORMAT,
                   quality: str = AUDIO_QUALITY) -> Tuple[bool, str]:
    """
    Download audio from URL.
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Build yt-dlp command for SPEED
    cmd = [
        "yt-dlp",
        url,
        "-x",  # Extract audio
        "--audio-format", format,
        "--audio-quality", quality,
        "-o", str(output_path),
        "--no-playlist",
        "--no-warnings",
        "--quiet",
        "--progress",
        # Speed optimizations
        "--concurrent-fragments", "4",  # Parallel fragment downloads
        "--buffer-size", "16K",
        "--no-check-certificates",  # Skip SSL verification (faster)
        # Avoid slow formats
        "--format", "bestaudio[ext=m4a]/bestaudio/best",
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 min timeout
        )
        
        if result.returncode == 0:
            # Find the actual output file (yt-dlp adds extension)
            expected_file = output_path.with_suffix(f".{format}")
            if expected_file.exists():
                return True, str(expected_file)
            
            # Check for file with original extension
            for ext in ['.m4a', '.webm', '.mp3', '.opus']:
                check_path = output_path.with_suffix(ext)
                if check_path.exists():
                    return True, str(check_path)
            
            return True, str(output_path)
        else:
            error = result.stderr or result.stdout or "Unknown error"
            return False, error[:200]
    
    except subprocess.TimeoutExpired:
        return False, "Download timed out (5 min limit)"
    except Exception as e:
        return False, str(e)[:200]


def download_song(song: dict, output_dir: Path = DOWNLOADS_DIR) -> Tuple[bool, str, Optional[str]]:
    """
    Search for and download a song.
    
    Args:
        song: Dict with 'title', 'artist', 'id' keys
        output_dir: Where to save the file
    
    Returns:
        Tuple of (success: bool, message: str, filepath: Optional[str])
    """
    title = song.get("title", "Unknown")
    artist = song.get("artist", "Unknown")
    song_id = song.get("id", 0)
    
    # Find on YouTube
    video = find_best_match(artist, title)
    
    if not video:
        return False, "No matching video found on YouTube", None
    
    # Build output filename
    filename = sanitize_filename(f"{artist} - {title}")
    output_path = output_dir / filename
    
    # Download with retries
    for attempt in range(MAX_RETRIES):
        success, result = download_audio(video["url"], output_path)
        
        if success:
            return True, f"Downloaded: {result}", result
        
        if attempt < MAX_RETRIES - 1:
            time.sleep(YOUTUBE_DELAY * (attempt + 1))  # Increasing delay
    
    return False, f"Failed after {MAX_RETRIES} attempts: {result}", None


class BulkDownloader:
    """
    Download multiple songs with progress tracking.
    Uses threading for parallel downloads (careful with rate limits).
    """
    
    def __init__(self, output_dir: Path = DOWNLOADS_DIR, 
                 progress_tracker = None):
        self.output_dir = output_dir
        self.progress = progress_tracker
        self.output_dir.mkdir(exist_ok=True)
    
    def download_all(self, songs: list, parallel: bool = False) -> dict:
        """
        Download all songs in list.
        
        Args:
            songs: List of song dicts
            parallel: Use parallel downloads (faster but risk rate limits)
        
        Returns:
            Dict with stats: completed, failed, skipped
        """
        stats = {"completed": 0, "failed": 0, "skipped": 0}
        total = len(songs)
        
        print(f"\n🎵 Starting download of {total} songs...")
        print(f"   Output directory: {self.output_dir}")
        print(f"   Format: {AUDIO_FORMAT} @ {AUDIO_QUALITY}kbps")
        print()
        
        if parallel and CONCURRENT_DOWNLOADS > 1:
            return self._download_parallel(songs, stats)
        else:
            return self._download_sequential(songs, stats)
    
    def _download_sequential(self, songs: list, stats: dict) -> dict:
        """Download songs one at a time (safer, no rate limits)."""
        total = len(songs)
        
        for i, song in enumerate(songs, 1):
            song_id = song.get("id")
            title = song.get("title", "Unknown")
            
            # Skip if already completed
            if self.progress and self.progress.is_completed(song_id):
                print(f"[{i}/{total}] ⏭️  Skipping (already downloaded): {title}")
                stats["skipped"] += 1
                continue
            
            print(f"[{i}/{total}] 🔍 Searching: {title}...", end=" ")
            
            success, message, filepath = download_song(song, self.output_dir)
            
            if success:
                print(f"✅")
                stats["completed"] += 1
                if self.progress:
                    self.progress.mark_completed(song_id, filepath)
            else:
                print(f"❌ {message}")
                stats["failed"] += 1
                if self.progress:
                    self.progress.mark_failed(song_id, message)
            
            # Rate limit between downloads
            time.sleep(YOUTUBE_DELAY)
        
        return stats
    
    def _download_parallel(self, songs: list, stats: dict) -> dict:
        """Download songs in parallel (faster but watch for rate limits)."""
        total = len(songs)
        
        # Filter out already completed
        pending = []
        for song in songs:
            if self.progress and self.progress.is_completed(song.get("id")):
                stats["skipped"] += 1
            else:
                pending.append(song)
        
        print(f"   Skipping {stats['skipped']} already downloaded")
        print(f"   Downloading {len(pending)} songs with {CONCURRENT_DOWNLOADS} threads")
        
        with ThreadPoolExecutor(max_workers=CONCURRENT_DOWNLOADS) as executor:
            futures = {
                executor.submit(download_song, song, self.output_dir): song 
                for song in pending
            }
            
            for i, future in enumerate(as_completed(futures), 1):
                song = futures[future]
                song_id = song.get("id")
                title = song.get("title", "Unknown")
                
                try:
                    success, message, filepath = future.result()
                    
                    if success:
                        print(f"[{i}/{len(pending)}] ✅ {title}")
                        stats["completed"] += 1
                        if self.progress:
                            self.progress.mark_completed(song_id, filepath)
                    else:
                        print(f"[{i}/{len(pending)}] ❌ {title}: {message}")
                        stats["failed"] += 1
                        if self.progress:
                            self.progress.mark_failed(song_id, message)
                
                except Exception as e:
                    print(f"[{i}/{len(pending)}] ❌ {title}: {e}")
                    stats["failed"] += 1
                    if self.progress:
                        self.progress.mark_failed(song_id, str(e))
        
        return stats


if __name__ == "__main__":
    # Test download
    if not check_ytdlp():
        print("❌ yt-dlp not found! Install with: pip install yt-dlp")
        exit(1)
    
    print("✅ yt-dlp found")
    
    # Test search
    print("\n🔍 Testing YouTube search...")
    results = search_youtube("J. Cole Middle Child", 3)
    for r in results:
        print(f"   {r['title']} ({r['duration']}s)")
