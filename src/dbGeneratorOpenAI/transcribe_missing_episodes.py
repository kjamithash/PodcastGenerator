#!/usr/bin/env python3
"""
Transcribe missing podcast episodes using OpenAI Whisper.

This script:
1. Gets the list of 41 missing episodes from the database
2. Finds the corresponding audio files (prefers non-_audacity.mp3 files)
3. Uses Whisper to transcribe them
4. Saves transcripts in DOCX format matching existing structure
5. Updates the database with the new transcripts

Usage:
    # Test with one episode
    python transcribe_missing_episodes.py --db mental_models.db --test

    # Transcribe all missing episodes
    python transcribe_missing_episodes.py --db mental_models.db

    # Transcribe specific episodes
    python transcribe_missing_episodes.py --db mental_models.db --episodes 199 200 201

Requirements:
    pip install openai-whisper python-docx
"""

import argparse
import datetime as dt
import os
import re
import sqlite3
import sys
from pathlib import Path

try:
    import whisper
except ImportError:
    print("ERROR: openai-whisper not installed.")
    print("Install with: pip install openai-whisper")
    print("\nNote: This will also install ffmpeg if not present.")
    sys.exit(1)

try:
    from docx import Document
    from docx.shared import Pt
except ImportError:
    print("ERROR: python-docx not installed.")
    print("Install with: pip install python-docx")
    sys.exit(1)

from rescan_and_match_transcripts import get_conn


def find_audio_file(episode_id: int, mental_model_name: str, episodes_root: str) -> str | None:
    """
    Find the audio file for an episode.

    Prefers the raw TTS file (without _audacity suffix) over the processed version.

    Returns:
        Path to audio file, or None if not found
    """
    if not mental_model_name:
        return None

    # Convert mental model name to filename format
    # E.g., "Bayes' Theorem" -> "BayesTheorem" or "Bayes_Theorem"
    base_name = re.sub(r"['\"/\\]", "", mental_model_name)
    base_name = re.sub(r"[^a-zA-Z0-9]+", "_", base_name)
    base_name = re.sub(r"_+", "_", base_name).strip("_")

    # Possible filename patterns
    possible_patterns = [
        base_name,
        base_name.replace("_", ""),
        mental_model_name.replace(" ", ""),
        mental_model_name.replace(" ", "_"),
        mental_model_name.replace("/", ""),
    ]

    # Search for audio files
    audio_files = []

    for root, dirs, files in os.walk(episodes_root):
        for fname in files:
            if not fname.lower().endswith(".mp3"):
                continue

            fname_lower = fname.lower()

            # Check if filename matches any pattern
            for pattern in possible_patterns:
                if pattern.lower() in fname_lower:
                    full_path = os.path.join(root, fname)
                    is_audacity = "_audacity" in fname_lower
                    audio_files.append((full_path, is_audacity))
                    break

    if not audio_files:
        return None

    # Prefer non-audacity files (raw TTS without music)
    non_audacity = [f for f, is_aud in audio_files if not is_aud]
    if non_audacity:
        return non_audacity[0]

    # Fall back to audacity version if that's all we have
    return audio_files[0][0]


def transcribe_audio(audio_path: str, model) -> str:
    """Transcribe audio file using Whisper."""
    print(f"  Transcribing: {os.path.basename(audio_path)}")
    print(f"  (This may take 2-5 minutes per episode...)")

    result = model.transcribe(audio_path, language="en", fp16=False)

    return result["text"]


def format_transcript(mental_model_name: str, transcript_text: str) -> str:
    """
    Format the transcript to match the existing podcast transcript structure.

    Returns formatted transcript text.
    """
    # Standard podcast intro
    intro = f"Welcome to Mental Models Daily, where we explore one mental model each day to help you elevate your daily decision making."

    # The transcript should already contain the mental model discussion
    # Just ensure it starts properly
    formatted = f"{intro}\n\n{transcript_text.strip()}"

    return formatted


def save_transcript_to_docx(mental_model_name: str, transcript_text: str, output_path: str):
    """Save transcript to a DOCX file."""
    doc = Document()

    # Add the transcript as a single paragraph
    # (matching the format of existing transcript files)
    p = doc.add_paragraph(transcript_text)
    p.style.font.size = Pt(12)

    doc.save(output_path)
    print(f"  ✓ Saved to: {output_path}")


def update_database_with_transcript(conn, episode_id: int, transcript_text: str,
                                    transcript_source: str):
    """Update the database with the new transcript."""
    cur = conn.cursor()
    now = dt.datetime.utcnow().isoformat(timespec="seconds")

    cur.execute("""
        UPDATE episodes
        SET transcript = ?,
            transcript_source = ?,
            transcript_index = 1,
            updated_at = ?
        WHERE id = ?
    """, (transcript_text, transcript_source, now, episode_id))

    conn.commit()


def transcribe_missing_episodes(db_path: str, episodes_root: str,
                               output_dir: str, test_mode: bool = False,
                               specific_episodes: list = None,
                               update_db: bool = True,
                               skip_confirm: bool = False):
    """Main function to transcribe missing episodes."""

    # Ask for confirmation upfront
    print(f"\n{'='*80}")
    print("WHISPER TRANSCRIPTION SETUP")
    print(f"{'='*80}")
    print(f"Database: {db_path}")
    print(f"Episodes root: {episodes_root}")
    print(f"Output directory: {output_dir}")
    print(f"Test mode: {test_mode}")
    print(f"Update database: {update_db}")

    if not test_mode and not specific_episodes and not skip_confirm:
        confirm = input("\n⚠️  This will transcribe all 41 missing episodes (~2-3 hours). Continue? (y/N): ").strip().lower()
        if confirm != 'y':
            print("Cancelled.")
            return

    print("\n📥 Loading Whisper model...")
    print("(This may take a minute on first run...)")

    try:
        # Load the medium model (good balance of speed and accuracy)
        model = whisper.load_model("medium")
        print("✓ Whisper model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading Whisper model: {e}")
        print("\nMake sure you have ffmpeg installed:")
        print("  brew install ffmpeg  (on macOS)")
        sys.exit(1)

    # Get missing episodes from database
    conn = get_conn(db_path)
    cur = conn.cursor()

    if specific_episodes:
        placeholders = ','.join('?' * len(specific_episodes))
        cur.execute(f"""
            SELECT e.id, e.title, mm.name as mental_model
            FROM episodes e
            LEFT JOIN mental_models mm ON e.mental_model_id = mm.id
            WHERE e.id IN ({placeholders})
              AND e.rss_guid IS NOT NULL
              AND (e.transcript IS NULL OR LENGTH(TRIM(e.transcript)) = 0)
            ORDER BY e.id
        """, specific_episodes)
    else:
        cur.execute("""
            SELECT e.id, e.title, mm.name as mental_model
            FROM episodes e
            LEFT JOIN mental_models mm ON e.mental_model_id = mm.id
            WHERE e.rss_guid IS NOT NULL
              AND (e.transcript IS NULL OR LENGTH(TRIM(e.transcript)) = 0)
            ORDER BY e.id
        """)

    missing_episodes = cur.fetchall()

    if not missing_episodes:
        print("\n✅ No episodes need transcription!")
        conn.close()
        return

    total = len(missing_episodes)
    if test_mode:
        missing_episodes = missing_episodes[:1]
        print(f"\n🧪 TEST MODE: Processing 1 episode (of {total} total)")
    else:
        print(f"\n📋 Found {total} episodes to transcribe")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Process each episode
    success_count = 0
    failed_count = 0

    for i, ep_row in enumerate(missing_episodes, 1):
        episode_id = ep_row["id"]
        episode_title = ep_row["title"]
        mental_model = ep_row["mental_model"]

        print(f"\n{'='*80}")
        print(f"[{i}/{len(missing_episodes)}] Episode {episode_id}: {mental_model or episode_title}")
        print(f"{'='*80}")

        # Find audio file
        audio_path = find_audio_file(episode_id, mental_model, episodes_root)

        if not audio_path:
            print(f"  ✗ Audio file not found for '{mental_model}'")
            failed_count += 1
            continue

        print(f"  Found audio: {os.path.relpath(audio_path, episodes_root)}")

        try:
            # Transcribe
            transcript_text = transcribe_audio(audio_path, model)

            # Format
            formatted_transcript = format_transcript(mental_model or episode_title, transcript_text)

            # Save to DOCX
            safe_filename = re.sub(r'[^\w\s-]', '', mental_model or episode_title).strip()
            safe_filename = re.sub(r'[-\s]+', '_', safe_filename)
            output_filename = f"{safe_filename}_transcript.docx"
            output_path = os.path.join(output_dir, output_filename)

            save_transcript_to_docx(mental_model or episode_title, formatted_transcript, output_path)

            # Update database
            if update_db:
                update_database_with_transcript(
                    conn,
                    episode_id,
                    formatted_transcript,
                    f"generated/{output_filename}"
                )
                print(f"  ✓ Database updated")

            success_count += 1

        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed_count += 1
            continue

    conn.close()

    # Summary
    print(f"\n{'='*80}")
    print("TRANSCRIPTION COMPLETE")
    print(f"{'='*80}")
    print(f"Successful: {success_count}")
    print(f"Failed: {failed_count}")
    print(f"Output directory: {output_dir}")

    if update_db and success_count > 0:
        print(f"\n✓ Database updated with {success_count} new transcripts")
        print(f"\nVerify with:")
        print(f"  python list_missing_transcripts.py --db {db_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe missing podcast episodes using Whisper"
    )
    parser.add_argument("--db", required=True, help="Path to database file")
    parser.add_argument(
        "--episodes-root",
        default="/Users/amithash/Library/Mobile Documents/com~apple~CloudDocs/MentalModels/Insta post automation/Episodes",
        help="Root folder containing episode audio files"
    )
    parser.add_argument(
        "--output-dir",
        default="./generated_transcripts",
        help="Directory to save generated transcripts (default: ./generated_transcripts)"
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test mode: only process one episode"
    )
    parser.add_argument(
        "--episodes",
        nargs='+',
        type=int,
        help="Specific episode IDs to transcribe (e.g., --episodes 199 200 201)"
    )
    parser.add_argument(
        "--no-db-update",
        action="store_true",
        help="Don't update database (only generate DOCX files)"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (useful for running in background)"
    )

    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: Database not found: {args.db}")
        sys.exit(1)

    if not os.path.exists(args.episodes_root):
        print(f"ERROR: Episodes folder not found: {args.episodes_root}")
        sys.exit(1)

    transcribe_missing_episodes(
        args.db,
        args.episodes_root,
        args.output_dir,
        test_mode=args.test,
        specific_episodes=args.episodes,
        update_db=not args.no_db_update,
        skip_confirm=args.yes
    )


if __name__ == "__main__":
    main()
