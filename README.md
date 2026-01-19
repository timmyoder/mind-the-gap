# Mind the Gap 🚇⚽🐺

**Analyzing the biggest relegation escapes in Premier League history**

Calculate and visualize points gaps from relegation across all PL seasons (1992-present). Built to answer: *Can Wolves survive a historic 15-point deficit in 2025/26?*

Live App: https://mind-the-gap-wolves.streamlit.app/

⚠️ Disclaimer: This whole thing was vibe coded. Don't judge me. 

## Project Motivation

The historical record for the biggest points gap overcome to survive Premier League relegation is **10 points** (West Ham United, 2006/07). 

Wolves currently sit ~15 points from safety. If they survive, it would be unprecedented.

## Features

- **Complete historical data**: All PL seasons from 1992/93 to present
- **Point-in-time queries**: View league table as it stood on any date
- **Gap tracking**: Calculate exact points deficit to safety throughout seasons
- **Survivor analysis**: Identify which teams escaped and from how deep
- **3D terrain visualization**: Coming soon - Streamlit app with interactive plots

## Quick Start

### 1. Environment Setup

```bash
# Activate conda environment
conda activate mind-the-gap

# Install dependencies
pip install -r requirements.txt
```

### 2. Download Historical Data

```bash
# Automated download from Football-Data.co.uk
python scripts/download_data.py
```

This downloads all available Premier League seasons (1993-2026) to `data/raw/`.

### 3. Build Database

```bash
# Run ETL pipeline to process raw data
python scripts/pipeline.py
```

This creates `data/mind_the_gap.db` with complete standings and gap calculations.

### 4. Validate Data

```bash
# Verify historical records are correct
python scripts/validate_data.py
```

Should confirm West Ham 10-point record and other key facts.

## Usage Examples

### Query the Database

```python
from src.data.db import EPLDatabase
from src.analysis.queries import get_max_gap_survived

with EPLDatabase() as db:

# Find the record
record = get_max_gap_survived(db.conn)
print(f"Biggest gap overcome: {record}")

db.close()
```

## Project Structure

```
mind-the-gap/
├── data/
│   ├── raw/              # CSVs from Football-Data.co.uk
│   └── mind_the_gap.db   # SQLite database (generated)
├── src/
│   ├── data/
│   │   ├── db.py         # SQLite schema and connection
│   │   ├── loaders.py    # CSV ingestion with format handling
│   │   └── transforms.py # ETL pipeline (matches → standings → gaps)
│   ├── analysis/
│   │   └── queries.py    # SQL query helpers
│   └── viz/              # Visualization (coming soon)
├── scripts/
│   ├── download_data.py  # Automated data download
│   ├── pipeline.py       # Main ETL orchestration
│   └── validate_data.py  # Data integrity checks
├── tests/
│   ├── test_transforms.py              # Unit tests
│   └── test_historical_validation.py   # Integration tests
├── scratch/              # Debugging scripts (not in git)
├── requirements.txt      # Dependencies
└── README.md
```

## Database Schema

### `raw_matches`
Original match results (one row per match)
- Columns: season, date, home_team, away_team, home_goals, away_goals, result

### `standings_snapshots`
Daily league tables throughout each season (forward-filled)
- **68,767 snapshots** covering 3,432 match days
- Enables queries like: "Show me the table on March 15, 2007"
- All 20 teams present on every date (fixed forward-fill bug)

### `relegation_gaps`
Gap calculations for **all teams** on **all dates**
- **68,337 records** (not just bottom 3)
- Positive gap = danger, Negative gap = safe, Zero = at safety line
- Includes `eventually_survived` flag (True/False/None)
- `games_in_hand_adjusted` field for fixture parity

## Key Findings

### Historical Record
✅ **10 points** - West Ham United (2006-07)
- Date: March 3, 2007
- Position: 20th place
- Finished: 15th (survived)

### The 11-Point Barrier
✅ **No team has ever survived an 11+ point gap**
- Verified across all 33 seasons
- Examples: Derby (25pts), Aston Villa (22pts), Sheffield United (21pts)

### Wolves 2025-26
⚠️ **14-point gap** - Would be 4 points deeper than any successful escape in history

## Development

### Running Tests
```bash
# All tests
pytest

# Specific test file
pytest tests/test_historical_validation.py -v

# With coverage
pytest --cov=src
```

### Code Quality
```bash
# Linting
ruff check .

# Formatting
ruff format .

# Type checking
mypy src/
```
```

### Run tests
```bash
pytest
```

### Code quality
```bash
ruff check .              # Lint
ruff format .             # Format
mypy src/                 # Type check
```

## Data Source

Historical match results from [Football-Data.co.uk](https://www.football-data.co.uk/englandm.php)
- Complete Premier League history (1992-present)
- Updated regularly during the season
- Free for non-commercial use

## Coming Soon

- [ ] Streamlit web app
- [ ] 3D terrain visualization (Plotly)
- [ ] Interactive season explorer
- [ ] Live 2025/26 season tracking
- [ ] Export reports and charts
- [ ] API for programmatic access

## Technical Notes

### Team Name Normalization
The pipeline normalizes common team name variations:
- "Man United" / "Manchester United" → "Manchester Utd"
- "Wolves" / "Wolverhampton Wanderers" → "Wolverhampton"
- "Leicester" → "Leicester City"

### Ranking Logic
Official Premier League tiebreakers:
1. Points
2. Goal Difference
3. Goals Scored
4. Alphabetical (if all else equal)

### Games in Hand
Two gap calculations provided:
- **Absolute**: Points gap as the table stands
- **Adjusted**: Accounting for fixture differences (assuming 3 pts/game)

Most historical records use the absolute gap.

## License

MIT - See LICENSE file

## Acknowledgments

- Data: [Football-Data.co.uk](https://www.football-data.co.uk/)
- Inspiration: Every team that's ever fought to survive
- Special motivation: C'mon Wolves! 🐺

---

**Up the Wolves!** ⚪🟡⚫
