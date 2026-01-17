# Scripts

Operational scripts for EPL Terrain data pipeline.

## Production Scripts

### `download_data.py`
Downloads historical Premier League match data from Football-Data.co.uk.

```bash
python scripts/download_data.py
```

**What it does:**
- Downloads CSV files for seasons 1993-94 through 2025-26
- Implements rate limiting (1 second between requests)
- Stores data in `data/raw/`
- Reports success/failure for each season

**When to run:**
- Initial setup
- When new season data becomes available
- If you suspect data files are corrupted

### `pipeline.py`
Main ETL pipeline that processes raw match data into the SQLite database.

```bash
python scripts/pipeline.py
```

**What it does:**
1. Loads raw CSV files from `data/raw/`
2. Normalizes team names across seasons
3. Transforms matches into long format
4. Calculates cumulative statistics
5. Creates daily standings snapshots (with forward-fill)
6. Calculates relegation gaps for all teams
7. Marks which teams survived vs. were relegated
8. Inserts all data into `data/epl_terrain.db`

**Output:**
- SQLite database at `data/epl_terrain.db`
- Summary statistics in console
- Current Wolves situation vs. historical record

**When to run:**
- After downloading new data
- When you modify transformation logic
- To rebuild database from scratch

### `validate_data.py`
Validates the database against known historical facts.

```bash
python scripts/validate_data.py
```

**What it does:**
- Verifies West Ham 10-point record exists
- Checks no team survived > 10 point gap
- Confirms 11+ point gaps always result in relegation
- Validates famous relegation battles (Derby, Villa, Sheffield)
- Checks data completeness (seasons, forward-fill integrity)

**Exit codes:**
- `0`: All checks passed
- `1`: One or more checks failed

**When to run:**
- After rebuilding database
- Before deploying to production
- When troubleshooting data issues
- As part of CI/CD pipeline

## Development Notes

**Debugging scripts** (check_*.py, verify_*.py, find_*.py) are kept in `scratch/` directory which is not tracked in git. These were used during development to investigate data issues but are not needed for production use.

**Integration tests** in `tests/test_historical_validation.py` duplicate much of the validation logic but integrate with pytest framework for automated testing.
