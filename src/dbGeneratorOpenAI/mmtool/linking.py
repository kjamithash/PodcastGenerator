import re
import sqlite3
from .db import get_conn
from .names import canonicalize_name, build_mental_model_index
from .models import get_mental_model_name_column
from .transcripts import guess_model_name_from_text

def title_looks_bad(title: str) -> bool:
    if not title:
        return True
    t = str(title).strip()

    if t.lower().startswith("episode from "):
        return True
    if re.fullmatch(r"\d+(\.\ds?)?", t):
        return True
    if len(title) <= 4:
        return True
    return False

def auto_link_models_from_transcripts(db_path: str, dry_run: bool = False):
    conn = get_conn(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    model_name_col = get_mental_model_name_column(conn)
    print(f"[auto-link-models] Using DB column '{model_name_col}' as the mental model name")

    cur.execute(f"SELECT id, {model_name_col} AS name FROM mental_models")
    models = cur.fetchall()

    if not models:
        print("No models found in mental_models table. Did you run import-models-from-excel?")
        conn.close()
        return

    model_index = build_mental_model_index(conn)

    model_variants: list[dict] = []
    for row in models:
        mid = row["id"]
        raw_name = (row["name"] or "").strip()
        if not raw_name:
            continue

        base = raw_name.lower()
        variants = set()
        variants.add(base)

        if base.startswith("the "):
            variants.add(base[4:])

        if "(" in base:
            before_paren = base.split("(", 1)[0].strip()
            if before_paren:
                variants.add(before_paren)

        if " vs " in base:
            variants.add(base.replace(" vs ", " vs. "))
            variants.add(base.replace(" vs ", " versus "))
        if " vs. " in base:
            variants.add(base.replace(" vs. ", " vs "))
            variants.add(base.replace(" vs. ", " versus "))
        if " versus " in base:
            variants.add(base.replace(" versus ", " vs "))
            variants.add(base.replace(" versus ", " vs. "))

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
    examples: list[tuple[int, str, str, str]] = []

    for ep in episodes:
        ep_id = ep["id"]
        title = ep["title"] or ""
        transcript = ep["transcript"] or ""

        if not transcript.strip():
            continue

        if ep["mental_model_id"] is not None:
            already_linked += 1
            continue

        chosen: dict | None = None
        reason = ""

        guessed_name = guess_model_name_from_text(transcript)
        if guessed_name:
            canon_guess = canonicalize_name(guessed_name)
            mm = model_index.get(canon_guess)
            if mm:
                chosen = {"model_id": mm["id"], "model_name": mm["name"]}
                reason = "transcript_guess"

        if not chosen:
            canon_title = canonicalize_name(title)
            mm = model_index.get(canon_title)
            if mm:
                chosen = {"model_id": mm["id"], "model_name": mm["name"]}
                reason = "title_match"

        if not chosen:
            blob = (title + "\n" + transcript).lower()

            matches: list[dict] = []
            for mv in model_variants:
                if mv["variant"] in blob:
                    matches.append(mv)

            if not matches:
                no_match += 1
                continue

            by_model: dict[int, dict] = {}
            for m in matches:
                mid = m["model_id"]
                prev = by_model.get(mid)
                if prev is None or m["length"] > prev["length"]:
                    by_model[mid] = m

            if len(by_model) == 1:
                chosen = list(by_model.values())[0]
            else:
                sorted_models = sorted(by_model.values(), key=lambda x: x["length"], reverse=True)
                top = sorted_models[0]
                second = sorted_models[1]
                if top["length"] >= second["length"] + 5:
                    chosen = top
                else:
                    ambiguous += 1
                    continue
            reason = "substring_match"

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
                    reason,
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
        for ep_id, title, model_name, reason in examples:
            print(f"- Episode {ep_id}: {title!r}  -->  {model_name!r} ({reason})")
    print("=========================================\n")

def repair_model_links(db_path: str, debug: bool = False):
    """
    Attempt to repair missing or incorrect model links for episodes.
    
    Args:
        db_path: Path to the SQLite database
        debug: If True, print detailed debugging information
    """
    # Known mental model names for direct matching
    KNOWN_MODELS = {
        # Add known models here for direct matching
        "second order thinking", "inversion", "first principles", 
        "map is not the territory", "thought experiment", "occam's razor",
        "hanlon's razor", "hickam's dictum", "hindsight bias", "confirmation bias",
        # Add more models as needed
    }
    
    def extract_model_candidates(title: str, transcript: str) -> list[tuple[str, str]]:
        """Extract potential model names from title and transcript."""
        candidates: list[tuple[str, str]] = []

        # 1. Try to extract model names using common patterns
        patterns = [
            # Pattern 1: "X: Y, also known as Z" - extract Y
            r":\s*([^:.,]+?)(?:,|\.|$| also known as)",
            # Pattern 2: "X: Y" - extract Y
            r":\s*([^:.,]+?)(?:\.|$)",
            # Pattern 3: "X, also known as Y" - extract X
            r"([^,]+?)(?:\s*,?\s*also known as\s+[^,]+)",
            # Pattern 4: "X (Y)" - extract X
            r"([^(]+?)(?:\s*\([^)]+\))?$",
        ]

        for idx, pattern in enumerate(patterns, start=1):
            matches = re.finditer(pattern, title, re.IGNORECASE)
            for match in matches:
                model_name = match.group(1).strip()
                if model_name and len(model_name) > 3:  # Skip very short matches
                    canon_name = canonicalize_name(model_name)
                    if canon_name and canon_name not in [c[1] for c in candidates]:
                        candidates.append((f"pattern_{idx}", canon_name))

        # 2. Try to extract from transcript if available
        if transcript:
            # Look for "also known as" pattern in transcript
            aka_matches = re.finditer(r"also known as\s+([^,.;]+)", transcript, re.IGNORECASE)
            for match in aka_matches:
                model_name = match.group(1).strip()
                canon_name = canonicalize_name(model_name)
                if canon_name and canon_name not in [c[1] for c in candidates]:
                    candidates.append(("transcript_aka", canon_name))

        # 3. Try the entire title as a last resort
        canon_title = canonicalize_name(title)
        if canon_title and canon_title not in [c[1] for c in candidates]:
            candidates.append(("full_title", canon_title))

        # 4. Include known model names that appear verbatim
        lowered_title = title.lower()
        if transcript:
            lowered_text = transcript.lower()
        else:
            lowered_text = ""
        for known in KNOWN_MODELS:
            if known in lowered_title or known in lowered_text:
                canon_known = canonicalize_name(known)
                if canon_known and canon_known not in [c[1] for c in candidates]:
                    candidates.append(("known_models", canon_known))

        return candidates
    
    # Main function body starts here
    conn = get_conn(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if debug:
        print("Building mental model index...")
    model_index = build_mental_model_index(conn, debug=debug)

    # Find episodes that need model links (with or without transcripts)
    cur.execute(
        """
        SELECT id, title, transcript, mental_model_id
        FROM episodes
        WHERE (mental_model_id IS NULL OR mental_model_id = 0)
        ORDER BY id
        """
    )
    episodes = cur.fetchall()

    if debug:
        print(f"\nFound {len(episodes)} episodes needing model links")

    fixed = 0
    skipped = 0

    for row in episodes:
        eid = row["id"]
        title = row["title"] or ""
        transcript = row["transcript"] or ""
        has_transcript = bool(transcript and transcript.strip())

        if debug:
            print(f"\nProcessing episode {eid}: {title!r}")
            print(f"  Has transcript: {has_transcript}")

        # Extract candidates using the new function
        candidates = extract_model_candidates(title, transcript)

        if debug and candidates:
            print("  Candidates:")
            for i, (source, cand) in enumerate(candidates, 1):
                print(f"    {i}. {source}: {cand!r}")

        chosen_model = None
        chosen_source = None
        best_match = None
        best_score = 0

        # Try to find the best match using fuzzy matching
        for source, canon in candidates:
            for model_canon, model_data in model_index.items():
                # 1. Exact match
                if canon == model_canon:
                    chosen_model = model_data
                    chosen_source = f"{source}_exact"
                    best_score = 1.0
                    break
                
                # 2. Partial match (one contains the other)
                if canon in model_canon or model_canon in canon:
                    score = 0.8  # Base score for partial matches
                    # Increase score if the match is at word boundaries
                    if (f" {canon} " in f" {model_canon} " or 
                        f" {model_canon} " in f" {canon} "):
                        score = 0.9
                    if score > best_score:
                        best_score = score
                        best_match = (f"{source}_partial_{score:.2f}", model_data, score)
                
                # 3. Fuzzy match using word overlap
                canon_words = set(canon.split())
                model_words = set(model_canon.split())
                if canon_words and model_words:  # Ensure we don't divide by zero
                    # Calculate Jaccard similarity
                    intersection = len(canon_words & model_words)
                    union = len(canon_words | model_words)
                    jaccard = intersection / union if union > 0 else 0
                    
                    # Calculate simple word overlap
                    overlap = intersection / min(len(canon_words), len(model_words)) if min(len(canon_words), len(model_words)) > 0 else 0
                    
                    # Use the higher of the two scores
                    score = max(jaccard, overlap)
                    
                    # Adjust score based on source
                    if source.startswith('pattern_'):
                        score *= 1.1  # Slight boost for pattern matches
                    elif source == 'transcript_aka':
                        score *= 1.2  # Higher boost for "also known as" matches
                        
                    if score > 0.4 and score > best_score:  # Lower threshold
                        best_score = score
                        best_match = (f"{source}_fuzzy_{score:.2f}", model_data, score)
            
            if best_score >= 0.9:  # Early exit if we have a very good match
                if chosen_model is None and best_match:
                    chosen_source, chosen_model, _ = best_match
                break

        # If no exact match, use the best match if score is good enough
        if not chosen_model and best_match and best_score > 0.5:  # Lowered threshold from 0.7 to 0.5
            chosen_source, chosen_model, _ = best_match

        if not chosen_model:
            skipped += 1
            if debug:
                print("  No matching model found")
                if candidates:
                    print("  Tried the following candidates:")
                    for i, (source, cand) in enumerate(candidates, 1):
                        print(f"    {i}. {source}: {cand!r} (not found in model index)")
            continue

        # Apply the model link
        mm_id = chosen_model["id"]
        mm_name = chosen_model["name"]

        try:
            updates = []
            params = []

            updates.append("mental_model_id = ?")
            params.append(chosen_model["id"])

            # Only update title if it looks bad or is empty
            if title_looks_bad(title) or not title.strip():
                updates.append("title = ?")
                params.append(chosen_model["name"])

            params.append(eid)

            sql = f"UPDATE episodes SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?"
            cur.execute(sql, params)
            conn.commit()
            fixed += 1

            if debug:
                print(f"  Linked to: {chosen_model['name']!r} (ID: {chosen_model['id']}, source: {chosen_source}, score: {best_score:.2f})")
                if "title = ?" in updates:
                    print(f"  Updated title to: {chosen_model['name']!r}")
        except Exception as e:
            if debug:
                print(f"  Error updating episode {eid}: {str(e)}")
            conn.rollback()
            skipped += 1

    # Print summary
    print("\n===== REPAIR SUMMARY =====")
    print(f"Episodes examined : {len(episodes)}")
    print(f"Episodes fixed    : {fixed}")
    print(f"Episodes skipped  : {skipped}")
    
    if debug and fixed > 0:
        print("\nSample of fixed episodes:")
        cur.execute("""
            SELECT e.id, e.title, m.name as model_name
            FROM episodes e
            JOIN mental_models m ON e.mental_model_id = m.id
            WHERE e.updated_at >= datetime('now', '-1 minute')
            ORDER BY e.id DESC
            LIMIT 5
        """)
        for row in cur.fetchall():
            print(f"- Episode {row['id']}: {row['title']!r} → {row['model_name']!r}")
    
    print("==========================")
    conn.close()
