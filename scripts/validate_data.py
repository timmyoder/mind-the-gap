#!/usr/bin/env python3
"""Validate the EPL terrain database against known historical facts.

This script checks that our pipeline correctly captures famous relegation battles
and verifies the integrity of the data processing.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.db import EPLDatabase
import pandas as pd


def check_west_ham_record() -> bool:
    """Verify West Ham 2006-07 10-point record exists."""
    with EPLDatabase() as db:
        query = '''
        SELECT MAX(gap_to_17th) as max_gap, date, position
        FROM relegation_gaps
        WHERE team LIKE '%West Ham%' AND season = '2006-07' AND eventually_survived = 1
        '''
        df = pd.read_sql_query(query, db.conn)
        
        if df.empty or df.iloc[0]['max_gap'] != 10:
            print(f"❌ West Ham 2006-07 record check FAILED")
            print(f"   Expected: 10 points, Got: {df.iloc[0]['max_gap'] if not df.empty else 'No data'}")
            return False
        
        print(f"✓ West Ham 2006-07: 10-point gap verified (Date: {df.iloc[0]['date']}, Position: {df.iloc[0]['position']})")
        return True


def check_no_survivors_above_10() -> bool:
    """Verify no team has survived a gap larger than 10 points."""
    with EPLDatabase() as db:
        query = '''
        SELECT season, team, MAX(gap_to_17th) as max_gap
        FROM relegation_gaps
        WHERE eventually_survived = 1
        GROUP BY season, team
        HAVING max_gap > 10
        '''
        df = pd.read_sql_query(query, db.conn)
        
        if not df.empty:
            print(f"❌ Found {len(df)} teams that survived gaps > 10 points:")
            for _, row in df.iterrows():
                print(f"   {row['season']} {row['team']}: {row['max_gap']} points")
            return False
        
        print(f"✓ No team has survived a gap > 10 points")
        return True


def check_11_plus_always_relegated() -> bool:
    """Verify teams with 11+ point gaps are always relegated."""
    with EPLDatabase() as db:
        query = '''
        SELECT season, team, MAX(gap_to_17th) as max_gap, MAX(CAST(eventually_survived AS INTEGER)) as survived
        FROM relegation_gaps
        WHERE gap_to_17th >= 11
        GROUP BY season, team
        HAVING survived = 1
        '''
        df = pd.read_sql_query(query, db.conn)
        
        if not df.empty:
            print(f"❌ Found {len(df)} teams that SURVIVED 11+ point gaps:")
            for _, row in df.iterrows():
                print(f"   {row['season']} {row['team']}: {row['max_gap']} points")
            return False
        
        print(f"✓ All teams with 11+ point gaps were relegated")
        return True


def check_famous_relegations() -> bool:
    """Verify famous relegation battles are correctly recorded."""
    test_cases = [
        ('Derby', '2007-08', 11, False),  # Derby should be relegated
        ('Aston Villa', '2015-16', 11, False),  # Villa should be relegated
        ('Sheffield United', '2020-21', 11, False),  # Sheffield should be relegated
    ]
    
    all_passed = True
    for team_name, season, min_gap, should_survive in test_cases:
        with EPLDatabase() as db:
            query = f'''
            SELECT MAX(gap_to_17th) as max_gap, MAX(CAST(eventually_survived AS INTEGER)) as survived
            FROM relegation_gaps
            WHERE team LIKE '%{team_name.split()[0]}%' AND season = '{season}'
            '''
            df = pd.read_sql_query(query, db.conn)
            
            if df.empty or df.iloc[0]['max_gap'] is None:
                print(f"❌ {season} {team_name}: No data found")
                all_passed = False
                continue
            
            max_gap = df.iloc[0]['max_gap']
            survived = bool(df.iloc[0]['survived'])
            
            if max_gap < min_gap:
                print(f"❌ {season} {team_name}: Expected gap >= {min_gap}, got {max_gap}")
                all_passed = False
            elif survived != should_survive:
                status = "survived" if survived else "relegated"
                expected = "survive" if should_survive else "be relegated"
                print(f"❌ {season} {team_name}: Expected to {expected}, but {status}")
                all_passed = False
            else:
                status = "survived" if survived else "relegated"
                print(f"✓ {season} {team_name}: {max_gap}-point gap, {status}")
    
    return all_passed


def check_data_completeness() -> bool:
    """Verify database has expected amount of data."""
    with EPLDatabase() as db:
        # Check number of seasons
        query = "SELECT COUNT(DISTINCT season) as num_seasons FROM raw_matches"
        df = pd.read_sql_query(query, db.conn)
        num_seasons = df.iloc[0]['num_seasons']
        
        if num_seasons < 30:
            print(f"❌ Expected ~33 seasons, found {num_seasons}")
            return False
        
        print(f"✓ Database contains {num_seasons} seasons of data")
        
        # Check total records
        query = "SELECT COUNT(*) as total FROM standings_snapshots"
        df = pd.read_sql_query(query, db.conn)
        total_snapshots = df.iloc[0]['total']
        
        if total_snapshots < 60000:
            print(f"❌ Expected ~68K standings snapshots, found {total_snapshots}")
            return False
        
        print(f"✓ Database contains {total_snapshots:,} standings snapshots")
        
        # Check gap records
        query = "SELECT COUNT(*) as total FROM relegation_gaps"
        df = pd.read_sql_query(query, db.conn)
        total_gaps = df.iloc[0]['total']
        
        if total_gaps < 60000:
            print(f"❌ Expected ~68K gap records, found {total_gaps}")
            return False
        
        print(f"✓ Database contains {total_gaps:,} gap records")
        
        return True


def main():
    """Run all validation checks."""
    print("="*80)
    print("EPL TERRAIN DATA VALIDATION")
    print("="*80)
    print()
    
    checks = [
        ("West Ham 10-point record", check_west_ham_record),
        ("No survivors above 10 points", check_no_survivors_above_10),
        ("11+ points always relegated", check_11_plus_always_relegated),
        ("Famous relegation battles", check_famous_relegations),
        ("Data completeness", check_data_completeness),
    ]
    
    results = []
    for name, check_func in checks:
        print(f"\n{name}:")
        try:
            passed = check_func()
            results.append((name, passed))
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append((name, False))
    
    print()
    print("="*80)
    print("SUMMARY")
    print("="*80)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Result: {passed_count}/{total_count} checks passed")
    
    sys.exit(0 if passed_count == total_count else 1)


if __name__ == '__main__':
    main()
