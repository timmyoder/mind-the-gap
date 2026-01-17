"""Query and analysis functions for relegation gap data."""

import sqlite3
import pandas as pd
from typing import Optional, List, Tuple


def get_max_gap_survived(conn: sqlite3.Connection) -> Optional[Tuple]:
    """Find the biggest relegation gap ever successfully overcome.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        Tuple of (season, date, team, position, gap) or None
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            season,
            date,
            team,
            position,
            gap_to_17th,
            games_in_hand_adjusted
        FROM relegation_gaps
        WHERE eventually_survived = 1
        ORDER BY gap_to_17th DESC
        LIMIT 1
    """)
    
    return cursor.fetchone()


def get_team_season_gaps(
    conn: sqlite3.Connection,
    team: str,
    season: str
) -> pd.DataFrame:
    """Get all relegation gap data for a specific team in a season.
    
    Args:
        conn: SQLite database connection
        team: Team name
        season: Season string (e.g., "2006-07")
        
    Returns:
        DataFrame with gap history for that team
    """
    query = """
        SELECT *
        FROM relegation_gaps
        WHERE team = ? AND season = ?
        ORDER BY date
    """
    
    return pd.read_sql_query(query, conn, params=(team, season))


def get_all_survivors_by_max_gap(conn: sqlite3.Connection) -> pd.DataFrame:
    """Get maximum gap reached by each team that eventually survived.
    
    Returns:
        DataFrame with columns: season, team, max_gap, date_of_max_gap
    """
    query = """
        SELECT 
            season,
            team,
            MAX(gap_to_17th) as max_gap,
            date as date_of_max_gap
        FROM relegation_gaps
        WHERE eventually_survived = 1
        GROUP BY season, team
        ORDER BY max_gap DESC
    """
    
    return pd.read_sql_query(query, conn)


def compare_team_to_history(
    conn: sqlite3.Connection,
    team: str,
    season: str,
    current_gap: int
) -> dict:
    """Compare a team's current gap to historical survival records.
    
    Args:
        conn: SQLite database connection
        team: Team name
        season: Current season
        current_gap: Current points gap to safety
        
    Returns:
        Dictionary with comparison statistics
    """
    # Get historical maximum
    max_survived = get_max_gap_survived(conn)
    
    if not max_survived:
        return {
            'team': team,
            'season': season,
            'current_gap': current_gap,
            'historical_max': None,
            'is_record': False,
            'message': 'No historical data available'
        }
    
    hist_season, hist_date, hist_team, hist_pos, hist_gap, hist_adjusted = max_survived
    
    return {
        'team': team,
        'season': season,
        'current_gap': current_gap,
        'historical_max': hist_gap,
        'historical_record_holder': hist_team,
        'historical_season': hist_season,
        'historical_date': hist_date,
        'is_record': current_gap > hist_gap,
        'gap_difference': current_gap - hist_gap,
        'message': (
            f"{team} would need to overcome a {current_gap}-point deficit. "
            f"The record is {hist_gap} points by {hist_team} in {hist_season}."
        )
    }


def get_standings_at_date(
    conn: sqlite3.Connection,
    season: str,
    date: str
) -> pd.DataFrame:
    """Get league table as it stood on a specific date.
    
    Args:
        conn: SQLite database connection
        season: Season string
        date: Date string (YYYY-MM-DD)
        
    Returns:
        DataFrame with standings on that date
    """
    query = """
        SELECT *
        FROM standings_snapshots
        WHERE season = ? AND date = ?
        ORDER BY position
    """
    
    return pd.read_sql_query(query, conn, params=(season, date))


def get_season_timeline(
    conn: sqlite3.Connection,
    season: str,
    teams: Optional[List[str]] = None
) -> pd.DataFrame:
    """Get standings progression throughout a season.
    
    Args:
        conn: SQLite database connection
        season: Season string
        teams: Optional list of teams to filter (default: all teams)
        
    Returns:
        DataFrame with date, team, position, points
    """
    if teams:
        placeholders = ','.join('?' * len(teams))
        query = f"""
            SELECT date, team, position, points, played
            FROM standings_snapshots
            WHERE season = ? AND team IN ({placeholders})
            ORDER BY date, position
        """
        params = [season] + teams
    else:
        query = """
            SELECT date, team, position, points, played
            FROM standings_snapshots
            WHERE season = ?
            ORDER BY date, position
        """
        params = [season]
    
    return pd.read_sql_query(query, conn, params=params)


def get_relegation_zone_history(
    conn: sqlite3.Connection,
    season: str
) -> pd.DataFrame:
    """Get all teams that spent time in relegation zone during a season.
    
    Args:
        conn: SQLite database connection
        season: Season string
        
    Returns:
        DataFrame showing which teams were in bottom 3 and when
    """
    query = """
        SELECT 
            team,
            MIN(date) as first_in_relegation,
            MAX(date) as last_in_relegation,
            COUNT(*) as days_in_relegation,
            MAX(gap_to_17th) as worst_gap,
            MAX(CASE WHEN eventually_survived THEN 1 ELSE 0 END) as survived
        FROM relegation_gaps
        WHERE season = ?
        GROUP BY team
        ORDER BY survived DESC, worst_gap DESC
    """
    
    return pd.read_sql_query(query, conn, params=(season,))


if __name__ == "__main__":
    # Quick test - requires populated database
    from src.data.db import EPLDatabase
    
    db = EPLDatabase()
    db.connect()
    
    print("Testing query functions...")
    print("\nLooking for maximum gap survived...")
    
    max_gap = get_max_gap_survived(db.conn)
    
    if max_gap:
        season, date, team, pos, gap, adjusted = max_gap
        print(f"\nRecord: {team} in {season}")
        print(f"Date: {date}")
        print(f"Position: {pos}")
        print(f"Gap to safety: {gap} points")
        print(f"Adjusted for games in hand: {adjusted} points")
    else:
        print("\nNo data found - database may be empty")
        print("Run data pipeline first to populate database")
    
    db.close()
