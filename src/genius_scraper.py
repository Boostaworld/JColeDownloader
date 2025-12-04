"""
Genius API client with aggressive caching to avoid re-scraping.
Filters songs where J. Cole performs (not just produces).
"""
import json
import time
import requests
from pathlib import Path
from typing import Optional
from config import (
    GENIUS_ACCESS_TOKEN, 
    JCOLE_ARTIST_ID, 
    JCOLE_NAME,
    SONGS_CACHE_FILE,
    GENIUS_DELAY,
    EXCLUDE_TERMS,
    INCLUDE_IF_JCOLE_PRIMARY
)

class GeniusScraper:
    BASE_URL = "https://api.genius.com"
    
    def __init__(self, access_token: str = GENIUS_ACCESS_TOKEN):
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}"
        })
        self._cache = None
    
    def _request(self, endpoint: str, params: dict = None) -> dict:
        """Make rate-limited API request."""
        url = f"{self.BASE_URL}{endpoint}"
        time.sleep(GENIUS_DELAY)  # Rate limit
        
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json()["response"]
    
    def get_artist_songs(self, artist_id: int = JCOLE_ARTIST_ID, 
                         max_songs: int = None,
                         use_cache: bool = True) -> list:
        """
        Get ALL songs for an artist from Genius.
        Caches results to avoid re-scraping.
        """
        # Check cache first
        if use_cache and SONGS_CACHE_FILE.exists():
            print(f"📁 Loading cached songs from {SONGS_CACHE_FILE}")
            with open(SONGS_CACHE_FILE, 'r') as f:
                cached = json.load(f)
                if cached.get("artist_id") == artist_id:
                    songs = cached.get("songs", [])
                    print(f"✅ Found {len(songs)} cached songs")
                    return songs
        
        print(f"🔍 Fetching songs from Genius API (this may take a few minutes)...")
        all_songs = []
        page = 1
        per_page = 50  # Max allowed by API
        
        while True:
            print(f"   Fetching page {page}...", end=" ")
            
            try:
                data = self._request(
                    f"/artists/{artist_id}/songs",
                    params={
                        "page": page,
                        "per_page": per_page,
                        "sort": "title"
                    }
                )
            except requests.exceptions.RequestException as e:
                print(f"❌ API error: {e}")
                break
            
            songs = data.get("songs", [])
            if not songs:
                print("done!")
                break
            
            print(f"got {len(songs)} songs")
            all_songs.extend(songs)
            
            if max_songs and len(all_songs) >= max_songs:
                all_songs = all_songs[:max_songs]
                break
            
            # Check for next page
            next_page = data.get("next_page")
            if next_page is None:
                break
            page = next_page
        
        # Cache results
        self._save_cache(artist_id, all_songs)
        
        return all_songs
    
    def get_song_details(self, song_id: int) -> dict:
        """Get full song details including all credits."""
        data = self._request(f"/songs/{song_id}")
        return data.get("song", {})
    
    def filter_performer_songs(self, songs: list, 
                                artist_id: int = JCOLE_ARTIST_ID,
                                fetch_full_details: bool = True) -> list:
        """
        Filter songs where artist performs (not just produces).
        
        Args:
            songs: List of song objects from get_artist_songs
            artist_id: Artist ID to check for
            fetch_full_details: If True, fetch full song details for accurate role detection
                               (slower but more accurate)
        """
        performer_songs = []
        total = len(songs)
        
        print(f"\n🎤 Filtering {total} songs for performer credits...")
        
        for i, song in enumerate(songs, 1):
            title = song.get("title", "Unknown")
            
            # Quick filter: skip excluded terms (unless primary artist)
            if not INCLUDE_IF_JCOLE_PRIMARY:
                if any(term.lower() in title.lower() for term in EXCLUDE_TERMS):
                    continue
            
            # Check primary artist (quick check from list data)
            primary_artist = song.get("primary_artist", {})
            is_primary = primary_artist.get("id") == artist_id
            
            if is_primary:
                # Definitely a performer song
                performer_songs.append(self._format_song(song, role="primary"))
                if i % 20 == 0:
                    print(f"   Processed {i}/{total} songs...")
                continue
            
            # For featured songs, we need full details to check credits
            if fetch_full_details:
                try:
                    full_song = self.get_song_details(song["id"])
                    role = self._get_artist_role(full_song, artist_id)
                    
                    if role in ["primary", "featured"]:
                        performer_songs.append(self._format_song(full_song, role=role))
                    
                except Exception as e:
                    # If we can't get details, include it to be safe
                    performer_songs.append(self._format_song(song, role="unknown"))
            else:
                # Without full details, include featured artists from list data
                featured_artists = song.get("featured_artists", [])
                is_featured = any(a.get("id") == artist_id for a in featured_artists)
                
                if is_featured:
                    performer_songs.append(self._format_song(song, role="featured"))
            
            if i % 20 == 0:
                print(f"   Processed {i}/{total} songs...")
        
        print(f"✅ Found {len(performer_songs)} songs where {JCOLE_NAME} performs")
        return performer_songs
    
    def _get_artist_role(self, song: dict, artist_id: int) -> str:
        """Determine artist's role in a song."""
        # Check primary
        if song.get("primary_artist", {}).get("id") == artist_id:
            return "primary"
        
        # Check featured
        for artist in song.get("featured_artists", []):
            if artist.get("id") == artist_id:
                return "featured"
        
        # Check producer (we want to EXCLUDE these)
        for artist in song.get("producer_artists", []):
            if artist.get("id") == artist_id:
                return "producer"
        
        # Check writer
        for artist in song.get("writer_artists", []):
            if artist.get("id") == artist_id:
                return "writer"
        
        return "none"
    
    def _format_song(self, song: dict, role: str) -> dict:
        """Format song data for our needs."""
        primary_artist = song.get("primary_artist", {})
        
        return {
            "id": song.get("id"),
            "title": song.get("title", "Unknown"),
            "artist": primary_artist.get("name", JCOLE_NAME),
            "full_title": song.get("full_title", ""),
            "url": song.get("url", ""),
            "release_date": song.get("release_date_for_display", ""),
            "role": role,  # primary, featured, producer, writer
            "album": song.get("album", {}).get("name") if song.get("album") else None,
        }
    
    def _save_cache(self, artist_id: int, songs: list):
        """Save songs to cache file."""
        cache_data = {
            "artist_id": artist_id,
            "artist_name": JCOLE_NAME,
            "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_songs": len(songs),
            "songs": songs
        }
        
        with open(SONGS_CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        
        print(f"💾 Cached {len(songs)} songs to {SONGS_CACHE_FILE}")
    
    def clear_cache(self):
        """Delete the cache file to force re-scrape."""
        if SONGS_CACHE_FILE.exists():
            SONGS_CACHE_FILE.unlink()
            print("🗑️  Cache cleared")
        else:
            print("ℹ️  No cache to clear")


def scrape_jcole_songs(use_cache: bool = True, 
                       fetch_full_details: bool = False) -> list:
    """
    Main function to get all J. Cole performer songs.
    
    Args:
        use_cache: Use cached results if available
        fetch_full_details: Fetch full song details for accurate role detection
                           (slower but catches edge cases)
    
    Returns:
        List of song dicts with: id, title, artist, full_title, url, role
    """
    scraper = GeniusScraper()
    
    # Get all songs
    all_songs = scraper.get_artist_songs(use_cache=use_cache)
    
    # Filter to only performer songs
    performer_songs = scraper.filter_performer_songs(
        all_songs, 
        fetch_full_details=fetch_full_details
    )
    
    return performer_songs


if __name__ == "__main__":
    # Test the scraper
    print("=" * 50)
    print("J. Cole Discography Scraper")
    print("=" * 50)
    
    songs = scrape_jcole_songs(use_cache=True, fetch_full_details=False)
    
    print(f"\n📊 Results:")
    print(f"   Total performer songs: {len(songs)}")
    
    # Show sample
    print(f"\n🎵 Sample songs:")
    for song in songs[:10]:
        print(f"   [{song['role']}] {song['full_title']}")
