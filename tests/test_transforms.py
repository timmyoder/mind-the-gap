"""Tests for data transformation pipeline."""

import pytest
import pandas as pd
from datetime import datetime

from src.data.transforms import (
    matches_to_long_format,
    calculate_cumulative_stats,
    create_standings_snapshots
)


@pytest.fixture
def sample_matches():
    """Create sample match data for testing."""
    return pd.DataFrame({
        'Season': ['2023-24'] * 4,
        'Date': pd.to_datetime([
            '2023-08-12', '2023-08-12',
            '2023-08-19', '2023-08-19'
        ]),
        'HomeTeam': ['Arsenal', 'Liverpool', 'Arsenal', 'Man City'],
        'AwayTeam': ['Man City', 'Chelsea', 'Liverpool', 'Chelsea'],
        'FTHG': [1, 2, 2, 3],
        'FTAG': [2, 1, 1, 0],
        'FTR': ['A', 'H', 'H', 'H']
    })


def test_matches_to_long_format(sample_matches):
    """Test conversion from match format to long format."""
    long_df = matches_to_long_format(sample_matches)
    
    # Should create 2 rows per match (one per team)
    assert len(long_df) == len(sample_matches) * 2
    
    # Check required columns exist
    required_cols = ['Season', 'Date', 'Team', 'Opponent', 'GF', 'GA', 'Pts', 'Venue']
    assert all(col in long_df.columns for col in required_cols)
    
    # Check points are assigned correctly
    # Arsenal at home vs Man City: lost 1-2 → 0 points
    arsenal_match1 = long_df[
        (long_df['Team'] == 'Arsenal') & 
        (long_df['Opponent'] == 'Man City')
    ]
    assert arsenal_match1.iloc[0]['Pts'] == 0
    
    # Liverpool at home vs Chelsea: won 2-1 → 3 points
    liverpool_match1 = long_df[
        (long_df['Team'] == 'Liverpool') & 
        (long_df['Opponent'] == 'Chelsea')
    ]
    assert liverpool_match1.iloc[0]['Pts'] == 3


def test_cumulative_stats_never_decrease(sample_matches):
    """Property-based test: cumulative points should never decrease."""
    long_df = matches_to_long_format(sample_matches)
    cumulative_df = calculate_cumulative_stats(long_df)
    
    # For each team, cumulative points should be monotonically increasing
    for team in cumulative_df['Team'].unique():
        team_data = cumulative_df[cumulative_df['Team'] == team].sort_values('Date')
        cum_pts = team_data['CumPts'].values
        
        # Check each point is >= previous point
        for i in range(1, len(cum_pts)):
            assert cum_pts[i] >= cum_pts[i-1], \
                f"Cumulative points decreased for {team}: {cum_pts[i-1]} → {cum_pts[i]}"


def test_cumulative_goal_difference(sample_matches):
    """Test that goal difference is calculated correctly."""
    long_df = matches_to_long_format(sample_matches)
    cumulative_df = calculate_cumulative_stats(long_df)
    
    # Check GD = GF - GA
    assert all(
        cumulative_df['CumGD'] == cumulative_df['CumGF'] - cumulative_df['CumGA']
    )


def test_standings_ranking_by_points(sample_matches):
    """Test that standings are ranked correctly by points."""
    long_df = matches_to_long_format(sample_matches)
    cumulative_df = calculate_cumulative_stats(long_df)
    standings = create_standings_snapshots(cumulative_df)
    
    # For each date, verify teams are ranked by points (descending)
    for (season, date), group in standings.groupby(['Season', 'Date']):
        points = group.sort_values('position')['points'].values
        
        # Check points are in descending order (or equal)
        for i in range(1, len(points)):
            assert points[i-1] >= points[i], \
                f"Incorrect ranking on {date}: position {i} has more points than position {i-1}"


def test_standings_positions_are_sequential():
    """Test that positions are 1, 2, 3, ... with no gaps."""
    sample_data = pd.DataFrame({
        'Season': ['2023-24'] * 6,
        'Date': pd.to_datetime(['2023-08-12'] * 6),
        'HomeTeam': ['A', 'B', 'C'] * 2,
        'AwayTeam': ['D', 'E', 'F'] * 2,
        'FTHG': [2, 1, 3, 0, 2, 1],
        'FTAG': [0, 1, 0, 1, 1, 2],
        'FTR': ['H', 'D', 'H', 'A', 'H', 'A']
    })
    
    long_df = matches_to_long_format(sample_data)
    cumulative_df = calculate_cumulative_stats(long_df)
    standings = create_standings_snapshots(cumulative_df)
    
    # Get standings for the date
    date_standings = standings[standings['Date'] == '2023-08-12']
    positions = sorted(date_standings['position'].values)
    
    # Should be [1, 2, 3, 4, 5, 6]
    assert positions == list(range(1, len(positions) + 1))


def test_played_column_increments():
    """Test that 'played' column increments correctly."""
    sample_data = pd.DataFrame({
        'Season': ['2023-24'] * 4,
        'Date': pd.to_datetime(['2023-08-12', '2023-08-12', '2023-08-19', '2023-08-19']),
        'HomeTeam': ['Arsenal', 'Liverpool', 'Arsenal', 'Man City'],
        'AwayTeam': ['Man City', 'Chelsea', 'Liverpool', 'Chelsea'],
        'FTHG': [1, 2, 2, 3],
        'FTAG': [2, 1, 1, 0],
        'FTR': ['A', 'H', 'H', 'H']
    })
    
    long_df = matches_to_long_format(sample_data)
    cumulative_df = calculate_cumulative_stats(long_df)
    
    # Arsenal played on both dates, should have Played=1 then Played=2
    arsenal_data = cumulative_df[cumulative_df['Team'] == 'Arsenal'].sort_values('Date')
    assert arsenal_data['Played'].tolist() == [1, 2]
    
    # Chelsea played twice on first date (both matches were on 2023-08-12)
    chelsea_data = cumulative_df[cumulative_df['Team'] == 'Chelsea'].sort_values('Date')
    # Chelsea appears twice on 2023-08-12 (once vs Liverpool, once vs Man City on 2023-08-19)
    # After cumulative calculation, Chelsea will have Played=1 then Played=2
    assert chelsea_data['Played'].tolist() == [1, 2], f"Expected [1, 2], got {chelsea_data['Played'].tolist()}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
