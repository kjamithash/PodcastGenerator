import argparse
from .db import get_conn
from .models import import_models_from_excel
from .rss_import import import_rss
from .transcripts import scan_transcripts
from .checks import check_missing_models
from .linking import repair_model_links, auto_link_models_from_transcripts

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
    scan_transcripts(args.db, args.episodes_root)

def cmd_check_missing_models(args):
    check_missing_models(args.db)

def cmd_repair_model_links(args):
    repair_model_links(args.db, debug=args.debug)

def cmd_auto_link_models(args):
    auto_link_models_from_transcripts(args.db, dry_run=args.dry_run)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mental Models Daily DB management tool"
    )
    parser.add_argument(
        "--db",
        required=True,
        help="Path to SQLite database file (will be created if not exists)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    p_init = subparsers.add_parser(
        "init-db", help="Create/verify DB schema (non-destructive)."
    )
    p_init.set_defaults(func=cmd_init_db)

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
        help="Excel column name/letter containing the model category/type.",
    )
    category_group.add_argument(
        "--category-column-index",
        type=int,
        help="1-based index for the category/type column.",
    )
    description_group = p_excel.add_mutually_exclusive_group()
    description_group.add_argument(
        "--description-column",
        help="Excel column name/letter for the brief description.",
    )
    description_group.add_argument(
        "--description-column-index",
        type=int,
        help="1-based index for the brief description column.",
    )
    notes_group = p_excel.add_mutually_exclusive_group()
    notes_group.add_argument(
        "--notes-column",
        help="Excel column name/letter for the detailed explanation / notes.",
    )
    notes_group.add_argument(
        "--notes-column-index",
        type=int,
        help="1-based index for the notes column.",
    )
    p_excel.add_argument(
        "--no-headers",
        action="store_true",
        help="Treat the first row as data (sheet has no header row).",
    )
    category_group = p_excel.add_mutually_exclusive_group()
    category_group.add_argument(
        "--category-column",
        help=(
            "Explicit Excel column name/letter for the category/type field "
            "when the sheet header isn't literally 'Category'."
        ),
    )
    category_group.add_argument(
        "--category-column-index",
        type=int,
        help="1-based index for the category/type column when headers are missing.",
    )
    p_excel.set_defaults(func=cmd_import_models_from_excel)

    p_rss = subparsers.add_parser(
        "import-rss", help="Import / update episodes from podcast RSS feed."
    )
    p_rss.add_argument("--rss-url", required=True, help="Podcast RSS feed URL.")
    p_rss.set_defaults(func=cmd_import_rss)

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

    p_check = subparsers.add_parser(
        "check-missing-models",
        help="Report episodes with missing model links or missing transcripts.",
    )
    p_check.set_defaults(func=cmd_check_missing_models)

    repair_parser = subparsers.add_parser(
        'repair-model-links',
        help='Repair missing or incorrect model links for episodes',
        description='Attempt to repair missing or incorrect model links using episode titles and transcripts.',
    )
    repair_parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output showing detailed matching information',
    )
    repair_parser.set_defaults(func=cmd_repair_model_links)

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

    return parser

def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
