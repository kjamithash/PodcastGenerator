# Mental Models Database Generator

This tool generates and maintains a SQLite database containing mental models, podcast episodes, and transcripts for the Mental Models Daily podcast.

## Database Schema

The database contains two main tables:

### `mental_models`
- `id` - Primary key
- `name` - Mental model name (unique)
- `category` - Category classification
- `description` - Detailed description

### `episodes`
- `id` - Primary key
- `mental_model_id` - Foreign key to mental_models
- `title` - Episode title
- `description` - Episode description
- `rss_guid` - Unique identifier from RSS feed
- `rss_link` - Episode URL
- `rss_pubdate` - Publication date
- `transcript` - Full episode transcript
- `transcript_source` - Source file path
- `transcript_index` - Index within multi-transcript files
- `created_at` - Record creation timestamp
- `updated_at` - Record update timestamp

## Quick Start

### Rebuild Database from Scratch

To completely rebuild the database:

```bash
python rebuild_database.py --yes
```

This will:
1. Create database schema
2. Import mental models from Excel
3. Import episodes from RSS feed
4. Match transcripts from DOCX files
5. Transcribe missing episodes using Whisper AI

### Rebuild Without Whisper Transcription

If you only want to use existing DOCX transcripts:

```bash
python rebuild_database.py --skip-whisper --yes
```

## Prerequisites

### Required Python Packages

```bash
pip install openai-whisper python-docx openpyxl feedparser
```

### Required Files

- `MentalModels_reorder.xlsx` - Excel file with mental models
- Episodes folder with DOCX transcripts and MP3 audio files
- RSS feed: https://anchor.fm/s/f7f821ac/podcast/rss

## Detailed Usage

### Command Line Options

```bash
python rebuild_database.py [OPTIONS]

Options:
  --db PATH            Database path (default: mental_models.db)
  --excel PATH         Excel file path (default: MentalModels_reorder.xlsx)
  --rss URL            RSS feed URL (default: Mental Models Daily feed)
  --episodes-root PATH Episodes folder path
  --skip-whisper       Skip Whisper transcription
  --yes                Skip confirmation prompts
```

### Examples

**Custom database location:**
```bash
python rebuild_database.py --db /path/to/database.db
```

**Custom episodes folder:**
```bash
python rebuild_database.py --episodes-root /path/to/episodes
```

**Run without prompts (useful for automation):**
```bash
python rebuild_database.py --yes
```

## Data Sources

### 1. Mental Models (Excel)

Mental models are imported from `MentalModels_reorder.xlsx` with columns:
- Mental Model Name
- Category
- Description

### 2. Episodes (RSS Feed)

Episodes are imported from the Mental Models Daily podcast RSS feed:
- URL: https://anchor.fm/s/f7f821ac/podcast/rss
- Contains: Title, Description, GUID, Link, Publication Date

### 3. Transcripts (DOCX Files)

Transcripts are sourced from two locations:

**a) Original DOCX files in Episodes folder:**
- Located in calendar week folders (CW01, CW02, etc.)
- Split by "Welcome to Mental Models Daily" markers
- Matched to episodes by mental model name

**b) Whisper-generated transcripts:**
- Generated from MP3 audio files
- Saved to `generated_transcripts/` folder
- Used when DOCX transcripts are unavailable

## File Structure

```
dbGeneratorOpenAI/
├── rebuild_database.py              # Main rebuild script
├── mental_models.db                 # SQLite database
├── MentalModels_reorder.xlsx        # Mental models Excel
├── generated_transcripts/           # Whisper-generated transcripts
├── mmtool/                          # Core database tools
│   ├── __init__.py
│   ├── models.py                    # Mental models import
│   ├── rss_import.py                # RSS feed import
│   └── transcripts.py               # Transcript matching
└── transcribe_missing_episodes.py   # Whisper transcription
```

## Transcript Matching Logic

The system uses multiple strategies to match transcripts to episodes:

1. **Exact canonical match** - Normalized names match exactly
2. **Partial match** - Beginning or end of names match
3. **Contains match** - One name contains the other
4. **Word-by-word match** - All words in one name appear in the other
5. **Levenshtein distance** - Fuzzy matching for spelling variations
6. **Episode title search** - Search for episode title in transcript text
7. **Calendar week matching** - Match by publication date to CW folder

## Whisper Transcription

The Whisper AI model is used to transcribe episodes when DOCX files are unavailable:

- **Model:** Whisper Medium (balance of speed and accuracy)
- **Language:** English
- **Format:** All transcripts start with "Welcome to Mental Models Daily..."
- **Output:** DOCX files saved to `generated_transcripts/`
- **Database:** Transcripts automatically saved to database
- **Time:** ~2-5 minutes per episode

### Audio File Preferences

When multiple audio files exist for an episode:
- Prefers raw TTS files (without `_audacity` suffix)
- Falls back to processed files (with intro/outro music)

## Validation

All transcripts are validated to ensure they:
- Start with "Welcome to Mental Models Daily..."
- Have reasonable length (>500 characters)
- Are properly formatted and readable

Invalid transcripts (Instagram captions, title lists, etc.) are automatically rejected.

## Database Statistics

After rebuilding, you can check statistics:

```bash
python mm_tool.py stats mental_models.db
```

Or query directly:

```sql
-- Total mental models
SELECT COUNT(*) FROM mental_models;

-- Total episodes
SELECT COUNT(*) FROM episodes WHERE rss_guid IS NOT NULL;

-- Episodes with transcripts
SELECT COUNT(*) FROM episodes
WHERE rss_guid IS NOT NULL AND transcript IS NOT NULL;

-- Transcript sources breakdown
SELECT transcript_source, COUNT(*)
FROM episodes
WHERE transcript IS NOT NULL
GROUP BY transcript_source LIKE 'generated/%';
```

## Troubleshooting

### Missing Transcripts

If episodes are missing transcripts after rebuild:

1. Check if audio files exist in the Episodes folder
2. Verify calendar week folders (CW##) are correctly named
3. Run with Whisper enabled (remove `--skip-whisper`)
4. Check `generated_transcripts/` folder for output

### Audio File Not Found

The script uses fuzzy matching to find audio files even with typos:
- "Athority" matches "Authority"
- "Favrotism" matches "Favoritism"
- "CLT" matches "Central Limit Theorem"
- "COIN" matches "Counter-Insurgency"

If still not found, check the CW folder for the episode's publication week.

### Whisper Model Download

On first run, Whisper downloads a 1.4GB model file. This may take 5-10 minutes depending on internet speed. The model is cached for future use.

## Performance

**Full rebuild time:**
- Mental models import: <1 second
- RSS episodes import: ~5 seconds
- DOCX transcript matching: ~10 seconds
- Whisper transcription: ~3-5 hours (for ~70 episodes)

**Incremental updates:**
Use `mm_tool.py` for specific operations instead of full rebuild.

## Maintenance

### Update RSS Episodes

```bash
python mm_tool.py refresh-rss mental_models.db
```

### Add New Transcripts

```bash
python mm_tool.py scan-transcripts mental_models.db /path/to/episodes
```

### Transcribe Specific Episodes

```bash
python transcribe_missing_episodes.py --db mental_models.db --episodes 38 120 234
```

## Version History

- **v1.0** - Initial database structure
- **v2.0** - Added fuzzy matching for transcripts
- **v3.0** - Integrated Whisper AI transcription
- **v4.0** - Complete rebuild script with validation

## License

Internal tool for Mental Models Daily podcast production.

## Support

For issues or questions, check:
1. This README
2. Script help: `python rebuild_database.py --help`
3. Database logs in `mental_models.db`
