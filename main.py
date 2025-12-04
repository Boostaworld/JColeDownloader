#!/usr/bin/env python3
"""
J. Cole Complete Discography Downloader

A fast, resumable downloader that:
1. Scrapes all J. Cole songs from Genius (with caching)
2. Filters to only songs where he performs (not just produces)
3. Downloads from YouTube with progress tracking
4. Resumes from where it left off after crashes

Usage:
    python main.py                  # Run full pipeline
    python main.py --status         # Show current progress
    python main.py --scrape-only    # Just scrape Genius (no download)
    python main.py --retry-failed   # Retry failed downloads
    python main.py --clear-progress # Reset all progress
    python main.py --clear-cache    # Force re-scrape from Genius
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import (
    GENIUS_ACCESS_TOKEN,
    DOWNLOADS_DIR,
    AUDIO_FORMAT,
    AUDIO_QUALITY,
    CONCURRENT_DOWNLOADS
)
from src.genius_scraper import scrape_jcole_songs, GeniusScraper
from src.progress_tracker import ProgressTracker, save_failed_log
from src.downloader import BulkDownloader, check_ytdlp


def print_banner():
    """Print the startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║     J. COLE COMPLETE DISCOGRAPHY DOWNLOADER                  ║
║                                                              ║
║     🎤 Performer songs only (no producer-only credits)       ║
║     💾 Cached scraping (won't re-scrape on restart)          ║
║     ✅ Progress tracking (resume after crashes)              ║
╚══════════════════════════════════════════════════════════════╝
    """)


def check_requirements():
    """Verify all requirements are met."""
    errors = []
    
    # Check Genius token
    if GENIUS_ACCESS_TOKEN == "YOUR_TOKEN_HERE":
        errors.append("❌ GENIUS_ACCESS_TOKEN not set in config.py")
        errors.append("   Get your token from: https://genius.com/api-clients")
    
    # Check yt-dlp
    if not check_ytdlp():
        errors.append("❌ yt-dlp not found")
        errors.append("   Install with: pip install yt-dlp")
    
    if errors:
        print("\n⚠️  SETUP REQUIRED:\n")
        for e in errors:
            print(f"   {e}")
        print()
        return False
    
    return True


def cmd_status(tracker: ProgressTracker):
    """Show current download status."""
    tracker.print_status()
    
    # Show some pending songs
    pending = tracker.get_pending_songs()
    if pending:
        print(f"\n⏳ Next 5 pending songs:")
        for song in pending[:5]:
            print(f"   • {song['title']}")
    
    # Show recent failures
    failed = tracker.get_failed_songs()
    if failed:
        print(f"\n❌ Recent failures:")
        for song in failed[:5]:
            print(f"   • {song['title']}: {song.get('error', 'Unknown error')[:50]}")


def cmd_scrape_only():
    """Just scrape Genius without downloading."""
    print("\n🔍 Scraping Genius for J. Cole songs...")
    
    songs = scrape_jcole_songs(use_cache=False, fetch_full_details=False)
    
    print(f"\n✅ Found {len(songs)} performer songs")
    print("\n🎵 Sample songs:")
    for song in songs[:15]:
        role_icon = "👑" if song['role'] == 'primary' else "🎤"
        print(f"   {role_icon} {song['full_title']}")
    
    # Initialize progress tracker with these songs
    tracker = ProgressTracker()
    tracker.initialize_songs(songs)
    
    print(f"\n💾 Songs cached. Run without --scrape-only to start downloading.")


def cmd_clear_progress(tracker: ProgressTracker):
    """Clear all progress."""
    confirm = input("⚠️  This will reset ALL download progress. Continue? (y/N): ")
    if confirm.lower() == 'y':
        tracker.clear_progress()
        print("✅ Progress cleared")
    else:
        print("Cancelled")


def cmd_clear_cache():
    """Clear the Genius cache."""
    scraper = GeniusScraper()
    scraper.clear_cache()
    print("✅ Cache cleared. Next run will re-scrape from Genius.")


def cmd_retry_failed(tracker: ProgressTracker):
    """Retry failed downloads."""
    failed = tracker.get_failed_songs()
    
    if not failed:
        print("✅ No failed downloads to retry")
        return
    
    print(f"\n🔄 Retrying {len(failed)} failed downloads...")
    
    # Reset failed status
    tracker.clear_failed()
    
    # Run downloader on pending (which now includes former failures)
    downloader = BulkDownloader(progress_tracker=tracker)
    pending = tracker.get_pending_songs()
    
    stats = downloader.download_all(pending, parallel=False)
    
    print(f"\n📊 Retry results:")
    print(f"   ✅ Completed: {stats['completed']}")
    print(f"   ❌ Still failed: {stats['failed']}")


def cmd_run_full(tracker: ProgressTracker, parallel: bool = False):
    """Run the full pipeline: scrape + download."""
    
    # Step 1: Get songs (from cache if available)
    print("\n📥 STEP 1: Getting song list...")
    songs = scrape_jcole_songs(use_cache=True, fetch_full_details=False)
    
    if not songs:
        print("❌ No songs found!")
        return
    
    # Step 2: Initialize progress tracker
    print("\n📋 STEP 2: Initializing progress tracker...")
    tracker.initialize_songs(songs)
    
    # Step 3: Get pending songs
    pending = tracker.get_pending_songs()
    
    if not pending:
        print("\n✅ All songs already downloaded!")
        tracker.print_status()
        return
    
    print(f"\n⏳ {len(pending)} songs pending download")
    
    # Step 4: Download
    print("\n📥 STEP 3: Downloading...")
    downloader = BulkDownloader(progress_tracker=tracker)
    
    try:
        stats = downloader.download_all(pending, parallel=parallel)
    except KeyboardInterrupt:
        print("\n\n⏸️  Download interrupted. Progress saved!")
        tracker.print_status()
        return
    
    # Step 5: Report
    print("\n" + "=" * 50)
    print("📊 DOWNLOAD COMPLETE")
    print("=" * 50)
    print(f"   ✅ Completed: {stats['completed']}")
    print(f"   ❌ Failed:    {stats['failed']}")
    print(f"   ⏭️  Skipped:   {stats['skipped']}")
    print(f"\n   Files saved to: {DOWNLOADS_DIR}")
    
    # Save failed log if any
    failed = tracker.get_failed_songs()
    if failed:
        save_failed_log(failed)
        print(f"   Failed songs logged for retry")
    
    tracker.print_status()


def main():
    parser = argparse.ArgumentParser(
        description="J. Cole Complete Discography Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                    # Run full download
  python main.py --status           # Check progress
  python main.py --scrape-only      # Just get song list
  python main.py --retry-failed     # Retry failed downloads
  python main.py --parallel         # Use parallel downloads (faster)
  python main.py --clear-progress   # Reset download progress
  python main.py --clear-cache      # Force re-scrape from Genius
        """
    )
    
    parser.add_argument('--status', action='store_true',
                        help='Show current download progress')
    parser.add_argument('--scrape-only', action='store_true',
                        help='Only scrape Genius, don\'t download')
    parser.add_argument('--retry-failed', action='store_true',
                        help='Retry failed downloads')
    parser.add_argument('--clear-progress', action='store_true',
                        help='Clear all download progress')
    parser.add_argument('--clear-cache', action='store_true',
                        help='Clear Genius cache (force re-scrape)')
    parser.add_argument('--parallel', action='store_true',
                        help=f'Use parallel downloads ({CONCURRENT_DOWNLOADS} threads)')
    
    args = parser.parse_args()
    
    print_banner()
    
    # Initialize tracker
    tracker = ProgressTracker()
    
    # Handle commands
    if args.status:
        cmd_status(tracker)
    
    elif args.scrape_only:
        if not check_requirements():
            return
        cmd_scrape_only()
    
    elif args.clear_progress:
        cmd_clear_progress(tracker)
    
    elif args.clear_cache:
        cmd_clear_cache()
    
    elif args.retry_failed:
        if not check_requirements():
            return
        cmd_retry_failed(tracker)
    
    else:
        # Full run
        if not check_requirements():
            return
        cmd_run_full(tracker, parallel=args.parallel)


if __name__ == "__main__":
    main()
