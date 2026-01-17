"""Transform match-level data into standings snapshots and relegation gaps."""

import pandas as pd
import sqlite3
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


def matches_to_long_format(df: pd.DataFrame) -> pd.DataFrame:
    """Convert match results to long format (one row per team per match).
    
    Each match creates two rows: one for home team, one for away team.
    
    Args:
        df: DataFrame with columns: Season, Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR
        
    Returns:
        Long-format DataFrame with columns: Season, Date, Team, Opponent, GF, GA, Pts
    """
    # Home team rows
    homes = df[['Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']].copy()
    homes = homes.rename(columns={
        'HomeTeam': 'Team',
        'AwayTeam': 'Opponent',
        'FTHG': 'GF',
        'FTAG': 'GA'
    })
    homes['Pts'] = homes['FTR'].map({'H': 3, 'D': 1, 'A': 0})
    homes['Venue'] = 'H'
    
    # Away team rows
    aways = df[['Season', 'Date', 'AwayTeam', 'HomeTeam', 'FTAG', 'FTHG', 'FTR']].copy()
    aways = aways.rename(columns={
        'AwayTeam': 'Team',
        'HomeTeam': 'Opponent',
        'FTAG': 'GF',
        'FTHG': 'GA'
    })
    aways['Pts'] = aways['FTR'].map({'A': 3, 'D': 1, 'H': 0})
    aways['Venue'] = 'A'
    
    # Combine and sort
    long_df = pd.concat([homes, aways], ignore_index=True)
    long_df = long_df.sort_values(['Season', 'Date', 'Team']).reset_index(drop=True)
    
    # Drop FTR column (no longer needed)
    long_df = long_df.drop('FTR', axis=1)
    
    return long_df


def calculate_cumulative_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate cumulative points, goals for, goals against for each team.
    
    Args:
        df: Long-format DataFrame from matches_to_long_format()
        
    Returns:
        DataFrame with cumulative columns: CumPts, CumGF, CumGA, CumGD, Played
    """
    df = df.copy()
    
    # Sort to ensure cumulative calculations are in date order
    df = df.sort_values(['Season', 'Team', 'Date'])
    
    # Calculate cumulative stats per team per season
    df['CumPts'] = df.groupby(['Season', 'Team'])['Pts'].cumsum()
    df['CumGF'] = df.groupby(['Season', 'Team'])['GF'].cumsum()
    df['CumGA'] = df.groupby(['Season', 'Team'])['GA'].cumsum()
    df['CumGD'] = df['CumGF'] - df['CumGA']
    df['Played'] = df.groupby(['Season', 'Team']).cumcount() + 1
    
    return df


def create_standings_snapshots(df: pd.DataFrame) -> pd.DataFrame:
    """Create league table snapshots for each date with matches.
    
    Ranks teams by official PL rules: Points > GD > GF > Alphabetical
    Forward-fills team stats to ensure all teams appear on all match dates.
    
    Args:
        df: DataFrame with cumulative stats from calculate_cumulative_stats()
        
    Returns:
        DataFrame with daily standings including Position column
    """
    # Get one row per team per date (after all matches on that date)
    team_dates = (
        df.groupby(['Season', 'Date', 'Team'])
        .agg({
            'CumPts': 'max',
            'CumGF': 'max',
            'CumGA': 'max',
            'CumGD': 'max',
            'Played': 'max'
        })
        .reset_index()
    )
    
    # Forward-fill: For each season, ensure all teams appear on all match dates
    all_standings = []
    for season in team_dates['Season'].unique():
        season_data = team_dates[team_dates['Season'] == season].copy()
        all_teams = season_data['Team'].unique()
        all_dates = sorted(season_data['Date'].unique())
        
        # Create complete grid of teams x dates
        for date in all_dates:
            date_data = season_data[season_data['Date'] == date].copy()
            teams_on_date = set(date_data['Team'])
            
            # For teams that didn't play on this date, carry forward their last known stats
            for team in all_teams:
                if team not in teams_on_date:
                    # Find most recent data for this team before this date
                    previous_data = season_data[
                        (season_data['Team'] == team) & 
                        (season_data['Date'] < date)
                    ].sort_values('Date')
                    
                    if not previous_data.empty:
                        # Use most recent stats
                        last_stats = previous_data.iloc[-1].copy()
                        last_stats['Date'] = date  # Update to current date
                        date_data = pd.concat([date_data, pd.DataFrame([last_stats])], ignore_index=True)
            
            all_standings.append(date_data)
    
    standings = pd.concat(all_standings, ignore_index=True)
    
    # Sort by ranking criteria and assign positions
    standings = standings.sort_values(
        ['Season', 'Date', 'CumPts', 'CumGD', 'CumGF', 'Team'],
        ascending=[True, True, False, False, False, True]
    )
    
    # Assign position within each date
    standings['Position'] = standings.groupby(['Season', 'Date']).cumcount() + 1
    
    # Rename columns for clarity
    standings = standings.rename(columns={
        'Team': 'team',
        'CumPts': 'points',
        'CumGF': 'goals_for',
        'CumGA': 'goals_against',
        'CumGD': 'goal_difference',
        'Played': 'played',
        'Position': 'position'
    })
    
    return standings


def calculate_relegation_gaps(standings: pd.DataFrame) -> pd.DataFrame:
    """Calculate points gap to 17th place (safety) for ALL teams.
    
    Calculates gap for every team in the league, creating complete landscape:
    - Negative gap = safe (points above 17th place)
    - Zero gap = exactly at safety line (tied with 17th)
    - Positive gap = danger (points below 17th place)
    
    Args:
        standings: DataFrame from create_standings_snapshots()
        
    Returns:
        DataFrame with gap calculations for all teams at every date
    """
    gaps = []
    
    # Group by season and date
    for (season, date), group in standings.groupby(['Season', 'Date']):
        # Sort by position to ensure correct ordering
        group = group.sort_values('position')
        
        # Get 17th place points (safety line)
        safety_rows = group[group['position'] == 17]
        
        if safety_rows.empty:
            # Handle seasons with fewer teams or incomplete data
            continue
        
        safety_points = safety_rows.iloc[0]['points']
        
        # Calculate gaps for ALL teams (no filtering)
        all_teams = group.copy()
        
        # Gap calculation: safety_points - team_points
        # Positive = below safety (danger), Negative = above safety (safe)
        all_teams['gap_to_17th'] = safety_points - all_teams['points']
        
        # Calculate games in hand (difference vs team with most games played)
        max_played = group['played'].max()
        all_teams['games_in_hand'] = max_played - all_teams['played']
        
        # Adjusted gap (assuming 3 points per game in hand)
        all_teams['games_in_hand_adjusted'] = (
            all_teams['gap_to_17th'] - (all_teams['games_in_hand'] * 3)
        )
        
        gaps.append(all_teams)
    
    if not gaps:
        return pd.DataFrame()
    
    return pd.concat(gaps, ignore_index=True)


def mark_survivors(gaps: pd.DataFrame, final_standings: pd.DataFrame) -> pd.DataFrame:
    """Mark which teams eventually survived relegation.
    
    Only marks teams that were actually in danger at some point (gap_to_17th > 0).
    Teams that never dropped below safety will have eventually_survived = None.
    
    Args:
        gaps: DataFrame from calculate_relegation_gaps()
        final_standings: Final standings for each season (position at season end)
        
    Returns:
        DataFrame with 'eventually_survived' column added (boolean or None)
    """
    # Get final positions (last date in each season)
    season_final = (
        final_standings
        .sort_values(['Season', 'Date'])
        .groupby(['Season', 'team'])
        .last()
        .reset_index()
    )
    
    season_final['survived'] = season_final['position'] <= 17
    survivor_map = season_final.set_index(['Season', 'team'])['survived'].to_dict()
    
    # Add survival status to gaps
    gaps = gaps.copy()
    
    # Only mark survival status for teams that were in danger (gap > 0)
    # Teams always safe (gap <= 0) get None
    def get_survival_status(row):
        if row['gap_to_17th'] > 0:  # Was in danger
            return survivor_map.get((row['Season'], row['team']), False)
        else:  # Never in danger
            return None
    
    gaps['eventually_survived'] = gaps.apply(get_survival_status, axis=1)
    
    return gaps


def insert_matches_to_db(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """Insert match results into raw_matches table.
    
    Args:
        df: DataFrame with match results
        conn: SQLite database connection
        
    Returns:
        Number of rows inserted
    """
    df_insert = df[['Season', 'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']].copy()
    df_insert['Date'] = df_insert['Date'].dt.strftime('%Y-%m-%d')
    
    # Rename columns to match database schema (snake_case)
    df_insert = df_insert.rename(columns={
        'Season': 'season',
        'Date': 'date',
        'HomeTeam': 'home_team',
        'AwayTeam': 'away_team',
        'FTHG': 'home_goals',
        'FTAG': 'away_goals',
        'FTR': 'result'
    })
    
    df_insert.to_sql(
        'raw_matches',
        conn,
        if_exists='append',
        index=False,
        dtype={
            'season': 'TEXT',
            'date': 'TEXT',
            'home_team': 'TEXT',
            'away_team': 'TEXT',
            'home_goals': 'INTEGER',
            'away_goals': 'INTEGER',
            'result': 'TEXT'
        }
    )
    
    return len(df_insert)


def insert_standings_to_db(standings: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """Insert standings snapshots into database.
    
    Args:
        standings: DataFrame from create_standings_snapshots()
        conn: SQLite database connection
        
    Returns:
        Number of rows inserted
    """
    df_insert = standings.copy()
    
    # Rename columns to match database schema (snake_case)
    df_insert = df_insert.rename(columns={
        'Season': 'season',
        'Date': 'date'
    })
    
    # Format date for database
    df_insert['date'] = pd.to_datetime(df_insert['date']).dt.strftime('%Y-%m-%d')
    
    df_insert.to_sql(
        'standings_snapshots',
        conn,
        if_exists='append',
        index=False,
        dtype={
            'season': 'TEXT',
            'date': 'TEXT',
            'team': 'TEXT',
            'position': 'INTEGER',
            'played': 'INTEGER',
            'points': 'INTEGER',
            'goals_for': 'INTEGER',
            'goals_against': 'INTEGER',
            'goal_difference': 'INTEGER'
        }
    )
    
    return len(df_insert)


def insert_gaps_to_db(gaps: pd.DataFrame, conn: sqlite3.Connection) -> int:
    """Insert relegation gaps into database.
    
    Args:
        gaps: DataFrame from mark_survivors()
        conn: SQLite database connection
        
    Returns:
        Number of rows inserted
    """
    df_insert = gaps.copy()
    
    # Rename columns to match database schema (snake_case)
    df_insert = df_insert.rename(columns={
        'Season': 'season',
        'Date': 'date'
    })
    
    # Select columns for database
    df_insert = df_insert[[
        'season', 'date', 'team', 'position', 'points',
        'gap_to_17th', 'games_in_hand_adjusted', 'eventually_survived'
    ]]
    
    df_insert.to_sql(
        'relegation_gaps',
        conn,
        if_exists='append',
        index=False,
        dtype={
            'season': 'TEXT',
            'date': 'TEXT',
            'team': 'TEXT',
            'position': 'INTEGER',
            'points': 'INTEGER',
            'gap_to_17th': 'INTEGER',
            'games_in_hand_adjusted': 'INTEGER',
            'eventually_survived': 'BOOLEAN'
        }
    )
    
    return len(df_insert)


if __name__ == "__main__":
    # Quick test with sample data
    logging.basicConfig(level=logging.INFO)
    
    # Create sample match data
    sample_data = {
        'Season': ['2023-24'] * 4,
        'Date': pd.to_datetime(['2023-08-12', '2023-08-12', '2023-08-19', '2023-08-19']),
        'HomeTeam': ['Arsenal', 'Liverpool', 'Arsenal', 'Man City'],
        'AwayTeam': ['Man City', 'Chelsea', 'Liverpool', 'Chelsea'],
        'FTHG': [1, 2, 2, 3],
        'FTAG': [2, 1, 1, 0],
        'FTR': ['A', 'H', 'H', 'H']
    }
    
    df = pd.DataFrame(sample_data)
    print("Sample matches:")
    print(df)
    
    print("\n" + "="*80)
    long_df = matches_to_long_format(df)
    print("\nLong format:")
    print(long_df)
    
    print("\n" + "="*80)
    cumulative_df = calculate_cumulative_stats(long_df)
    print("\nCumulative stats:")
    print(cumulative_df[['Season', 'Date', 'Team', 'Pts', 'CumPts', 'CumGD']])
    
    print("\n" + "="*80)
    standings = create_standings_snapshots(cumulative_df)
    print("\nStandings snapshots:")
    print(standings)
