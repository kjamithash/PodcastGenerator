# db_utils.py
import sqlite3

def get_mental_model_name_column(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(mental_models)")
    cols = cur.fetchall()
    if not cols:
        raise RuntimeError("mental_models table not found in database.")

    preferred = ["name", "model", "model_name", "title", "label"]
    col_by_name = {c[1].lower(): c for c in cols}

    for wanted in preferred:
        if wanted.lower() in col_by_name:
            return col_by_name[wanted.lower()][1]

    for c in cols:
        col_name = c[1].lower()
        if "name" in col_name or "model" in col_name:
            return c[1]

    return "name"  # default fallback