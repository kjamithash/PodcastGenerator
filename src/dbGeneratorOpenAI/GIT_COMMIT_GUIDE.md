# Git Commit Guide

## Files to Commit

These are the clean, production-ready files that should be committed to git:

### Core Scripts
```
✅ rebuild_database.py           # Main database rebuild script
✅ transcribe_missing_episodes.py # Whisper AI transcription
✅ mm_tool.py                     # Database management CLI
✅ mm.py                          # Helper script
```

### mmtool Package
```
✅ mmtool/                        # Core functionality
   ✅ __init__.py
   ✅ models.py                   # Mental models import
   ✅ rss_import.py               # RSS feed import
   ✅ transcripts.py              # Transcript matching
```

### Documentation
```
✅ README.md                      # Complete documentation
✅ QUICKSTART.md                  # Quick start guide
✅ GIT_COMMIT_GUIDE.md            # This file
```

### Configuration
```
✅ requirements.txt               # Python dependencies
✅ .gitignore                     # Git ignore rules
```

### Data Files (to commit)
```
✅ MentalModels_reorder.xlsx     # Mental models Excel source
```

## Files NOT to Commit (in .gitignore)

These are excluded via .gitignore:

### Generated Files
```
❌ mental_models.db               # Database (regenerated)
❌ mental_models.db.bak           # Backups
❌ generated_transcripts/         # Whisper output
```

### Temporary/Development Files
```
❌ clear_and_rescan.py            # Development script
❌ fix_database.py                # Development script
❌ fix_invalid_transcripts.py     # Development script
❌ match_by_calendar_week.py      # Development script
❌ match_by_episode_title.py      # Development script
❌ rescan_and_match_transcripts.py # Development script
❌ review_unmatched_blocks.py     # Development script
❌ list_missing_transcripts.py    # Development script
❌ scan_transcripts.py            # Old script
```

### Documentation (development notes)
```
❌ DATABASE_ANALYSIS.md           # Development notes
❌ FIXES_APPLIED.md               # Development notes
❌ FUZZY_MATCHING_RESULTS.md      # Development notes
❌ RESCAN_RESULTS.md              # Development notes
❌ TRANSCRIPT_ISSUE_ANALYSIS.md   # Development notes
❌ missing_transcripts.csv        # Development output
```

### System Files
```
❌ .DS_Store                      # macOS
❌ __pycache__/                   # Python cache
❌ ~$*.xlsx                       # Excel temp files
```

## Git Commands

### Initial Commit

```bash
cd /path/to/PodcastGenerator/src/dbGeneratorOpenAI

# Add core files
git add rebuild_database.py
git add transcribe_missing_episodes.py
git add mm_tool.py
git add mm.py

# Add mmtool package
git add mmtool/

# Add documentation
git add README.md
git add QUICKSTART.md
git add GIT_COMMIT_GUIDE.md

# Add configuration
git add requirements.txt
git add .gitignore

# Add data source
git add MentalModels_reorder.xlsx

# Commit
git commit -m "Add Mental Models database generator with Whisper AI transcription

Features:
- Automated database rebuild from Excel, RSS, and DOCX files
- Whisper AI transcription for missing episodes
- Fuzzy matching for transcript-to-episode matching
- Complete documentation and quick start guide
- 280/280 episodes with transcripts (100% complete)"
```

### Update After Changes

```bash
# Check what changed
git status

# Add updated files
git add rebuild_database.py  # (or whichever files changed)

# Commit with descriptive message
git commit -m "Fix: Update transcript matching logic"
```

## Verification Before Commit

Run these checks before committing:

### 1. Test rebuild script
```bash
python rebuild_database.py --help
```

### 2. Verify .gitignore is working
```bash
git status --ignored
# Should NOT show .db files, generated_transcripts/, etc.
```

### 3. Check for sensitive data
```bash
# Make sure no API keys, credentials, or personal data in code
grep -r "password\|api_key\|secret" *.py
```

### 4. Run a quick test
```bash
# Test with skip-whisper (fast)
rm -f test.db
python rebuild_database.py --db test.db --skip-whisper --yes
sqlite3 test.db "SELECT COUNT(*) FROM mental_models"
# Should show: 364
rm -f test.db
```

## What Someone Else Needs to Rebuild

After cloning your repo, they will need:

1. **Your committed files** (from git)
2. **Episodes folder** (not in git - too large)
   - Share separately or document the path
3. **Python environment:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Run rebuild:**
   ```bash
   python rebuild_database.py --yes
   ```

## Notes

- The database file (`mental_models.db`) should NOT be in git
- It's regenerated from source files (Excel + RSS + DOCX)
- This makes the repo smaller and ensures reproducibility
- Anyone can rebuild the exact same database from source

## Summary

**Commit these:** Clean production code + documentation + source data
**Don't commit:** Generated files + development scripts + temporary files

The goal is that anyone can clone the repo and run `rebuild_database.py` to regenerate everything.
