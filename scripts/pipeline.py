"""Main pipeline script to process EPL data from CSV to database."""

import logging
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.db import initialize_database
from src.data.loaders import load_all_seasons, normalize_team_names
from src.data.transforms import (
    matches_to_long_format,
    calculate_cumulative_stats,
    create_standings_snapshots,
    calculate_relegation_gaps,
    mark_survivors,
    insert_matches_to_db,
    insert_standings_to_db,
    insert_gaps_to_db
)
from src.analysis.queries import get_max_gap_survived

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_full_pipeline(data_dir: str = "data/raw", db_path: str = "data/epl_terrain.db"):
    """Execute complete data pipeline from CSV to populated database.
    
    Args:
        data_dir: Directory containing season CSV files
        db_path: Path to SQLite database
    """
    logger.info("="*80)
    logger.info("STARTING EPL TERRAIN DATA PIPELINE")
    logger.info("="*80)
    
    # Step 1: Initialize database
    logger.info("\n[1/7] Initializing database...")
    db = initialize_database(db_path)
    logger.info(f"✓ Database created at: {db.db_path}")
    
    # Step 2: Load all season CSVs
    logger.info("\n[2/7] Loading CSV data...")
    try:
        matches_df = load_all_seasons(data_dir)
        
        if matches_df.empty:
            raise ValueError("No data loaded from any CSV files!")
        
        # Validate season loading
        seasons_loaded = matches_df['Season'].nunique()
        total_matches = len(matches_df)
        
        logger.info(f"✓ Loaded {total_matches} total matches from {seasons_loaded} seasons")
        logger.info(f"  Date range: {matches_df['Date'].min().strftime('%Y-%m-%d')} to {matches_df['Date'].max().strftime('%Y-%m-%d')}")
        
        # Show per-season breakdown
        logger.info(f"\n  Season-by-season breakdown:")
        season_summary = matches_df.groupby('Season').size().sort_index()
        for season, count in season_summary.items():
            # Expected: ~380 matches per season (38 games * 20 teams / 2)
            if count < 100:
                logger.warning(f"    {season}: {count} matches (⚠️  unusually low)")
            elif count > 400:
                logger.warning(f"    {season}: {count} matches (⚠️  unusually high)")
            else:
                logger.info(f"    {season}: {count} matches ✓")
        
        # Check for missing seasons
        csv_files = list(Path(data_dir).glob("*.csv"))
        expected_seasons = len(csv_files)
        if seasons_loaded < expected_seasons:
            logger.warning(f"\n⚠️  Only loaded {seasons_loaded}/{expected_seasons} CSV files")
            logger.warning("   Some seasons may have failed to load (check logs above)")
            
    except FileNotFoundError as e:
        logger.error(f"✗ Failed to load data: {e}")
        logger.info("\nDownload CSV files from:")
        logger.info("https://www.football-data.co.uk/englandm.php")
        logger.info(f"Save them to: {Path(data_dir).absolute()}")
        db.close()
        return
    except ValueError as e:
        logger.error(f"✗ Data validation failed: {e}")
        db.close()
        return
    
    # Step 3: Normalize team names
    logger.info("\n[3/7] Normalizing team names...")
    matches_df = normalize_team_names(matches_df)
    logger.info(f"✓ Normalized team names across {matches_df['HomeTeam'].nunique()} unique teams")
    
    # Step 4: Transform to long format and calculate cumulative stats
    logger.info("\n[4/7] Transforming to long format and calculating cumulative stats...")
    long_df = matches_to_long_format(matches_df)
    logger.info(f"✓ Created {len(long_df)} team-match records")
    
    cumulative_df = calculate_cumulative_stats(long_df)
    logger.info(f"✓ Calculated cumulative statistics")
    
    # Step 5: Create standings snapshots
    logger.info("\n[5/7] Creating standings snapshots...")
    standings_df = create_standings_snapshots(cumulative_df)
    logger.info(f"✓ Created {len(standings_df)} standings snapshots")
    logger.info(f"  Covering {standings_df.groupby('Season')['Date'].nunique().sum()} match days")
    
    # Step 6: Calculate relegation gaps
    logger.info("\n[6/7] Calculating relegation gaps...")
    gaps_df = calculate_relegation_gaps(standings_df)
    logger.info(f"✓ Calculated {len(gaps_df)} total gap records (all teams)")
    
    # Mark survivors
    gaps_df = mark_survivors(gaps_df, standings_df)
    
    # Count teams in actual danger (gap > 0)
    danger_teams = gaps_df[gaps_df['gap_to_17th'] > 0]
    survivors = danger_teams[danger_teams['eventually_survived'] == True]['team'].nunique()
    relegated = danger_teams[danger_teams['eventually_survived'] == False]['team'].nunique()
    logger.info(f"✓ Identified {survivors} survivors and {relegated} relegated teams from relegation zone")
    
    # Step 7: Insert into database
    logger.info("\n[7/7] Inserting data into database...")
    
    # Clear existing data
    cursor = db.conn.cursor()
    cursor.execute("DELETE FROM raw_matches")
    cursor.execute("DELETE FROM standings_snapshots")
    cursor.execute("DELETE FROM relegation_gaps")
    db.conn.commit()
    
    # Insert new data
    match_count = insert_matches_to_db(matches_df, db.conn)
    logger.info(f"✓ Inserted {match_count} matches")
    
    standings_count = insert_standings_to_db(standings_df, db.conn)
    logger.info(f"✓ Inserted {standings_count} standings snapshots")
    
    gaps_count = insert_gaps_to_db(gaps_df, db.conn)
    logger.info(f"✓ Inserted {gaps_count} relegation gap records")
    
    # Final summary
    logger.info("\n" + "="*80)
    logger.info("PIPELINE COMPLETE - ANALYZING RESULTS")
    logger.info("="*80)
    
    # Find the record
    max_gap = get_max_gap_survived(db.conn)
    
    if max_gap:
        season, date, team, position, gap, adjusted = max_gap
        logger.info(f"\n🏆 BIGGEST RELEGATION GAP EVER OVERCOME:")
        logger.info(f"   Team: {team}")
        logger.info(f"   Season: {season}")
        logger.info(f"   Date: {date}")
        logger.info(f"   Position: {position}")
        logger.info(f"   Gap to safety: {gap} points")
        logger.info(f"   Adjusted (games in hand): {adjusted} points")
        logger.info(f"\n   {team} were {gap} points from safety on {date}")
        logger.info(f"   but managed to survive relegation by season's end!")
    
    # Show Wolves comparison (if current season data exists)
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT date, gap_to_17th, position 
        FROM relegation_gaps 
        WHERE team = 'Wolverhampton' AND season = '2025-26'
        ORDER BY date DESC 
        LIMIT 1
    """)
    wolves_current = cursor.fetchone()
    
    if wolves_current:
        date, wolves_gap, pos = wolves_current
        logger.info(f"\n🐺 WOLVES 2025-26 SITUATION:")
        logger.info(f"   Current gap: {wolves_gap} points (Position: {pos})")
        logger.info(f"   Historical record: {gap} points")
        
        if wolves_gap > gap:
            logger.info(f"   ⚠️  Wolves face a {wolves_gap - gap} point bigger challenge than the record!")
        else:
            logger.info(f"   ✓ Wolves' gap is {gap - wolves_gap} points smaller than the record")
    
    logger.info("\n" + "="*80)
    logger.info(f"Database ready at: {db.db_path}")
    logger.info("="*80 + "\n")
    
    db.close()


if __name__ == "__main__":
    run_full_pipeline()
