"""Integration tests that verify key historical facts are correctly captured."""

import pytest
import pandas as pd
from src.data.db import EPLDatabase


@pytest.fixture
def db():
    """Provide database connection."""
    with EPLDatabase() as database:
        yield database


class TestHistoricalRecords:
    """Verify famous relegation battles are correctly recorded."""
    
    def test_west_ham_10_point_record(self, db):
        """West Ham 2006-07 should have overcome a 10-point gap."""
        query = '''
        SELECT MAX(gap_to_17th) as max_gap
        FROM relegation_gaps
        WHERE team LIKE '%West Ham%' AND season = '2006-07' AND eventually_survived = 1
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert not df.empty, "West Ham 2006-07 data not found"
        assert df.iloc[0]['max_gap'] == 10, f"Expected 10-point gap, got {df.iloc[0]['max_gap']}"
    
    def test_no_survivors_above_10_points(self, db):
        """No team has survived a gap larger than 10 points."""
        query = '''
        SELECT season, team, MAX(gap_to_17th) as max_gap
        FROM relegation_gaps
        WHERE eventually_survived = 1
        GROUP BY season, team
        HAVING max_gap > 10
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found teams that survived > 10 point gaps: {df.to_dict('records')}"
    
    def test_11_plus_always_relegated(self, db):
        """Teams with 11+ point gaps are always relegated."""
        query = '''
        SELECT season, team, MAX(gap_to_17th) as max_gap
        FROM relegation_gaps
        WHERE gap_to_17th >= 11 AND eventually_survived = 1
        GROUP BY season, team
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found teams that survived 11+ point gaps: {df.to_dict('records')}"
    
    @pytest.mark.parametrize("team,season,should_be_relegated", [
        ("Derby", "2007-08", True),
        ("Aston Villa", "2015-16", True),
        ("Sheffield United", "2020-21", True),
    ])
    def test_famous_relegations(self, db, team, season, should_be_relegated):
        """Verify famous relegation battles are correctly recorded."""
        query = f'''
        SELECT MAX(CAST(eventually_survived AS INTEGER)) as survived
        FROM relegation_gaps
        WHERE team LIKE '%{team.split()[0]}%' AND season = '{season}'
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert not df.empty, f"{season} {team} data not found"
        
        survived = bool(df.iloc[0]['survived'])
        if should_be_relegated:
            assert not survived, f"{season} {team} should have been relegated but survived"
        else:
            assert survived, f"{season} {team} should have survived but was relegated"


class TestDataIntegrity:
    """Verify data pipeline integrity."""
    
    def test_minimum_seasons(self, db):
        """Database should contain at least 30 seasons."""
        query = "SELECT COUNT(DISTINCT season) as num_seasons FROM raw_matches"
        df = pd.read_sql_query(query, db.conn)
        
        assert df.iloc[0]['num_seasons'] >= 30, "Expected at least 30 seasons of data"
    
    def test_all_survivors_finished_17th_or_higher(self, db):
        """Teams marked as survived must have finished in a safe position."""
        # This test would require final standings data
        # For now, just verify the eventually_survived column is populated
        query = '''
        SELECT COUNT(*) as count
        FROM relegation_gaps
        WHERE gap_to_17th > 0 AND eventually_survived IS NULL
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.iloc[0]['count'] == 0, "Found teams in danger with NULL survival status"
    
    def test_cumulative_points_never_decrease(self, db):
        """Within a season, a team's points should never decrease over time."""
        query = '''
        WITH team_progression AS (
            SELECT 
                season, team, date, points,
                LAG(points) OVER (PARTITION BY season, team ORDER BY date) as prev_points
            FROM standings_snapshots
        )
        SELECT season, team, date, prev_points, points
        FROM team_progression
        WHERE prev_points IS NOT NULL AND points < prev_points
        LIMIT 5
        '''
        df = pd.read_sql_query(query, db.conn)
        
        assert df.empty, f"Found cases where points decreased: {df.to_dict('records')}"
