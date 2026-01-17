"""SQLite database setup and management for EPL terrain data."""

import sqlite3
from pathlib import Path
from typing import Optional


class EPLDatabase:
    """Manages SQLite database for EPL match and standings data."""

    def __init__(self, db_path: str = "data/epl_terrain.db"):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self) -> sqlite3.Connection:
        """Establish database connection.
        
        Returns:
            SQLite connection object
        """
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        return self.conn

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def create_tables(self) -> None:
        """Create all database tables with proper schema."""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()

        # Table 1: Raw match results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raw_matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season TEXT NOT NULL,
                date TEXT NOT NULL,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                home_goals INTEGER NOT NULL,
                away_goals INTEGER NOT NULL,
                result TEXT NOT NULL CHECK(result IN ('H', 'D', 'A')),
                UNIQUE(season, date, home_team, away_team)
            )
        """)

        # Table 2: Daily league table snapshots
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS standings_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season TEXT NOT NULL,
                date TEXT NOT NULL,
                team TEXT NOT NULL,
                position INTEGER NOT NULL,
                played INTEGER NOT NULL,
                points INTEGER NOT NULL,
                goals_for INTEGER NOT NULL,
                goals_against INTEGER NOT NULL,
                goal_difference INTEGER NOT NULL,
                UNIQUE(season, date, team)
            )
        """)

        # Table 3: Pre-calculated relegation gaps
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relegation_gaps (
                gap_id INTEGER PRIMARY KEY AUTOINCREMENT,
                season TEXT NOT NULL,
                date TEXT NOT NULL,
                team TEXT NOT NULL,
                position INTEGER NOT NULL,
                points INTEGER NOT NULL,
                gap_to_17th INTEGER NOT NULL,
                games_in_hand_adjusted INTEGER,
                eventually_survived BOOLEAN,
                UNIQUE(season, date, team)
            )
        """)

        # Create indexes for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_matches_season_date 
            ON raw_matches(season, date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_standings_season_date 
            ON standings_snapshots(season, date)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gaps_season_team 
            ON relegation_gaps(season, team)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gaps_survived 
            ON relegation_gaps(eventually_survived)
        """)

        self.conn.commit()

    def get_table_at_date(self, season: str, date: str) -> list:
        """Query standings snapshot for a specific date.
        
        Args:
            season: Season string (e.g., "2006-07")
            date: Date string (YYYY-MM-DD format)
            
        Returns:
            List of Row objects with standings data
        """
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM standings_snapshots
            WHERE season = ? AND date = ?
            ORDER BY position
        """, (season, date))

        return cursor.fetchall()

    def get_max_gap_survived(self) -> Optional[sqlite3.Row]:
        """Find the largest gap ever overcome by a surviving team.
        
        Returns:
            Row with maximum gap details, or None if no data
        """
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 
                season,
                date,
                team,
                position,
                points,
                gap_to_17th,
                games_in_hand_adjusted
            FROM relegation_gaps
            WHERE eventually_survived = 1
            ORDER BY gap_to_17th DESC
            LIMIT 1
        """)

        return cursor.fetchone()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def initialize_database(db_path: str = "data/epl_terrain.db") -> EPLDatabase:
    """Initialize database and create tables.
    
    Args:
        db_path: Path to SQLite database file
        
    Returns:
        EPLDatabase instance with tables created
    """
    db = EPLDatabase(db_path)
    db.connect()
    db.create_tables()
    return db


if __name__ == "__main__":
    # Quick test: create database and tables
    db = initialize_database()
    print(f"Database created at: {db.db_path}")
    print("Tables created successfully")
    db.close()
