#!/usr/bin/env python
"""Entry-point wrapper for the Mental Models DB tools.

Usage examples (run from the folder where this file lives):

    python mm.py --db mental_models.db init-db

    python mm.py --db mental_models.db import-models-from-excel \
        --excel "MentalModels_reorder.xlsx" --sheet "Sheet1"

    python mm.py --db mental_models.db import-rss \
        --rss-url "https://anchor.fm/s/f7f821ac/podcast/rss"

    python mm.py --db mental_models.db scan-transcripts \
        --episodes-root "../Episodes"

    python mm.py --db mental_models.db check-missing-models

    python mm.py --db mental_models.db repair-model-links

    python mm.py --db mental_models.db auto-link-models --dry-run
"""

from mmtool.cli import main

if __name__ == "__main__":
    main()
