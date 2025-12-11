"""
Name normalisation and lookup helpers for the Mental Models DB.

Shared by:
- RSS import (title → mental model)
- transcript scanner (guessed name → mental model)
- linking/repair utilities
"""

from __future__ import annotations
import re
import sqlite3
from typing import Dict, Any
from . import utils
from .db_utils import get_mental_model_name_column


def canonicalize_name(s: str) -> str:
    """
    Canonicalize a mental model name for consistent comparison.
    """
    if not s:
        return ""

    s = s.lower().strip()

    connector_replacements = {
        "/": " and ",
        "&": " and ",
        "+": " and ",
    }
    for old, new in connector_replacements.items():
        s = s.replace(old, new)

    # Remove generic “today, we're diving into…” lead-ins
    s = re.sub(
        r"^(today,?\s+we(?:'| a)re|today we(?:'| a)re)\s+"
        r"(?:diving into|examining|exploring|discussing|delving into|"
        r"focusing on|unraveling|looking at)\s+",
        "",
        s,
    )
    s = re.sub(
        r"^(we(?:'| a)re\s+diving into\s+)",
        "",
        s,
    )
    s = re.sub(
        r"^(imagine you(?:'| a)re|imagine you)\s+",
        "",
        s,
    )

    # Remove generic “a powerful concept / a fascinating principle / ...” lead-ins
    s = re.sub(
        r"^(a|an|the)\s+"
        r"(powerful|fascinating|fundamental|revolutionary|strategic|economic|"
        r"psychological|concept|principle|tool|idea|thought experiment|framework|"
        r"pattern|phenomenon|lens|force|paradox|bias|model)\b"
        r"[\s:–—-]*",
        "",
        s,
    )

    # If there's a colon, choose the shorter side around it
    if ":" in s:
        left, right = [p.strip() for p in s.split(":", 1)]
        left_len, right_len = len(left), len(right)
        if right and (right_len <= left_len or left_len > 40):
            s = right
        else:
            s = left

    # Clear quotes / bullets / emojis
    s = re.sub(r"['\"“”‘’•·#*]+", " ", s)

    # Allow letters, numbers, &, /, + and spaces. Hyphens become spaces.
    s = s.replace("-", " ")
    s = re.sub(r"[^a-z0-9&/+ ]+", " ", s)

    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()

    return s


def build_mental_model_index(conn: sqlite3.Connection, debug: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Build a mapping from canonicalised mental model name → {id, name}.

    Args:
        conn: SQLite connection
        debug: When True, prints each model and its canonical form
    """
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM mental_models")
    model_index = {}
    models = cur.fetchall()
    
    if debug:
        print("\n=== MODEL INDEX ===")
        for row in models:
            canon = canonicalize_name(row["name"])
            print(f"ID: {row['id']}, Name: {row['name']!r}, Canonical: {canon!r}")
    
    for row in models:
        canon = canonicalize_name(row["name"])
        if canon:
            model_index[canon] = {"id": row["id"], "name": row["name"], "canon_name": canon}
    return model_index
