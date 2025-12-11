import re
from .db import get_conn
from .transcripts import guess_model_name_from_text

def check_missing_models(db_path: str, debug: bool = False):
    conn = get_conn(db_path)
    cur = conn.cursor()

    if debug:
        print("Debug mode: Checking for missing models...")

    cur.execute(
        """
        SELECT COUNT(*) AS c
          FROM episodes
         WHERE transcript IS NOT NULL
           AND TRIM(transcript) != ''
        """
    )
    episodes_with_transcripts = cur.fetchone()["c"]

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
        if debug:
            print(f"SNIPPET      : {snippet} ...")
        print("-" * 80)

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
