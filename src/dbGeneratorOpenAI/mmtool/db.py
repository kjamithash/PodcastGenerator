import sqlite3
import datetime as dt

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
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row["name"] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        conn.commit()

def ensure_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

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

    ensure_column(conn, "episodes", "rss_guid", "TEXT")
    ensure_column(conn, "episodes", "rss_link", "TEXT")
    ensure_column(conn, "episodes", "rss_pubdate", "TEXT")
    ensure_column(conn, "episodes", "transcript", "TEXT")
    ensure_column(conn, "episodes", "transcript_source", "TEXT")
    ensure_column(conn, "episodes", "transcript_index", "INTEGER")
    ensure_column(conn, "episodes", "created_at", "TEXT")
    ensure_column(conn, "episodes", "updated_at", "TEXT")

    conn.commit()

def utc_now_iso() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds")
