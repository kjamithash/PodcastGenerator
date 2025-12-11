"""
Transcript scanning and model-name guessing utilities.

Responsible for:
- Reading .docx transcript files
- Splitting documents into episode-sized blocks
- Guessing the mental model name from each block
- Attaching transcripts to episodes in the DB
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3
import unicodedata

from .db import get_conn
from .names import canonicalize_name, build_mental_model_index

_DOCX_DOCUMENT = None


def _ensure_docx_document():
    """Load python-docx lazily so other commands don't require it."""
    global _DOCX_DOCUMENT
    if _DOCX_DOCUMENT is not None:
        return _DOCX_DOCUMENT

    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError(
            "The 'python-docx' package is required to scan transcripts. "
            "Install it with `pip install python-docx` and rerun the command."
        ) from exc

    _DOCX_DOCUMENT = Document
    return _DOCX_DOCUMENT


# ---------------------------------------------------------------------------
# Episode block splitting
# ---------------------------------------------------------------------------

EPISODE_START_PATTERN = re.compile(
    r"(?:(?<=\n)|^)"
    r"(?=(?:Welcome(?: back)? to Mental Models Daily|Host: Welcome to Mental Models Daily))",
    re.MULTILINE,
)


def extract_text_from_docx(path: str) -> str:
    """Extract plain text from a DOCX file, preserving paragraph boundaries."""
    Document = _ensure_docx_document()
    doc = Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def split_into_episode_blocks(text: str) -> list[str]:
    """
    Split a transcript DOCX text into episode-sized blocks.

    Heuristic:
    - Use repeated "Welcome to Mental Models Daily" / "Host: Welcome..." as markers.
    - If no markers are present, treat the entire doc as a single block.
    """
    if not text:
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("\n"):
        text = "\n" + text

    starts = [m.start() for m in EPISODE_START_PATTERN.finditer(text)]
    blocks: list[str] = []

    if not starts:
        blk = text.strip()
        return [blk] if blk else []

    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        blk = text[start:end].strip()
        if blk:
            blocks.append(blk)

    return blocks


# ---------------------------------------------------------------------------
# Guessing the model name from transcript text
# ---------------------------------------------------------------------------

INTRO_PATTERNS = [
    # "Today, we're examining X"
    r"Today,\s+we(?:'| a)re\s+(?:diving into|examining|exploring|discussing|"
    r"delving into|focusing on|unraveling|looking at)\s+(?P<name>.+?)(?:[\.!\n]|$)",

    # "Today we're diving into the concept of X"
    r"Today\s+we(?:'| a)re\s+(?:diving into|examining|exploring|discussing|"
    r"delving into|focusing on|unraveling|looking at)\s+(?:the\s+concept\s+of\s+)?"
    r"(?P<name>.+?)(?:[\.!\n]|$)",

    # "Today, we're diving into a powerful tool for ...: Error Bars"
    r"Today.*?:\s*(?P<name>[A-Z][^\.!\n]+)",

    # "we’re diving into the concept of X." (without 'Today')
    r"we(?:'| a)re\s+diving into\s+(?:the\s+concept\s+of\s+)?"
    r"(?P<name>.+?)(?:[\.!\n]|$)",
]


def _clean_raw_name(raw: str) -> str:
    """Small helper to trim punctuation around a captured name."""
    return raw.strip(" .:\"'“”‘’")


def guess_model_name_from_text(text: str) -> str | None:
    """
    Heuristic extraction of the mental model name from a transcript block.

    This is intentionally regex-based and *does not* touch the DB.
    Higher-level code will run `canonicalize_name()` on the result and
    then look it up in the mental_models index.

    We try, in order:
    1) Your common "Today we're diving into ..." style intros (INTRO_PATTERNS).
    2) A Markdown-style heading / emphasised name on the first line, e.g. "**Utilitarianism**".
    3) A capitalised phrase before "is/are/teaches/highlights/explains", excluding junk like "This concept".
    4) A quoted capitalised phrase, e.g. `"Error Bars"`.
    5) A "the X" pattern near the beginning, excluding "Mental Models Daily", "Host", etc.
    """
    if not text:
        return None

    snippet = unicodedata.normalize("NFKD", text[:2000])

    # 1) Explicit intro patterns
    for pat in INTRO_PATTERNS:
        m = re.search(pat, snippet, flags=re.IGNORECASE | re.DOTALL)
        if m:
            name = _clean_raw_name(m.group("name"))
            if len(name) > 140:
                # Often the actual name is before a comma or "which/that"
                name = re.split(r"(,|\bwhich\b|\bthat\b)", name)[0].strip()
            return name or None

    # 2) First line heading / emphasised word
    first_line = snippet.splitlines()[0] if snippet.splitlines() else snippet
    m = re.search(
        r"^\s*(\*\*|__)?(?P<name>[A-Z][A-Za-z0-9' \-/&]{3,80})(\*\*|__)?\s*$",
        first_line,
    )
    if m:
        return _clean_raw_name(m.group("name"))

    # 3) "X is/are/teaches/highlights/explains ..."
    m = re.search(
        r"\b(?P<name>[A-Z][A-Za-z0-9' \-/&]{3,80})\s+"
        r"(?:is|are|teaches|highlights|explains)\b",
        snippet,
    )
    if m:
        candidate = _clean_raw_name(m.group("name"))
        # Avoid junk like "This concept", "This principle"
        bad_prefixes = (
            "this concept",
            "this principle",
            "this model",
            "this idea",
            "this bias",
        )
        if not any(candidate.lower().startswith(bp) for bp in bad_prefixes):
            return candidate

    # 4) Quoted capitalised phrase
    m = re.search(
        r"[\"“‘'](?P<q>[A-Z][A-Za-z0-9' \-/&]{2,80})[\"”’']",
        snippet,
    )
    if m:
        return _clean_raw_name(m.group("q"))

    # 5) "the X" near the start (for things like "the Filter Bubble")
    m = re.search(
        r"\bthe\s+(?P<name>[A-Z][A-Za-z0-9' \-/&]{3,80})",
        snippet,
    )
    if m:
        candidate = _clean_raw_name(m.group("name"))
        # Filter out obviously non-model phrases
        if not re.match(
            r"^(mental models daily|host)\b",
            candidate,
            flags=re.IGNORECASE,
        ):
            return candidate

    return None


# ---------------------------------------------------------------------------
# Scanning DOCX transcripts and attaching them to the DB
# ---------------------------------------------------------------------------


def scan_transcripts(db_path: str, episodes_root: str) -> None:
    """
    Walk the episodes_root folder, read *.docx transcripts, and attach them
    to episodes.

    For each detected episode block:
      - Guess the mental model name from the text
      - Map to mental_models (via canonicalise + index)
      - Find/create an episodes row and store transcript + source info

    NOTE: This will happily create "episode" rows for content that isn't yet
    published in the RSS feed (e.g. drafts, social captions). That is why
    you see hundreds of rows in `episodes` – it's by design: the table is
    acting as a generic "content episode" store, not just "RSS-published
    episodes".
    """
    try:
        _ensure_docx_document()
    except ImportError as exc:
        print(f"ERROR: {exc}")
        return

    conn = get_conn(db_path)
    cur = conn.cursor()

    model_index = build_mental_model_index(conn, debug=False)

    cur.execute("SELECT id, mental_model_id, title FROM episodes")
    existing_by_model: dict[int, dict] = {}
    existing_by_title: dict[str, dict] = {}

    def cache_episode(row: dict) -> None:
        rid = row["id"]
        mid = row["mental_model_id"]
        title = row["title"] or ""
        if mid:
            existing_by_model.setdefault(mid, row)
        canon = canonicalize_name(title)
        if canon:
            existing_by_title.setdefault(canon, row)

    for row in cur.fetchall():
        cache_episode({"id": row["id"], "mental_model_id": row["mental_model_id"], "title": row["title"]})

    transcripts_found = 0
    episodes_updated = 0
    episodes_inserted = 0

    print("=== SCAN TRANSCRIPTS ===")
    print(f"Root folder: {episodes_root}\n")

    for root, _, files in os.walk(episodes_root):
        for fname in files:
            if not fname.lower().endswith(".docx"):
                continue

            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, episodes_root)
            print(f"Processing DOCX: {rel_path}")

            try:
                text = extract_text_from_docx(full_path)
            except Exception as e:  # pragma: no cover – defensive
                print(f"  ! Error reading {rel_path}: {e}")
                continue

            blocks = split_into_episode_blocks(text)
            if not blocks:
                print("  ! No episode blocks detected")
                continue

            print(f"  Detected {len(blocks)} episode block(s) in file")

            for idx, block in enumerate(blocks, start=1):
                transcripts_found += 1

                guessed = guess_model_name_from_text(block)
                canon_guess = canonicalize_name(guessed) if guessed else ""
                mm = model_index.get(canon_guess) if canon_guess else None

                mental_model_id = mm["id"] if mm else None
                mm_name = mm["name"] if mm else None

                # If we know the mental model, try to find an existing episode row
                episode_row = None
                if mental_model_id is not None:
                    cached = existing_by_model.get(mental_model_id)
                    if cached:
                        cur.execute("SELECT * FROM episodes WHERE id = ?", (cached["id"],))
                        episode_row = cur.fetchone()
                if episode_row is None and canon_guess:
                    cached = existing_by_title.get(canon_guess)
                    if cached:
                        cur.execute("SELECT * FROM episodes WHERE id = ?", (cached["id"],))
                        episode_row = cur.fetchone()

                now = dt.datetime.utcnow().isoformat(timespec="seconds")

                if episode_row:
                    # Update transcript in existing episode
                    cur.execute(
                        """
                        UPDATE episodes
                           SET transcript        = ?,
                               transcript_source = ?,
                               transcript_index  = ?,
                               updated_at        = ?
                         WHERE id = ?
                        """,
                        (block, rel_path, idx, now, episode_row["id"]),
                    )
                    episodes_updated += 1
                    print(
                        f"    Updated existing episode #{episode_row['id']} "
                        f"({mm_name}) [block {idx}]"
                    )
                else:
                    # Create new episode row.
                    # Title preference: canonical mental model name if known,
                    # otherwise the raw guessed name, otherwise a fallback.
                    title = mm_name or guessed or f"Episode from {os.path.basename(full_path)}"

                    cur.execute(
                        """
                        INSERT INTO episodes
                            (mental_model_id, title, description,
                             transcript, transcript_source, transcript_index,
                             created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            mental_model_id,
                            title,
                            None,
                            block,
                            rel_path,
                            idx,
                            now,
                            now,
                        ),
                    )
                    episodes_inserted += 1
                    new_id = cur.lastrowid
                    cache_episode({"id": new_id, "mental_model_id": mental_model_id, "title": title})
                    print(
                        f"    Inserted new episode (title={title!r}, block={idx}, "
                        f"guessed={guessed!r})"
                    )

            conn.commit()
            print()

    conn.close()

    print("=== SCAN SUMMARY ===")
    print(f"Transcript blocks found : {transcripts_found}")
    print(f"Episodes updated        : {episodes_updated}")
    print(f"Episodes inserted       : {episodes_inserted}")
    print("======================\n")
