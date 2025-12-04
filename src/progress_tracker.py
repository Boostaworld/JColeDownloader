"""
Progress tracking for downloads.
Saves state so you can resume after crashes.
"""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime
from config import PROGRESS_FILE, FAILED_FILE


class ProgressTracker:
    """
    Tracks download progress with checkmarks.
    Persists to JSON so you can resume after crashes.
    """
    
    def __init__(self, progress_file: Path = PROGRESS_FILE):
        self.progress_file = progress_file
        self.data = self._load()
    
    def _load(self) -> dict:
        """Load progress from file."""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return self._empty_progress()
        return self._empty_progress()
    
    def _empty_progress(self) -> dict:
        """Create empty progress structure."""
        return {
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "stats": {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "pending": 0
            },
            "songs": {}  # song_id -> status dict
        }
    
    def _save(self):
        """Save progress to file."""
        self.data["last_updated"] = datetime.now().isoformat()
        self._update_stats()
        
        with open(self.progress_file, 'w') as f:
            json.dump(self.data, f, indent=2)
    
    def _update_stats(self):
        """Recalculate stats from songs."""
        songs = self.data["songs"]
        self.data["stats"] = {
            "total": len(songs),
            "completed": sum(1 for s in songs.values() if s.get("completed")),
            "failed": sum(1 for s in songs.values() if s.get("failed")),
            "pending": sum(1 for s in songs.values() if not s.get("completed") and not s.get("failed"))
        }
    
    def initialize_songs(self, songs: list):
        """
        Initialize progress for a list of songs.
        Preserves existing progress for songs already tracked.
        """
        for song in songs:
            song_id = str(song["id"])
            
            # Don't overwrite existing entries
            if song_id not in self.data["songs"]:
                self.data["songs"][song_id] = {
                    "id": song["id"],
                    "title": song["title"],
                    "artist": song["artist"],
                    "full_title": song.get("full_title", ""),
                    "completed": False,
                    "failed": False,
                    "filepath": None,
                    "error": None,
                    "attempts": 0,
                    "added_at": datetime.now().isoformat()
                }
        
        self._save()
        print(f"📋 Progress tracker initialized with {len(songs)} songs")
    
    def mark_completed(self, song_id: int, filepath: str):
        """Mark a song as successfully downloaded."""
        song_id = str(song_id)
        if song_id in self.data["songs"]:
            self.data["songs"][song_id].update({
                "completed": True,
                "failed": False,
                "filepath": filepath,
                "error": None,
                "completed_at": datetime.now().isoformat()
            })
            self._save()
    
    def mark_failed(self, song_id: int, error: str):
        """Mark a song as failed."""
        song_id = str(song_id)
        if song_id in self.data["songs"]:
            self.data["songs"][song_id]["attempts"] += 1
            self.data["songs"][song_id].update({
                "failed": True,
                "error": error,
                "failed_at": datetime.now().isoformat()
            })
            self._save()
    
    def is_completed(self, song_id: int) -> bool:
        """Check if a song has the checkmark (completed)."""
        song_id = str(song_id)
        return self.data["songs"].get(song_id, {}).get("completed", False)
    
    def get_pending_songs(self) -> list:
        """Get all songs that haven't been downloaded yet."""
        pending = []
        for song_id, song in self.data["songs"].items():
            if not song.get("completed"):
                pending.append(song)
        return pending
    
    def get_failed_songs(self) -> list:
        """Get all songs that failed to download."""
        return [s for s in self.data["songs"].values() if s.get("failed")]
    
    def get_completed_songs(self) -> list:
        """Get all successfully downloaded songs."""
        return [s for s in self.data["songs"].values() if s.get("completed")]
    
    def get_stats(self) -> dict:
        """Get current stats."""
        self._update_stats()
        return self.data["stats"]
    
    def clear_progress(self):
        """Clear all progress (reset everything)."""
        self.data = self._empty_progress()
        self._save()
        print("🗑️  Progress cleared")
    
    def clear_failed(self):
        """Reset failed songs to pending (for retry)."""
        count = 0
        for song in self.data["songs"].values():
            if song.get("failed") and not song.get("completed"):
                song["failed"] = False
                song["error"] = None
                count += 1
        self._save()
        print(f"🔄 Reset {count} failed songs to pending")
    
    def print_status(self):
        """Print current progress status."""
        stats = self.get_stats()
        
        print("\n" + "=" * 50)
        print("📊 DOWNLOAD PROGRESS")
        print("=" * 50)
        print(f"   Total songs:     {stats['total']}")
        print(f"   ✅ Completed:    {stats['completed']}")
        print(f"   ❌ Failed:       {stats['failed']}")
        print(f"   ⏳ Pending:      {stats['pending']}")
        
        if stats['total'] > 0:
            pct = (stats['completed'] / stats['total']) * 100
            print(f"\n   Progress: {pct:.1f}%")
            bar_len = 30
            filled = int(bar_len * stats['completed'] / stats['total'])
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"   [{bar}]")
        
        print("=" * 50)


def save_failed_log(failed_songs: list):
    """Save detailed log of failed downloads."""
    with open(FAILED_FILE, 'w') as f:
        json.dump({
            "exported_at": datetime.now().isoformat(),
            "count": len(failed_songs),
            "songs": failed_songs
        }, f, indent=2)
    print(f"📝 Failed songs log saved to {FAILED_FILE}")


if __name__ == "__main__":
    # Test the tracker
    tracker = ProgressTracker()
    tracker.print_status()
