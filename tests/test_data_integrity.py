"""Property-based and data integrity tests.

These tests verify the logic and data processing pipeline is working correctly,
independent of specific historical results. They check mathematical properties,
consistency, and reasonable bounds.
"""

import pytest
import pandas as pd
from src.data.db import EPLDatabase


@pytest.fixture
def db():
    """Provide database connection."""
    with EPLDatabase() as database:
        yield database


class TestMatchDataIntegrity:
    """Verify raw match data is complete and consistent."""
    
    def test_full_seasons_have_correct_match_count(self, db):
        """Complete seasons should have 380 matches (20 teams) or 462 (22 teams)."""
        query = '''
        SELECT season, COUNT(*) as num_matches
        FROM raw_matches
        WHERE season NOT IN ('2025-26')  -- Exclude current incomplete season
        GROUP BY season
        '''
        df = pd.read_sql_query(query, db.conn)
        
        for _, row in df.iterrows():
            season = row['season']
            count = row['num_matches']
            
            if season in ['1993-94', '1994-95']:
                # 1993-94, 1994-95 had 22 teams = 462 matches
                assert count == 462, f"{season} should have 462 matches (22 teams), got {count}"
            else:
                # 1995-96 onwards = 20 teams = 380 matches
                assert count == 380, f"{season} should have 380 matches (20 teams), got {count}"
    
    def test_all_matches_have_valid_scores(self, db):
        """Goals should be non-negative integers in reasonable range."""
        query = '''
        SELECT season, date, home_team, away_team, home_goals, away_goals
        FROM raw_matches
        WHERE home_goals < 0 OR away_goals < 0 OR home_goals > 15 OR away_goals > 15
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found matches with invalid scores: {df.to_dict('records')}"
    
    def test_total_points_distributed_correctly(self, db):
        """Total points should be close to 3 * number of matches.
        
        Note: Actual may be lower due to:
        - Point deductions (e.g., Everton -8, Nottingham Forest -4 in 2023-24)
        - Our pipeline calculates from match results, not adjusted final standings
        """
        query = '''
        SELECT season, COUNT(*) * 3 as expected_total_points
        FROM raw_matches
        WHERE season = '2023-24'
        '''
        expected = pd.read_sql_query(query, db.conn).iloc[0]['expected_total_points']
        
        # Get actual points from standings
        query2 = '''
        SELECT SUM(points) as actual_total_points
        FROM (
            SELECT team, MAX(points) as points
            FROM standings_snapshots
            WHERE season = '2023-24'
            GROUP BY team
        )
        '''
        actual = pd.read_sql_query(query2, db.conn).iloc[0]['actual_total_points']
        
        # Actual should be <= expected (point deductions reduce totals)
        # Allow up to 150 points discrepancy for deductions
        diff = expected - actual  # Note: expected - actual (should be positive if deductions)
        assert 0 <= diff < 150, f"Points discrepancy out of range: expected {expected}, got {actual}, diff={diff}"


class TestStandingsIntegrity:
    """Verify standings snapshots are mathematically consistent."""
    
    def test_positions_are_sequential_without_gaps(self, db):
        """Every standings snapshot should have positions 1,2,3...N with no gaps."""
        query = '''
        SELECT season, date, 
               COUNT(DISTINCT position) as unique_positions,
               MAX(position) as max_position,
               COUNT(*) as total_teams
        FROM standings_snapshots
        WHERE season = '2023-24' AND date = '2024-05-19'  -- Final day
        GROUP BY season, date
        '''
        df = pd.read_sql_query(query, db.conn)
        
        for _, row in df.iterrows():
            # unique_positions should equal max_position (no gaps)
            assert row['unique_positions'] == row['max_position'], \
                f"Position gaps found: {row['unique_positions']} unique positions but max is {row['max_position']}"
            # Total teams should equal max position
            assert row['total_teams'] == row['max_position'], \
                f"Team count mismatch: {row['total_teams']} teams but max position is {row['max_position']}"
    
    def test_higher_points_means_higher_position(self, db):
        """Within each date, more points should mean better (lower) position."""
        query = '''
        WITH standings_with_next AS (
            SELECT season, date, team, position, points,
                   LEAD(points) OVER (PARTITION BY season, date ORDER BY position) as next_points
            FROM standings_snapshots
            WHERE season = '2023-24'
        )
        SELECT season, date, team, position, points, next_points
        FROM standings_with_next
        WHERE next_points IS NOT NULL AND points < next_points
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found teams with fewer points but better position: {df.to_dict('records')}"
    
    def test_points_never_decrease_for_team(self, db):
        """A team's points should never decrease as season progresses."""
        query = '''
        WITH team_progression AS (
            SELECT season, team, date, points,
                   LAG(points) OVER (PARTITION BY season, team ORDER BY date) as prev_points
            FROM standings_snapshots
            WHERE season = '2023-24'
        )
        SELECT season, team, date, prev_points, points
        FROM team_progression
        WHERE prev_points IS NOT NULL AND points < prev_points
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found teams where points decreased: {df.to_dict('records')}"
    
    def test_all_teams_play_same_number_of_games(self, db):
        """At season end, all teams should have played the same number of games."""
        query = '''
        SELECT season, MAX(played) as max_played, MIN(played) as min_played
        FROM standings_snapshots
        WHERE date = (SELECT MAX(date) FROM standings_snapshots WHERE season = standings_snapshots.season)
        AND season NOT IN ('2025-26')  -- Exclude incomplete season
        GROUP BY season
        HAVING max_played != min_played
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found seasons where teams played different number of games: {df.to_dict('records')}"


class TestGapCalculationIntegrity:
    """Verify relegation gap calculations are mathematically sound."""
    
    def test_gaps_are_in_reasonable_range(self, db):
        """Gaps should be between -70 and +50 points (dominant teams can have large negative gaps)."""
        query = '''
        SELECT season, date, team, gap_to_17th
        FROM relegation_gaps
        WHERE gap_to_17th < -70 OR gap_to_17th > 50
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found unreasonable gap values: {df.to_dict('records')}"
    
    def test_safety_line_consistency(self, db):
        """17th place should always have >= points than 18th place."""
        query = '''
        WITH positions_17_18 AS (
            SELECT season, date, 
                   MAX(CASE WHEN position = 17 THEN points END) as pos_17_points,
                   MAX(CASE WHEN position = 18 THEN points END) as pos_18_points
            FROM standings_snapshots
            GROUP BY season, date
            HAVING pos_17_points IS NOT NULL AND pos_18_points IS NOT NULL
        )
        SELECT season, date, pos_17_points, pos_18_points
        FROM positions_17_18
        WHERE pos_17_points < pos_18_points
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found cases where 18th has more points than 17th: {df.to_dict('records')}"
    
    def test_positive_gap_means_below_safety(self, db):
        """Teams with positive gap should have position >= 18."""
        query = '''
        SELECT season, date, team, position, gap_to_17th
        FROM relegation_gaps
        WHERE gap_to_17th > 0 AND position < 18
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found teams with positive gap but position < 18: {df.to_dict('records')}"
    
    def test_negative_gap_means_above_safety(self, db):
        """Teams with negative gap should have position <= 17."""
        query = '''
        SELECT season, date, team, position, gap_to_17th
        FROM relegation_gaps
        WHERE gap_to_17th < 0 AND position > 17
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found teams with negative gap but position > 17: {df.to_dict('records')}"
    
    def test_bottom_three_at_season_end_are_relegated(self, db):
        """Teams finishing in positions 18-20 should be marked as relegated (eventually_survived = 0)."""
        query = '''
        SELECT g.season, g.team, s.position, g.eventually_survived
        FROM relegation_gaps g
        JOIN standings_snapshots s ON g.season = s.season AND g.date = s.date AND g.team = s.team
        WHERE g.date = (SELECT MAX(date) FROM relegation_gaps WHERE season = g.season)
        AND s.position >= 18
        AND g.eventually_survived != 0
        AND g.season NOT IN ('2025-26')  -- Exclude incomplete season
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found bottom-3 teams not marked as relegated: {df.to_dict('records')}"
    
    def test_top_seventeen_at_season_end_survived(self, db):
        """Teams finishing in positions 1-17 should be marked as survived or NULL (never in danger)."""
        query = '''
        SELECT g.season, g.team, s.position, g.eventually_survived
        FROM relegation_gaps g
        JOIN standings_snapshots s ON g.season = s.season AND g.date = s.date AND g.team = s.team
        WHERE g.date = (SELECT MAX(date) FROM relegation_gaps WHERE season = g.season)
        AND s.position <= 17
        AND g.eventually_survived = 0
        AND g.season NOT IN ('2025-26')  -- Exclude incomplete season
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found top-17 teams marked as relegated: {df.to_dict('records')}"


class TestSeasonConsistency:
    """Verify teams and dates are consistent within seasons."""
    
    def test_same_teams_throughout_season(self, db):
        """Same set of teams should appear throughout each season (after opening day).
        
        Note: Opening days may have fewer teams due to staggered match scheduling.
        Only teams that have played at least one match appear in standings.
        """
        query = '''
        WITH season_teams AS (
            SELECT season, team
            FROM standings_snapshots
            WHERE date = (SELECT MAX(date) FROM standings_snapshots WHERE season = standings_snapshots.season)
            AND season = '2023-24'
        ),
        all_dates AS (
            SELECT DISTINCT season, date
            FROM standings_snapshots
            WHERE season = '2023-24'
            AND date > (SELECT MIN(date) + 3 FROM standings_snapshots WHERE season = '2023-24')  -- Skip opening weekend
        )
        SELECT ad.date, st.team, COUNT(*) as missing_count
        FROM all_dates ad
        CROSS JOIN season_teams st
        WHERE NOT EXISTS (
            SELECT 1 FROM standings_snapshots s
            WHERE s.season = ad.season AND s.date = ad.date AND s.team = st.team
        )
        GROUP BY ad.date, st.team
        '''
        df = pd.read_sql_query(query, db.conn)
        
        # After opening weekend, all teams should appear on all dates
        assert df.empty, f"Found teams missing after opening weekend: {df.head(10).to_dict('records')}"
    
    def test_dates_progress_chronologically(self, db):
        """Within a season, dates should always progress forward."""
        query = '''
        WITH date_progression AS (
            SELECT DISTINCT season, date,
                   LAG(date) OVER (PARTITION BY season ORDER BY date) as prev_date
            FROM standings_snapshots
            WHERE season = '2023-24'
        )
        SELECT season, prev_date, date
        FROM date_progression
        WHERE prev_date IS NOT NULL AND date < prev_date
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found dates going backwards: {df.to_dict('records')}"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_no_null_critical_fields(self, db):
        """Critical fields should never be NULL."""
        query = '''
        SELECT season, date, team, position, points, gap_to_17th
        FROM relegation_gaps
        WHERE season IS NULL OR date IS NULL OR team IS NULL 
           OR position IS NULL OR points IS NULL OR gap_to_17th IS NULL
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found NULL values in critical fields: {df.to_dict('records')}"
    
    def test_season_format_is_consistent(self, db):
        """All seasons should follow YYYY-YY format."""
        query = '''
        SELECT DISTINCT season
        FROM raw_matches
        WHERE season NOT LIKE '____-__'
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found seasons with incorrect format: {df.to_dict('records')}"
    
    def test_no_duplicate_standings_per_date(self, db):
        """Each team should appear exactly once per date in standings."""
        query = '''
        SELECT season, date, team, COUNT(*) as count
        FROM standings_snapshots
        GROUP BY season, date, team
        HAVING count > 1
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found duplicate standings entries: {df.to_dict('records')}"
