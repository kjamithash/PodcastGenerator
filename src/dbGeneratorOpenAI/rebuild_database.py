#!/usr/bin/env python3
"""
Mental Models Database Builder

This script rebuilds the mental_models.db database from scratch by:
1. Importing mental models from Excel
2. Importing episodes from RSS feed
3. Matching transcripts from DOCX files
4. Transcribing missing episodes using Whisper AI

Usage:
    python rebuild_database.py [--skip-whisper] [--db DATABASE_PATH]

Options:
    --skip-whisper    Skip Whisper transcription (only use existing DOCX files)
    --db PATH         Database path (default: mental_models.db)
    --episodes-root   Episodes folder path
    --yes             Skip confirmation prompts
"""

import argparse
import sys
import os
from pathlib import Path

# Import from mm_tool
from mm_tool import (
    ensure_schema,
    get_conn,
    import_models_from_excel,
    import_rss,
    canonicalize_name
)


def rebuild_database(db_path: str, excel_path: str, rss_url: str,
                     episodes_root: str, skip_whisper: bool = False,
                     skip_confirm: bool = False):
    """Rebuild the database from scratch."""

    print("=" * 100)
    print("MENTAL MODELS DATABASE BUILDER")
    print("=" * 100)
    print()
    print(f"Database: {db_path}")
    print(f"Excel: {excel_path}")
    print(f"RSS Feed: {rss_url}")
    print(f"Episodes Root: {episodes_root}")
    print(f"Skip Whisper: {skip_whisper}")
    print()

    if not skip_confirm:
        confirm = input("This will rebuild the database. Continue? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

    # Step 1: Initialize database
    print("\n" + "=" * 100)
    print("STEP 1: Initialize Database Schema")
    print("=" * 100)
    conn = get_conn(db_path)
    ensure_schema(conn)
    conn.close()
    print("✓ Database schema created")

    # Step 2: Import mental models from Excel
    print("\n" + "=" * 100)
    print("STEP 2: Import Mental Models from Excel")
    print("=" * 100)
    import_models_from_excel(db_path, excel_path)
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM mental_models")
    count = cur.fetchone()[0]
    conn.close()
    print(f"✓ Imported {count} mental models")

    # Step 3: Import episodes from RSS
    print("\n" + "=" * 100)
    print("STEP 3: Import Episodes from RSS Feed")
    print("=" * 100)
    import_rss(db_path, rss_url)
    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL")
    count = cur.fetchone()[0]
    conn.close()
    print(f"✓ Imported {count} episodes from RSS")

    # Step 4: Scan and match transcripts from DOCX files
    print("\n" + "=" * 100)
    print("STEP 4: Scan and Match Transcripts from DOCX Files")
    print("=" * 100)
    # Import scan-transcripts functionality from mmtool
    import sys
    sys.path.insert(0, str(Path(__file__).parent / "mmtool"))
    from transcripts import scan_transcripts_cmd

    class Args:
        db = db_path
        episodes_root = episodes_root

    scan_transcripts_cmd(Args())

    conn = get_conn(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM episodes WHERE transcript IS NOT NULL AND rss_guid IS NOT NULL")
    count = cur.fetchone()[0]
    conn.close()
    print(f"✓ Matched {count} transcripts from DOCX files")

    # Step 5: Transcribe missing episodes with Whisper
    if not skip_whisper:
        print("\n" + "=" * 100)
        print("STEP 5: Transcribe Missing Episodes with Whisper AI")
        print("=" * 100)

        # Import and run transcription
        from transcribe_missing_episodes import transcribe_missing_episodes
        transcribe_missing_episodes(
            db_path=db_path,
            episodes_root=episodes_root,
            output_dir="./generated_transcripts",
            test_mode=False,
            specific_episodes=None,
            update_db=True,
            skip_confirm=skip_confirm
        )
    else:
        print("\n" + "=" * 100)
        print("STEP 5: Whisper Transcription (SKIPPED)")
        print("=" * 100)
        print("Use --no-skip-whisper to enable Whisper transcription")

    # Final summary
    print("\n" + "=" * 100)
    print("DATABASE REBUILD COMPLETE")
    print("=" * 100)

    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM mental_models")
    models_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL")
    episodes_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL AND transcript IS NOT NULL")
    transcripts_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL AND (transcript IS NULL OR LENGTH(TRIM(transcript)) = 0)")
    missing_count = cur.fetchone()[0]

    conn.close()

    print(f"\nMental Models: {models_count}")
    print(f"RSS Episodes: {episodes_count}")
    print(f"With Transcripts: {transcripts_count} ({transcripts_count*100//episodes_count}%)")
    print(f"Missing Transcripts: {missing_count}")
    print()
    print(f"✓ Database saved to: {db_path}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild the Mental Models database from scratch"
    )
    parser.add_argument(
        "--db",
        default="mental_models.db",
        help="Path to database file (default: mental_models.db)"
    )
    parser.add_argument(
        "--excel",
        default="MentalModels_reorder.xlsx",
        help="Path to Excel file with mental models (default: MentalModels_reorder.xlsx)"
    )
    parser.add_argument(
        "--rss",
        default="https://anchor.fm/s/f7f821ac/podcast/rss",
        help="RSS feed URL (default: Mental Models Daily feed)"
    )
    parser.add_argument(
        "--episodes-root",
        default="/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/MentalModels/Insta post automation/Episodes",
        help="Root folder containing episode transcripts and audio files"
    )
    parser.add_argument(
        "--skip-whisper",
        action="store_true",
        help="Skip Whisper transcription (only use existing DOCX files)"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    # Validate paths
    if not os.path.exists(args.excel):
        print(f"ERROR: Excel file not found: {args.excel}")
        sys.exit(1)

    if not os.path.exists(args.episodes_root):
        print(f"ERROR: Episodes folder not found: {args.episodes_root}")
        sys.exit(1)

    # Rebuild database
    rebuild_database(
        db_path=args.db,
        excel_path=args.excel,
        rss_url=args.rss,
        episodes_root=args.episodes_root,
        skip_whisper=args.skip_whisper,
        skip_confirm=args.yes
    )


if __name__ == "__main__":
    main()
