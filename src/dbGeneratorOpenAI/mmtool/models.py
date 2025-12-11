# models.py
import json
import os
import sqlite3
import datetime as dt
from .db import get_conn
from . import utils
from .db_utils import get_mental_model_name_column


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
        col_name = c[1]
        col_type = (c[2] or "").upper()
        is_pk = bool(c[5])
        if not is_pk and ("CHAR" in col_type or "TEXT" in col_type or col_type == ""):
            return col_name

    if len(cols) >= 2:
        return cols[1][1]

    raise RuntimeError("Could not determine model name column for mental_models table.")

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
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "The 'pandas' package is required for import-models-from-excel. "
            "Install it with `pip install pandas` or add it to your environment."
        ) from exc

    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")

    header_param = 0 if has_headers else None
    df = pd.read_excel(excel_path, sheet_name=sheet_name, header=header_param)

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

    model_excel_col = _pick_column_with_defaults(
        excel_col_keys,
        excel_col_lower,
        explicit_name=model_column,
        explicit_index=model_column_index,
        role="model",
        default_index=DEFAULT_MODEL_COL_INDEX,
    )

    if model_excel_col is None:
        # First try exact column name match for your specific case
        for i, col in enumerate(excel_col_display):
            if "Best Alternative to Negotiated Agreement" in col:
                model_excel_col = excel_col_keys[i]
                break

    # If not found, try the standard column names
    if model_excel_col is None:
        candidates = ["model", "name", "title", "mental model", "mental_model"]
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

    model_name_col = get_mental_model_name_column(conn)
    print(f"[import-models-from-excel] Using DB column '{model_name_col}' for mental model name")

    cur.execute("PRAGMA table_info(mental_models)")
    mm_cols = [r[1] for r in cur.fetchall()]
    lower_cols = [c.lower() for c in mm_cols]
    has_description_col = "description" in lower_cols
    has_category_col = "category" in lower_cols
    has_notes_col = "notes" in lower_cols
    has_metadata_col = "metadata" in lower_cols

    count_insert = 0
    count_update = 0

    for _, row in df.iterrows():
        raw_val = row[model_excel_col]
        if pd.isna(raw_val):
            continue
        model_name = str(raw_val).strip()
        if not model_name:
            continue

        desc_val = None
        if desc_excel_col is not None and not pd.isna(row[desc_excel_col]):
            desc_val = str(row[desc_excel_col]).strip()
        cat_val = None
        if category_excel_col is not None and not pd.isna(row[category_excel_col]):
            cat_val = str(row[category_excel_col]).strip()
        notes_val = None
        if notes_excel_col is not None and not pd.isna(row[notes_excel_col]):
            notes_val = str(row[notes_excel_col]).strip()

        metadata_obj = {}
        for col in df.columns:
            raw_cell = row[col]
            if pd.isna(raw_cell):
                metadata_obj[str(col)] = None
            else:
                val = raw_cell
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

        cur.execute(
            f"SELECT id FROM mental_models WHERE LOWER({model_name_col}) = LOWER(?)",
            (model_name,),
        )
        existing = cur.fetchone()

        if existing:
            sets = []
            params: list = []
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
            if has_metadata_col:
                sets.append("metadata = ?")
                params.append(metadata_json)

            params.append(existing["id"])
            sql = f"UPDATE mental_models SET {', '.join(sets)} WHERE id = ?"
            cur.execute(sql, params)
            count_update += 1
        else:
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
            if has_metadata_col:
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
