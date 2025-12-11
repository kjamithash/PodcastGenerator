# Quick Start Guide

## First Time Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- openai-whisper (for AI transcription)
- python-docx (for reading/writing DOCX files)
- openpyxl (for reading Excel files)
- feedparser (for parsing RSS feeds)

### 2. Verify Required Files

Make sure you have:
- ✅ `MentalModels_reorder.xlsx` - Excel file with mental models
- ✅ Episodes folder with transcripts and audio files
- ✅ Internet connection (for RSS feed and Whisper model download)

## Rebuild Database

### Option 1: Complete Rebuild (with Whisper)

This will transcribe missing episodes from audio files (~3-5 hours):

```bash
python rebuild_database.py --yes
```

### Option 2: Quick Rebuild (DOCX only)

This skips Whisper transcription (~30 seconds):

```bash
python rebuild_database.py --skip-whisper --yes
```

## What Gets Created

After running the rebuild:

```
dbGeneratorOpenAI/
├── mental_models.db              # ✅ SQLite database (3.8 MB)
└── generated_transcripts/        # ✅ Whisper transcripts (if enabled)
    ├── Episode_Name_1.docx
    ├── Episode_Name_2.docx
    └── ...
```

## Verify Success

Check the database:

```bash
sqlite3 mental_models.db << 'SQL'
SELECT 'Mental Models' as metric, COUNT(*) as count FROM mental_models
UNION ALL
SELECT 'Episodes', COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL
UNION ALL
SELECT 'With Transcripts', COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL AND transcript IS NOT NULL;
SQL
```

Expected output:
```
Mental Models|364
Episodes|280
With Transcripts|280
```

## Common Issues

### Issue: "Excel file not found"
**Solution:** Make sure `MentalModels_reorder.xlsx` is in the same directory

### Issue: "Episodes folder not found"
**Solution:** Update the path with `--episodes-root /path/to/your/episodes`

### Issue: Whisper downloads slowly
**Solution:** First run downloads 1.4GB model. Be patient or use `--skip-whisper`

### Issue: Some transcripts missing
**Solution:**
1. Check if audio files exist in Episodes folder
2. Verify calendar week folders (CW01, CW02, etc.)
3. Run without `--skip-whisper` to enable Whisper transcription

## Next Steps

Once the database is built:

1. **Use the database:**
   - Query with SQLite tools
   - Import into your application
   - Generate reports

2. **Update incrementally:**
   - Use `mm_tool.py` for specific updates
   - No need to rebuild from scratch each time

3. **Backup your database:**
   ```bash
   cp mental_models.db mental_models.db.backup
   ```

## Getting Help

- Read the full [README.md](README.md)
- Check `rebuild_database.py --help`
- Review the database schema in README.md
