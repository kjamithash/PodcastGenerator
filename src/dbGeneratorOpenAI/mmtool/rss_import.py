from .db import get_conn, utc_now_iso
from .names import canonicalize_name, build_mental_model_index

def import_rss(db_path: str, rss_url: str):
    try:
        import feedparser
    except ImportError as exc:
        raise ImportError(
            "The 'feedparser' package is required to import RSS feeds. "
            "Install it with `pip install feedparser`."
        ) from exc

    conn = get_conn(db_path)
    cur = conn.cursor()
    model_index = build_mental_model_index(conn)

    print(f"Fetching RSS: {rss_url}")
    feed = feedparser.parse(rss_url)

    if feed.bozo:
        print("WARNING: RSS feed parse error:", feed.bozo_exception)

    inserted = 0
    updated = 0

    for entry in feed.entries:
        title = getattr(entry, "title", "").strip()
        guid = getattr(entry, "id", None) or getattr(entry, "guid", None)
        link = getattr(entry, "link", None)
        desc = getattr(entry, "summary", None) or getattr(entry, "description", None)

        pubdate_raw = getattr(entry, "published", None)
        if not pubdate_raw and hasattr(entry, "updated"):
            pubdate_raw = entry.updated
        pubdate = pubdate_raw

        canon_title = canonicalize_name(title)
        mm = model_index.get(canon_title)
        mental_model_id = mm["id"] if mm else None

        existing = None
        if guid:
            cur.execute("SELECT * FROM episodes WHERE rss_guid = ?", (guid,))
            existing = cur.fetchone()
        if not existing:
            cur.execute("SELECT * FROM episodes WHERE title = ?", (title,))
            existing = cur.fetchone()

        now = utc_now_iso()

        if existing:
            cur.execute(
                """
                UPDATE episodes
                   SET title       = COALESCE(?, title),
                       description = COALESCE(?, description),
                       rss_guid    = COALESCE(?, rss_guid),
                       rss_link    = COALESCE(?, rss_link),
                       rss_pubdate = COALESCE(?, rss_pubdate),
                       mental_model_id = COALESCE(?, mental_model_id),
                       updated_at  = ?
                 WHERE id = ?
                """,
                (
                    title or existing["title"],
                    desc or existing["description"],
                    guid or existing["rss_guid"],
                    link or existing["rss_link"],
                    pubdate or existing["rss_pubdate"],
                    mental_model_id,
                    now,
                    existing["id"],
                ),
            )
            updated += 1
        else:
            cur.execute(
                """
                INSERT INTO episodes
                    (title, description, rss_guid, rss_link,
                     rss_pubdate, mental_model_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (title, desc, guid, link, pubdate, mental_model_id, now, now),
            )
            inserted += 1

    conn.commit()
    conn.close()

    print("=== IMPORT RSS ===")
    print(f"RSS URL   : {rss_url}")
    print(f"Inserted  : {inserted}")
    print(f"Updated   : {updated}")
    print("===================\n")
