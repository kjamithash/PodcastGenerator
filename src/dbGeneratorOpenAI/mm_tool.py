#!/usr/bin/env python
"""
Utility tool for managing the Mental Models Daily SQLite database.

Key ideas:
- Excel file  -> canonical list of mental models (mental_models table)
- RSS feed    -> list of published episodes (episodes table rows)
- Transcripts -> fill/attach transcript text to episodes where possible

Commands (examples):
    python mm_tool.py --db mental_models.db init-db

    python mm_tool.py --db mental_models.db import-models-from-excel \
        --excel /path/to/models.xlsx --sheet "Sheet1"

    python mm_tool.py --db mental_models.db import-rss \
        --rss-url "https://anchor.fm/s/f7f821ac/podcast/rss"

    python mm_tool.py --db mental_models.db scan-transcripts \
        --episodes-root "/Users/.../Episodes"

    python mm_tool.py --db mental_models.db check-missing-models

    python mm_tool.py --db mental_models.db repair-model-links
"""

import argparse
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import textwrap
import unicodedata

_PANDAS = None
def _ensure_pandas():
    global _PANDAS
    if _PANDAS is not None:
        return _PANDAS
    try:
        import pandas as pd  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "The 'pandas' package is required for import-models-from-excel. "
            "Install it with `pip install pandas` and rerun the command."
        ) from exc
    _PANDAS = pd
    return _PANDAS

from mmtool.checks import check_missing_models as check_missing_models_impl
from mmtool.rss_import import import_rss as import_rss_impl
from mmtool.transcripts import scan_transcripts as scan_transcripts_impl


# ---------------------------------------------------------------------------
# DB helpers / schema
# ---------------------------------------------------------------------------


def get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cur.fetchone() is not None


def ensure_column(
    conn: sqlite3.Connection, table: str, column: str, col_def: str
) -> None:
    """Add a column if it does not exist already."""
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row["name"] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        conn.commit()


def ensure_schema(conn: sqlite3.Connection) -> None:
    """
    Ensure schema exists and is compatible with what this tool expects.
    Non-destructive: only creates tables/columns if missing.
    """
    cur = conn.cursor()

    # mental_models: canonical list from Excel
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS mental_models (
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT,
            description TEXT,
            notes TEXT,
            metadata TEXT
        )
        """
    )
    ensure_column(conn, "mental_models", "category", "TEXT")
    ensure_column(conn, "mental_models", "description", "TEXT")
    ensure_column(conn, "mental_models", "notes", "TEXT")
    ensure_column(conn, "mental_models", "metadata", "TEXT")

    # episodes: podcast episodes
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS episodes (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            mental_model_id   INTEGER,
            title             TEXT,
            description       TEXT,
            rss_guid          TEXT UNIQUE,
            rss_link          TEXT,
            rss_pubdate       TEXT,
            transcript        TEXT,
            transcript_source TEXT,
            transcript_index  INTEGER,
            created_at        TEXT DEFAULT (datetime('now')),
            updated_at        TEXT,
            FOREIGN KEY (mental_model_id) REFERENCES mental_models(id)
        )
        """
    )

    # Ensure newer columns exist in older DBs
    ensure_column(conn, "episodes", "rss_guid", "TEXT")
    ensure_column(conn, "episodes", "rss_link", "TEXT")
    ensure_column(conn, "episodes", "rss_pubdate", "TEXT")
    ensure_column(conn, "episodes", "transcript", "TEXT")
    ensure_column(conn, "episodes", "transcript_source", "TEXT")
    ensure_column(conn, "episodes", "transcript_index", "INTEGER")
    ensure_column(conn, "episodes", "created_at", "TEXT")
    ensure_column(conn, "episodes", "updated_at", "TEXT")

    conn.commit()


def get_mental_model_name_column(conn: sqlite3.Connection) -> str:
    """
    Inspect the mental_models table and guess which column is the 'name' of the model.

    Preference order:
      1) Columns named (case-insensitive): name, model, model_name, title, label
      2) Otherwise: first TEXT column that is not the primary key.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(mental_models)")
    cols = cur.fetchall()
    if not cols:
        raise RuntimeError("mental_models table not found in database.")

    # Columns are: cid, name, type, notnull, dflt_value, pk
    preferred = ["name", "model", "model_name", "title", "label"]

    # Map names for quick lookup
    col_by_name = {c[1].lower(): c for c in cols}

    for wanted in preferred:
        if wanted.lower() in col_by_name:
            return col_by_name[wanted.lower()][1]

    # Fallback: first TEXT column that is not the PK
    for c in cols:
        col_name = c[1]
        col_type = (c[2] or "").upper()
        is_pk = bool(c[5])
        if not is_pk and "CHAR" in col_type or "TEXT" in col_type or col_type == "":
            # SQLite is loose with types; empty type is often TEXT-ish.
            return col_name

    # If still nothing, just use the second column (non-id) as last resort
    if len(cols) >= 2:
        return cols[1][1]

    raise RuntimeError("Could not determine model name column for mental_models table.")


# ---------------------------------------------------------------------------
# Name normalisation / matching
# ---------------------------------------------------------------------------


def canonicalize_name(name: str) -> str:
    """
    Turn a model/episode name into a canonical form for matching.

    - Lowercase
    - Remove accents
    - Strip quotes/emojis/punctuation except letters/numbers/&/spaces
    - Normalise 'versus' / 'vs.' / 'and' etc.
    - Drop taglines after ':' (we care about the core model name)
    """
    if not name:
        return ""

    # Only care about text before ':' (so taglines in RSS titles don't hurt)
    name = str(name).split(":", 1)[0]

    # Normalise unicode
    name = unicodedata.normalize("NFKD", name)

    # Lowercase
    name = name.lower()

    connector_replacements = {
        "/": " and ",
        "&": " and ",
        "+": " and ",
    }
    for old, new in connector_replacements.items():
        name = name.replace(old, new)

    # Normalise some words/phrases
    replacements = {
        " versus ": " vs ",
        " vs. ": " vs ",
        " vs ": " vs ",
        "–": " ",
        "—": " ",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
    for old, new in replacements.items():
        name = name.replace(old, new)

    # Remove most punctuation except letters/numbers/&/spaces
    name = re.sub(r"[^a-z0-9& ]+", " ", name)

    # Collapse whitespace
    name = re.sub(r"\s+", " ", name).strip()

    return name

def auto_link_models_from_transcripts(db_path: str, dry_run: bool = False, debug: bool = False):
    """
    Try to automatically link episodes to mental models by scanning the
    episode title + transcript text for known model names from the
    mental_models table.

    - Uses the Excel-imported mental_models list as the source of truth.
    - Only links episodes that currently have mental_model_id IS NULL.
    - Skips episodes where multiple different models appear strongly.
    """
    conn = get_conn(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1) Find which column in mental_models is the 'name' column
    model_name_col = get_mental_model_name_column(conn)
    print(f"[auto-link-models] Using DB column '{model_name_col}' as the mental model name")

    # 2) Load all mental models
    cur.execute(f"SELECT id, {model_name_col} AS name FROM mental_models")
    models = cur.fetchall()

    if not models:
        print("No models found in mental_models table. Did you run import-models-from-excel?")
        conn.close()
        return

    # Build variants for matching
    model_variants: list[dict] = []
    for row in models:
        mid = row["id"]
        raw_name = (row["name"] or "").strip()
        if not raw_name:
            continue

        base = raw_name.lower()
        variants = set()

        # Base name
        variants.add(base)

        # Strip leading 'the '
        if base.startswith("the "):
            variants.add(base[4:])

        # Strip parenthetical part: "Mutually Assured Destruction (MAD)" -> "mutually assured destruction"
        if "(" in base:
            before_paren = base.split("(", 1)[0].strip()
            if before_paren:
                variants.add(before_paren)

        # Handle common "vs" variations:
        if " vs " in base:
            variants.add(base.replace(" vs ", " vs. "))
            variants.add(base.replace(" vs ", " versus "))
        if " vs. " in base:
            variants.add(base.replace(" vs. ", " vs "))
            variants.add(base.replace(" vs. ", " versus "))
        if " versus " in base:
            variants.add(base.replace(" versus ", " vs "))
            variants.add(base.replace(" versus ", " vs. "))

        # Filter out very short variants to reduce noise
        for v in variants:
            v = v.strip()
            if len(v) >= 4:
                model_variants.append(
                    {
                        "model_id": mid,
                        "model_name": raw_name,
                        "variant": v,
                        "length": len(v),
                    }
                )

    if not model_variants:
        print("No usable model name variants built from mental_models table.")
        conn.close()
        return

    # 3) Fetch episodes that have transcripts
    cur.execute(
        """
        SELECT id, title, transcript, mental_model_id
          FROM episodes
      ORDER BY id
        """
    )
    episodes = cur.fetchall()

    linked = 0
    already_linked = 0
    no_match = 0
    ambiguous = 0
    examples: list[tuple[int, str, str]] = []

    for ep in episodes:
        ep_id = ep["id"]
        title = ep["title"] or ""
        transcript = ep["transcript"] or ""

        if not transcript.strip():
            # No transcript, nothing to match against
            continue

        if ep["mental_model_id"] is not None:
            already_linked += 1
            continue

        blob = (title + "\n" + transcript).lower()

        # Find all model variants that appear in this episode
        matches: list[dict] = []
        for mv in model_variants:
            if mv["variant"] in blob:
                matches.append(mv)

        if not matches:
            no_match += 1
            continue

        # Group matches by model_id and keep the longest variant per model
        by_model: dict[int, dict] = {}
        for m in matches:
            mid = m["model_id"]
            prev = by_model.get(mid)
            if prev is None or m["length"] > prev["length"]:
                by_model[mid] = m

        # If multiple different models hit, only pick if one is clearly dominant
        if len(by_model) == 1:
            chosen = list(by_model.values())[0]
        else:
            # Sort by variant length (longest wins)
            sorted_models = sorted(by_model.values(), key=lambda x: x["length"], reverse=True)
            top = sorted_models[0]
            second = sorted_models[1]

            # Heuristic: require the top match to be meaningfully longer
            # than the second best to auto-link. Otherwise mark as ambiguous.
            if top["length"] >= second["length"] + 5:
                chosen = top
            else:
                ambiguous += 1
                continue

        if not dry_run:
            cur.execute(
                "UPDATE episodes SET mental_model_id = ? WHERE id = ?",
                (chosen["model_id"], ep_id),
            )

        linked += 1
        if len(examples) < 15:
            examples.append(
                (
                    ep_id,
                    title,
                    chosen["model_name"],
                )
            )

    if not dry_run:
        conn.commit()
    conn.close()

    print("=== AUTO-LINK MODELS FROM TRANSCRIPTS ===")
    print(f"Total episodes scanned       : {len(episodes)}")
    print(f"Episodes already linked      : {already_linked}")
    print(f"Episodes newly linked        : {linked}")
    print(f"Episodes with no clear match : {no_match}")
    print(f"Episodes ambiguous (skipped) : {ambiguous}")
    if dry_run:
        print("NOTE: dry_run=True, no changes were written to the database.")
    print("-----------------------------------------")
    if examples:
        print("Sample links:")
        for ep_id, title, model_name in examples:
            print(f"- Episode {ep_id}: {title!r}  -->  {model_name!r}")
    print("=========================================\n")



def build_mental_model_index(conn: sqlite3.Connection, debug: bool = False) -> dict:
    """
    Returns mapping:
        canonical_name -> { 'id': int, 'name': str }
    from the mental_models table.
    
    Args:
        conn: Database connection
        debug: If True, print debug information
    """
    # Build index of canonical model names
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM mental_models")
    model_index = {}
    models = cur.fetchall()
    
    if debug:
        print("\n=== MODEL INDEX ===")
        print(f"Found {len(models)} mental models in database")
        for row in models:
            canon = canonicalize_name(row["name"])
            print(f"ID: {row['id']}, Name: {row['name']!r}, Canonical: {canon!r}")
    
    for row in models:
        canon = canonicalize_name(row["name"])
        if canon:
            model_index[canon] = {"id": row["id"], "name": row["name"], "canon_name": canon}
    
    if debug:
        print(f"Built index with {len(model_index)} canonical model names")
    
    return model_index


def title_looks_bad(title: str, debug: bool = False) -> bool:
    """
    Heuristic to decide if an episode title is junk and should be overwritten.

    Examples:
    - "1.3s"
    - "Episode from CW44_Transcript"
    - Very short or numeric-only titles
    """
    if not title or not title.strip():
        return True
    title = title.strip()
    if len(title) < 3 or title.isdigit() or title.lower() in ["new recording", "untitled"]:
        return True

    # Generic junk patterns
    if title.lower().startswith("episode from "):
        return True
    if re.fullmatch(r"\d+(\.\ds?)?", title):  # e.g. "1.3s", "1.0s"
        return True
    if len(title) <= 4:
        return True

    return False


# ---------------------------------------------------------------------------
# Guessing model name from transcript text
# ---------------------------------------------------------------------------

INTRO_PATTERNS = [
    # "Today, we're examining X"
    r"Today,\s+we(?:'| a)re\s+(?:diving into|examining|exploring|discussing|delving into|focusing on|unraveling|looking at)\s+(?P<name>.+?)(?:[\.!\n]|$)",
    # "Today we're diving into the concept of X"
    r"Today\s+we(?:'| a)re\s+(?:diving into|examining|exploring|discussing|delving into|focusing on|unraveling|looking at)\s+(?:the\s+concept\s+of\s+)?(?P<name>.+?)(?:[\.!\n]|$)",
    # "Today, we're diving into a powerful tool for ..: Error Bars"
    r"Today.*?:\s*(?P<name>[A-Z][^\.!\n]+)",
    # "we’re diving into the concept of X." (without 'Today')
    r"we(?:'| a)re\s+diving into\s+(?:the\s+concept\s+of\s+)?(?P<name>.+?)(?:[\.!\n]|$)",
]


def guess_model_name_from_text(text: str) -> str | None:
    """
    Heuristic extraction of the mental model name from a transcript block.
    Purely regex-based; no LLM calls.

    Returns the raw extracted phrase (not canonicalised) or None.
    """
    if not text:
        return None
    snippet = text[:2000]  # keep it manageable
    snippet = unicodedata.normalize("NFKD", snippet)

    for pat in INTRO_PATTERNS:
        m = re.search(pat, snippet, flags=re.IGNORECASE | re.DOTALL)
        if m:
            name = m.group("name").strip(" .:\"'“”‘’")
            # Some guesses are really whole sentences, trim if obviously too long
            if len(name) > 140:
                # Often the actual name is before a comma or "which"
                name = re.split(r"(,|\bwhich\b|\bthat\b)", name)[0].strip()
            return name or None

    # Fallback: look for first capitalised phrase before "is", "are", "teaches", etc.
    m = re.search(
        r"\b(?P<name>[A-Z][A-Za-z0-9' \-/&]{3,80})\s+(?:is|are|teaches|highlights|explains)\b",
        snippet,
    )
    if m:
        return m.group("name").strip(" .:\"'“”‘’")

    return None


# ---------------------------------------------------------------------------
# Excel import: mental_models
# ---------------------------------------------------------------------------


def _excel_column_label_to_index(label: str) -> int | None:
    clean = str(label or "").strip()
    if not clean:
        return None
    if clean.isdigit():
        idx = int(clean) - 1
        return idx if idx >= 0 else None
    if not clean.isalpha():
        return None
    clean = clean.upper()
    total = 0
    for ch in clean:
        total = total * 26 + (ord(ch) - ord("A") + 1)
    return total - 1


def _resolve_explicit_excel_column(
    excel_cols: list[str],
    excel_col_lower: dict[str, str],
    *,
    explicit_name: str | None,
    explicit_index: int | None,
    role: str,
) -> str | None:
    if explicit_name:
        normalized = str(explicit_name).strip()
        lower = normalized.lower()
        if lower in excel_col_lower:
            return excel_col_lower[lower]
        idx = _excel_column_label_to_index(normalized)
        if idx is not None:
            if 0 <= idx < len(excel_cols):
                return excel_cols[idx]
            raise ValueError(
                f"{role.title()} column reference '{explicit_name}' maps to index {idx}, "
                f"but the sheet only has {len(excel_cols)} columns."
            )
        raise ValueError(
            f"{role.title()} column '{explicit_name}' was not found in the sheet. "
            f"Available columns: {excel_cols}"
        )

    if explicit_index is not None:
        if explicit_index < 0 or explicit_index >= len(excel_cols):
            raise ValueError(
                f"{role.title()} column index {explicit_index + 1} is out of range. "
                f"The sheet only has {len(excel_cols)} columns."
            )
        return excel_cols[explicit_index]

    return None


def _pick_column_with_defaults(
    excel_cols: list[str],
    excel_col_lower: dict[str, str],
    *,
    explicit_name: str | None,
    explicit_index: int | None,
    role: str,
    default_index: int | None = None,
) -> str | None:
    col = _resolve_explicit_excel_column(
        excel_cols,
        excel_col_lower,
        explicit_name=explicit_name,
        explicit_index=explicit_index,
        role=role,
    )
    if col is None and default_index is not None and 0 <= default_index < len(excel_cols):
        return excel_cols[default_index]
    return col


def import_models_from_excel(
    db_path: str,
    excel_path: str,
    sheet_name: str | None = None,
    *,
    model_column: str | None = None,
    model_column_index: int | None = None,
    category_column: str | None = None,
    category_column_index: int | None = None,
    description_column: str | None = None,
    description_column_index: int | None = None,
    notes_column: str | None = None,
    notes_column_index: int | None = None,
    has_headers: bool = True,
):
    """
    Import / upsert mental models from an Excel sheet into the mental_models table.

    We auto-detect:
      - Which Excel column holds the model name (Model / Name / Title / etc.)
      - Which DB column holds the model name (name / model / model_name / etc.)
    """
    pd = _ensure_pandas()

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    header_param = 0 if has_headers else None
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_param)

    # 1) Determine which Excel column has the model name
    excel_col_keys = list(df.columns)
    excel_col_display = [str(c).strip() for c in excel_col_keys]
    excel_col_lower = {
        excel_col_display[i].lower(): excel_col_keys[i]
        for i in range(len(excel_col_keys))
    }

    DEFAULT_CATEGORY_COL_INDEX = 1
    DEFAULT_MODEL_COL_INDEX = 2
    DEFAULT_DESCRIPTION_COL_INDEX = 3
    DEFAULT_NOTES_COL_INDEX = 4

    candidates = ["model", "name", "title", "mental model", "mental_model"]
    model_excel_col = _pick_column_with_defaults(
        excel_col_keys,
        excel_col_lower,
        explicit_name=model_column,
        explicit_index=model_column_index,
        role="model",
        default_index=DEFAULT_MODEL_COL_INDEX,
    )
    if model_excel_col is None:
        for cand in candidates:
            if cand in excel_col_lower:
                model_excel_col = excel_col_lower[cand]
                break

    if model_excel_col is None:
        raise ValueError(
            "Could not find a model-name column in Excel. "
            f"Available columns: {excel_col_display}. "
            "Expected something like 'Model', 'Name', 'Title', 'Mental Model', or 'mental_model'."
        )

    # Optional: description / category columns (if present)
    desc_excel_col = _pick_column_with_defaults(
        excel_col_keys,
        excel_col_lower,
        explicit_name=description_column,
        explicit_index=description_column_index,
        role="description",
        default_index=DEFAULT_DESCRIPTION_COL_INDEX,
    )
    if desc_excel_col is None:
        for cand in ["description", "desc", "summary"]:
            if cand in excel_col_lower:
                desc_excel_col = excel_col_lower[cand]
                break

    category_excel_col = _pick_column_with_defaults(
        excel_col_keys,
        excel_col_lower,
        explicit_name=category_column,
        explicit_index=category_column_index,
        role="category",
        default_index=DEFAULT_CATEGORY_COL_INDEX,
    )
    if category_excel_col is None:
        for cand in ["category", "type", "bucket"]:
            if cand in excel_col_lower:
                category_excel_col = excel_col_lower[cand]
                break

    notes_excel_col = _pick_column_with_defaults(
        excel_col_keys,
        excel_col_lower,
        explicit_name=notes_column,
        explicit_index=notes_column_index,
        role="notes",
        default_index=DEFAULT_NOTES_COL_INDEX,
    )

    conn = get_conn(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 2) Figure out which DB column holds the model name
    model_name_col = get_mental_model_name_column(conn)
    print(f"[import-models-from-excel] Using DB column '{model_name_col}' for mental model name")

    # 3) Ensure basic columns exist (id + name + optional description/category)
    #    We won't modify schema here; we just upsert into whatever columns exist.
    cur.execute("PRAGMA table_info(mental_models)")
    mm_cols = [r[1] for r in cur.fetchall()]

    lower_cols = [c.lower() for c in mm_cols]
    has_description_col = "description" in lower_cols
    has_category_col = "category" in lower_cols
    has_notes_col = "notes" in lower_cols

    # 4) Insert / update
    count_insert = 0
    count_update = 0

    for _, row in df.iterrows():
        model_name = str(row[model_excel_col]).strip() if not pd.isna(row[model_excel_col]) else ""
        if not model_name:
            continue

        metadata_obj = {}
        for col in df.columns:
            raw_val = row[col]
            if pd.isna(raw_val):
                metadata_obj[str(col)] = None
            else:
                val = raw_val
                if hasattr(val, "to_pydatetime"):
                    val = val.to_pydatetime()
                elif hasattr(val, "item"):
                    try:
                        val = val.item()
                    except Exception:
                        pass
                if isinstance(val, (dt.datetime, dt.date)):
                    val = val.isoformat()
                metadata_obj[str(col)] = val
        metadata_json = json.dumps(metadata_obj, ensure_ascii=False)

        desc_val = None
        if desc_excel_col is not None and not pd.isna(row[desc_excel_col]):
            desc_val = str(row[desc_excel_col]).strip()

        cat_val = None
        if category_excel_col is not None and not pd.isna(row[category_excel_col]):
            cat_val = str(row[category_excel_col]).strip()

        notes_val = None
        if notes_excel_col is not None and not pd.isna(row[notes_excel_col]):
            notes_val = str(row[notes_excel_col]).strip()

        # Check if this model already exists (by name) in DB
        cur.execute(
            f"SELECT id FROM mental_models WHERE LOWER({model_name_col}) = LOWER(?)",
            (model_name,),
        )
        existing = cur.fetchone()

        if existing:
            # Update
            sets = []
            params: list = []

            # name column
            sets.append(f"{model_name_col} = ?")
            params.append(model_name)

            if has_description_col and desc_val is not None:
                sets.append("description = ?")
                params.append(desc_val)

            if has_category_col and cat_val is not None:
                sets.append("category = ?")
                params.append(cat_val)
            if has_notes_col and notes_val is not None:
                sets.append("notes = ?")
                params.append(notes_val)
            sets.append("metadata = ?")
            params.append(metadata_json)

            params.append(existing["id"])

            sql = f"UPDATE mental_models SET {', '.join(sets)} WHERE id = ?"
            cur.execute(sql, params)
            count_update += 1
        else:
            # Insert
            cols = [model_name_col]
            vals = [model_name]
            placeholders = ["?"]

            if has_description_col and desc_val is not None:
                cols.append("description")
                vals.append(desc_val)
                placeholders.append("?")

            if has_category_col and cat_val is not None:
                cols.append("category")
                vals.append(cat_val)
                placeholders.append("?")
            if has_notes_col and notes_val is not None:
                cols.append("notes")
                vals.append(notes_val)
                placeholders.append("?")
            cols.append("metadata")
            vals.append(metadata_json)
            placeholders.append("?")

            sql = f"INSERT INTO mental_models ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
            cur.execute(sql, vals)
            count_insert += 1

    conn.commit()
    conn.close()

    print("=== IMPORT MODELS FROM EXCEL ===")
    print(f"Excel file        : {excel_path}")
    print(f"Sheet             : {sheet_name}")
    print(f"Excel name column : {model_excel_col}")
    print(f"DB name column    : {model_name_col}")
    print(f"Models inserted   : {count_insert}")
    print(f"Models updated    : {count_update}")
    print("================================\n")



# ---------------------------------------------------------------------------
# RSS import: episodes metadata
# ---------------------------------------------------------------------------


def import_rss(db_path: str, rss_url: str):
    """Delegate to the canonical rss_import implementation."""
    import_rss_impl(db_path, rss_url)


# ---------------------------------------------------------------------------
# Repair: auto-link episodes to mental models (fix mental_model_id & titles)
# ---------------------------------------------------------------------------


def get_best_model_match(canon_title: str, model_index: dict, debug: bool = False) -> tuple[dict, str, float] | tuple[None, None, float]:
    """
    Find the best matching model for a canonicalized title.
    
    Returns:
        Tuple of (best_match_model, match_type, confidence) or (None, None, 0.0)
    """
    from difflib import SequenceMatcher
    
    best_match = None
    best_score = 0.0
    best_match_type = None
    
    for model_canon, model_data in model_index.items():
        # Exact match
        if canon_title == model_canon:
            return model_data, "exact", 1.0
            
        # Check if one is a substring of the other
        if canon_title in model_canon or model_canon in canon_title:
            # Calculate overlap ratio
            ratio = SequenceMatcher(None, canon_title, model_canon).ratio()
            if ratio > best_score:
                best_score = ratio
                best_match = model_data
                best_match_type = "substring"
    
    # If we have a good enough match, return it
    if best_match and best_score >= 0.7:  # 70% similarity threshold
        return best_match, best_match_type, best_score
        
    # Try fuzzy matching for similar titles
    for model_canon, model_data in model_index.items():
        ratio = SequenceMatcher(None, canon_title, model_canon).ratio()
        if ratio > best_score:
            best_score = ratio
            best_match = model_data
            best_match_type = "fuzzy"
    
    if best_match and best_score >= 0.8:  # 80% similarity threshold for fuzzy matches
        return best_match, best_match_type, best_score
        
    return None, None, 0.0

def repair_model_links(db_path: str, debug: bool = False):
    if debug:
        print("Starting repair_model_links with debug output")
    """
    For episodes that have a transcript but no mental_model_id, infer the correct
    mental model using:
      (1) canonicalised episode title
      (2) guessed model name from transcript text

    If we get a unique match in mental_models, fill in mental_model_id.
    If the episode title looks obviously wrong, also update it to the canonical
    mental model name from Excel.
    
    Args:
        db_path: Path to the SQLite database
        debug: If True, print detailed debugging information
    """
    conn = get_conn(db_path)
    cur = conn.cursor()

    model_index = build_mental_model_index(conn, debug=debug)

    cur.execute(
        """
        SELECT e.id, e.title, e.transcript, e.mental_model_id
        FROM episodes e
        WHERE (e.mental_model_id IS NULL OR e.mental_model_id = 0)
        ORDER BY e.id
        """
    )
    episodes = cur.fetchall()

    if debug:
        print(f"Found {len(episodes)} episodes needing model links")

    fixed = 0
    skipped = 0

    for row in episodes:
        eid = row["id"]
        title = row["title"] or ""
        transcript = row["transcript"] or ""

        if debug:
            print(f"\nProcessing episode {eid}: {title!r}")

        # Skip if no title to match against
        if not title.strip():
            if debug:
                print("  ✗ No title to match against")
            skipped += 1
            continue
            
        # Try to match by title
        canon_title = canonicalize_name(title)
        if debug:
            print(f"  Canonical title: {canon_title!r}")
            
        # Get the best matching model
        model, match_type, confidence = get_best_model_match(canon_title, model_index, debug)
        
        if model and confidence >= 0.7:  # 70% confidence threshold
            if debug:
                print(f"  ✓ Matched by {match_type} to: {model['name']!r} "
                      f"(ID: {model['id']}, confidence: {confidence:.1%})")
            
            # Update the episode with the matched model
            updates = ["mental_model_id = ?"]
            params = [model["id"]]
            
            # Update title if it looks bad or if we have a better canonical name
            if title_looks_bad(title, debug=debug) or match_type == "exact":
                updates.append("title = ?")
                params.append(model["name"])
            
            params.append(eid)
            
            sql = f"UPDATE episodes SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?"
            cur.execute(sql, params)
            conn.commit()
            fixed += 1
            continue
            
        # If we get here, no good match was found
        if debug:
            print(f"  ✗ No good match found (best confidence: {confidence:.1%})")
            
            # Show top 3 closest matches for debugging
            if confidence > 0.3:  # Only show if somewhat close
                print("  Closest matches:")
                from difflib import get_close_matches
                matches = get_close_matches(canon_title, model_index.keys(), n=3, cutoff=0.3)
                for match in matches:
                    model = model_index[match]
                    ratio = SequenceMatcher(None, canon_title, match).ratio()
                    print(f"    - {model['name']!r} (ID: {model['id']}, confidence: {ratio:.1%})")
        
        skipped += 1

        candidates: list[tuple[str, str]] = []

        # Candidate 1: from title
        canon_title = canonicalize_name(title)
        if canon_title:
            candidates.append(("title", canon_title))

        # Candidate 2: from guessed name
        guessed = guess_model_name_from_text(transcript)
        canon_guess = canonicalize_name(guessed) if guessed else ""
        if canon_guess and canon_guess != canon_title:
            candidates.append(("guess", canon_guess))

        chosen_model = None
        chosen_source = None

        for source, canon in candidates:
            if canon in model_index:
                chosen_model = model_index[canon]
                chosen_source = source
                break

        if not chosen_model:
            skipped += 1
            continue

        mm_id = chosen_model["id"]
        mm_name = chosen_model["name"]

        updates = []
        params = []

        updates.append("mental_model_id = ?")
        params.append(mm_id)

        if title_looks_bad(title):
            updates.append("title = ?")
            params.append(mm_name)

        params.append(eid)

        sql = f"UPDATE episodes SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?"
        cur.execute(sql, params)
        fixed += 1

        print(
            f"FIXED episode {eid}: source={chosen_source}, "
            f"old_title={title!r}, new_model={mm_name!r} (id={mm_id})"
        )

    conn.commit()
    conn.close()

    print("\n===== REPAIR SUMMARY =====")
    print(f"Episodes examined : {len(episodes)}")
    print(f"Episodes fixed    : {fixed}")
    print(f"Episodes skipped  : {skipped}")
    print("==========================\n")


# ---------------------------------------------------------------------------
# Check: missing models / missing transcripts
# ---------------------------------------------------------------------------


def check_missing_models(db_path: str):
    """
    Diagnostics:
      - episodes with transcripts but no model (mental_model_id IS NULL)
      - episodes with model but no transcript (planned / RSS-only / not imported)

    Also prints 'guessed name' for the first group.
    """
    conn = get_conn(db_path)
    cur = conn.cursor()

    # Count episodes with transcripts
    cur.execute(
        """
        SELECT COUNT(*) AS c
          FROM episodes
         WHERE transcript IS NOT NULL
           AND TRIM(transcript) != ''
        """
    )
    episodes_with_transcripts = cur.fetchone()["c"]

    # Episodes with transcript but no mental_model_id
    cur.execute(
        """
        SELECT id, title, transcript
          FROM episodes
         WHERE transcript IS NOT NULL
           AND TRIM(transcript) != ''
           AND (mental_model_id IS NULL OR mental_model_id = 0)
         ORDER BY id
        """
    )
    missing_model_rows = cur.fetchall()

    # Episodes with mental_model_id but no transcript
    cur.execute(
        """
        SELECT id, title
          FROM episodes
         WHERE (transcript IS NULL OR TRIM(transcript) = '')
           AND mental_model_id IS NOT NULL
         ORDER BY id
        """
    )
    no_transcript_rows = cur.fetchall()

    total_issues = len(missing_model_rows) + len(no_transcript_rows)

    print("\n================ DB CHECK: EPISODES WITH MISSING MODEL NAMES ================")
    print(f"Episodes with transcripts: {episodes_with_transcripts}")
    print(f"Total episodes with problems: {total_issues}\n")

    # 1) Episodes with transcripts but no detected model
    for row in missing_model_rows:
        eid = row["id"]
        title = row["title"]
        transcript = row["transcript"] or ""

        snippet = transcript.strip().replace("\n", " ")
        snippet = re.sub(r"\s+", " ", snippet)[:220]

        guessed = guess_model_name_from_text(transcript)

        print(f"EPISODE ID   : {eid}")
        print(f"TITLE        : {title}")
        print(f"ISSUE        : no_model_detected")
        if guessed:
            print(f"GUESSED NAME : {guessed}")
        print(f"SNIPPET      : {snippet} ...")
        print("-" * 80)

    # 2) Episodes with model but no transcript
    if no_transcript_rows:
        print(
            "\n=== EPISODES WITH NO TRANSCRIPT (RSS-ONLY / PLANNED / NOT YET IMPORTED) ====="
        )
        for row in no_transcript_rows:
            eid = row["id"]
            title = row["title"]
            print(f"EPISODE ID   : {eid}")
            print(f"TITLE        : {title}")
            print(f"ISSUE        : no_transcript")
            print("-" * 80)

    conn.close()


# ---------------------------------------------------------------------------
# CLI wiring
# ---------------------------------------------------------------------------


def cmd_init_db(args):
    conn = get_conn(args.db)
    conn.close()
    print(f"Initialised / verified DB schema at: {args.db}")


def cmd_import_models_from_excel(args):
    model_col_index = args.model_column_index - 1 if args.model_column_index is not None else None
    category_col_index = args.category_column_index - 1 if args.category_column_index is not None else None
    description_col_index = args.description_column_index - 1 if args.description_column_index is not None else None
    notes_col_index = args.notes_column_index - 1 if args.notes_column_index is not None else None
    import_models_from_excel(
        args.db,
        args.excel,
        args.sheet,
        model_column=args.model_column,
        model_column_index=model_col_index,
        category_column=args.category_column,
        category_column_index=category_col_index,
        description_column=args.description_column,
        description_column_index=description_col_index,
        notes_column=args.notes_column,
        notes_column_index=notes_col_index,
        has_headers=not args.no_headers,
    )


def cmd_import_rss(args):
    import_rss(args.db, args.rss_url)


def cmd_scan_transcripts(args):
    scan_transcripts_impl(args.db, args.episodes_root)


def cmd_check_missing_models(args):
    check_missing_models_impl(args.db, debug=getattr(args, 'debug', False))


def cmd_repair_model_links(args):
    """CLI handler for repair-model-links command"""
    repair_model_links(args.db, debug=args.debug)


def cmd_auto_link_models(args):
    """
    CLI wrapper for auto_link_models_from_transcripts.
    """
    auto_link_models_from_transcripts(args.db, dry_run=args.dry_run, debug=args.debug)



def main():
    parser = argparse.ArgumentParser(
        description="Mental Models Daily DB management tool"
    )
    parser.add_argument(
        "--db", required=True, help="Path to SQLite database file (will be created if not exists)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    p_init = subparsers.add_parser(
        "init-db", help="Create/verify DB schema (non-destructive)."
    )
    p_init.set_defaults(func=cmd_init_db)

    # import-models-from-excel
    p_excel = subparsers.add_parser(
        "import-models-from-excel",
        help="Import mental models list from Excel into mental_models table.",
    )
    p_excel.add_argument("--excel", required=True, help="Path to Excel workbook.")
    p_excel.add_argument(
        "--sheet",
        required=False,
        help="Sheet name (if omitted, first sheet is used).",
    )
    excel_col_group = p_excel.add_mutually_exclusive_group()
    excel_col_group.add_argument(
        "--model-column",
        help=(
            "Explicit Excel column name/letter that contains the mental model names "
            "(e.g. 'Model' or 'C'). Useful when the sheet lacks headers."
        ),
    )
    excel_col_group.add_argument(
        "--model-column-index",
        type=int,
        help=(
            "1-based column index for the mental model names when the sheet has no headers "
            "(e.g. 3 for the third column)."
        ),
    )
    category_group = p_excel.add_mutually_exclusive_group()
    category_group.add_argument(
        "--category-column",
        help=(
            "Excel column name/letter containing the category/type. "
            "Use when the sheet header isn't literally 'Category'."
        ),
    )
    category_group.add_argument(
        "--category-column-index",
        type=int,
        help="1-based column index to use for category/type when headers are missing.",
    )
    description_group = p_excel.add_mutually_exclusive_group()
    description_group.add_argument(
        "--description-column",
        help="Excel column name/letter containing the brief description.",
    )
    description_group.add_argument(
        "--description-column-index",
        type=int,
        help="1-based column index for the brief description.",
    )
    notes_group = p_excel.add_mutually_exclusive_group()
    notes_group.add_argument(
        "--notes-column",
        help="Excel column name/letter for the detailed explanation / notes.",
    )
    notes_group.add_argument(
        "--notes-column-index",
        type=int,
        help="1-based column index for the detailed explanation / notes.",
    )
    p_excel.add_argument(
        "--no-headers",
        action="store_true",
        help="Treat the first row as data (useful when the sheet has no header row).",
    )
    p_excel.set_defaults(func=cmd_import_models_from_excel)

    # import-rss
    p_rss = subparsers.add_parser(
        "import-rss", help="Import / update episodes from podcast RSS feed."
    )
    p_rss.add_argument("--rss-url", required=True, help="Podcast RSS feed URL.")
    p_rss.set_defaults(func=cmd_import_rss)

    # scan-transcripts
    p_scan = subparsers.add_parser(
        "scan-transcripts",
        help=(
            "Scan DOCX transcripts in a folder and attach them to episodes. "
            "Walks the folder recursively and processes all *.docx files."
        ),
    )
    p_scan.add_argument(
        "--episodes-root",
        required=True,
        help="Root folder containing CWxx transcript DOCX files.",
    )
    p_scan.set_defaults(func=cmd_scan_transcripts)

    # check-missing-models
    p_check = subparsers.add_parser(
        "check-missing-models",
        help="Report episodes with missing model links or missing transcripts.",
    )
    p_check.add_argument(
        '--debug',
        action='store_true',
        help='Show detailed debug output',
    )
    p_check.set_defaults(func=cmd_check_missing_models)

    # repair-model-links
    repair_parser = subparsers.add_parser(
        'repair-model-links',
        help='Repair missing or incorrect model links for episodes',
    )
    repair_parser.add_argument(
        '--debug',
        action='store_true',
        help='Show detailed debug output',
    )
    repair_parser.set_defaults(func=cmd_repair_model_links)

    # auto-link-models
    p_auto = subparsers.add_parser(
        "auto-link-models",
        help=(
            "Link episodes to mental models by scanning titles + transcripts "
            "for names from the mental_models table (imported from Excel)."
        ),
    )
    p_auto.set_defaults(func=cmd_auto_link_models)
    p_auto.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be linked without actually updating the database.",
    )
    p_auto.add_argument(
        "--debug",
        action="store_true",
        help="Show detailed debug output while linking.",
    )


    args = parser.parse_args()

    # Delegate to subcommand
    args.func(args)


if __name__ == "__main__":
    main()
