"""Methodology tab: Data sources and calculation methods."""

import streamlit as st


def render_methodology_tab(db_path: str, season_start: str, season_end: str):
    """Render the Methodology tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
    """
    st.subheader("📚 Methodology & Data Sources")
    
    # Data Sources
    st.markdown("### 📊 Data Sources")
    st.markdown("""
    All historical Premier League match data is sourced from:
    
    **[Football-Data.co.uk](https://www.football-data.co.uk/englandm.php)**
    - Complete match results for all Premier League seasons (1992/93 - 2024/25)
    - Includes: Date, Home Team, Away Team, Full-Time Home Goals (FTHG), Full-Time Away Goals (FTAG), Result (FTR)
    - Data is downloaded as CSV files and stored locally in `data/raw/`
    
    **Live Season Data (2025/26)**
    - Current season data is manually updated periodically
    - Uses the same format as historical data for consistency
    """)
    
    st.markdown("---")
    
    # Gap Calculation
    st.markdown("### 🧮 How We Calculate the Gap")
    st.markdown("""
    The "gap to safety" represents how many points behind 17th place (the last safe position) a team is at any given moment:
    """)
    
    # Visual explanation
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("""
        #### Data Transformation Pipeline
        
        **Step 1: Match → Team Results**
        - Each match is split into two rows (home team, away team)
        - Points assigned: Win = 3, Draw = 1, Loss = 0
        - Track goals for (GF) and goals against (GA)
        
        **Step 2: Cumulative Standings**
        - Sort all results by season and date
        - Calculate running totals for each team:
          - Cumulative Points (CumPts)
          - Cumulative Goal Difference (CumGD = GF - GA)
        
        **Step 3: Daily League Tables**
        - For each date with matches, rank all teams
        - Ranking order: Points → Goal Difference → Goals For
        - Identify position 17th (safety line) through 20th
        """)
    
    with col2:
        st.markdown("""
        #### Gap Calculation
        
        **Gap to Safety Formula:**
        ```
        gap_to_17th = current_team_points - 17th_place_points
        ```
        
        **Interpretation:**
        - Negative gap = Team is in danger (below 17th)
        - Zero gap = Team is exactly on safety line (17th place)
        - Positive gap = Team is safe (above 17th)
        
        **Example:**
        - 17th place has 25 points
        - Your team has 18 points
        - Gap = 18 - 25 = **-7 points** (in danger!)
        
        **Games in Hand:**
        - We also calculate adjusted gaps accounting for fixture differences
        - Maximum potential points if games in hand were all won
        - Both "absolute" and "adjusted" gaps are tracked
        """)
    
    st.markdown("---")
    
    # Database Schema
    st.markdown("### 🗄️ Database Structure")
    st.markdown("""
    All data is stored in a SQLite database (`data/mind_the_gap.db`) with three core tables:
    """)
    
    with st.expander("📋 View Database Schema", expanded=False):
        st.markdown("""
        **Table 1: `raw_matches`**
        - Original match-level data (one row per match)
        - Columns: `season`, `date`, `home_team`, `away_team`, `home_goals`, `away_goals`, `result`
        
        **Table 2: `standings_snapshots`**
        - Daily league tables (enables point-in-time queries)
        - Columns: `season`, `date`, `team`, `position`, `played`, `points`, `goals_for`, `goals_against`, `goal_difference`
        - Unique constraint: `(season, date, team)`
        
        **Table 3: `relegation_gaps`**
        - Pre-calculated gaps for performance
        - Columns: `season`, `date`, `team`, `position`, `points`, `gap_to_17th`, `games_in_hand_adjusted`, `eventually_survived`
        - Unique constraint: `(season, date, team)`
        """)
    
    st.markdown("---")
    
    # Key Definitions
    st.markdown("### 📖 Key Definitions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        **Survived**
        - Team finished in positions 1-17
        - Remained in Premier League
        - "Eventually survived" = True in database
        """)
    
    with col2:
        st.markdown("""
        **Relegated**
        - Team finished in positions 18-20
        - Dropped to Championship
        - "Eventually survived" = False
        """)
    
    with col3:
        st.markdown("""
        **Maximum Gap**
        - The worst (most negative) gap a team faced during the season
        - Only meaningful for teams that survived
        - Shows how deep they were in danger
        """)
    
    st.markdown("---")
    
    # Visualization Notes
    st.markdown("### 📈 Visualization Notes")
    st.markdown("""
    **Comeback Trajectories:**
    - Each line represents one team's journey through a season
    - Only shows the team with the biggest successful escape from each season
    - Line opacity reflects severity: darker = bigger gap overcome
    - Red line = current season (Wolves 2025-26)
    
    **Gap Distribution:**
    - Histogram showing all maximum gaps overcome by survivors
    - Most teams only dip slightly below 17th (small gaps)
    - Large escapes (10+ points) are extremely rare
    
    **Danger Map:**
    - Shows all teams in all positions over time
    - Circle size = gap severity
    - Color indicates survival outcome
    """)
    
    st.markdown("---")
    
    # Historical Context
    st.markdown("### 🏆 Historical Records")
    st.info("""
    **Biggest Recorded Escape:** West Ham United 2006/07  
    - Overcame a 10-point deficit to survive
    - This stood as the Premier League record for biggest comeback
    
    **Wolves 2025/26:**
    - Currently facing a ~15-point deficit
    - If they survive, it would be an unprecedented achievement
    - No team has ever overcome this large of a gap in PL history
    """)
    
    st.markdown("---")
    
    # Technical Notes
    with st.expander("🔧 Technical Implementation Details", expanded=False):
        st.markdown("""
        **Tech Stack:**
        - Framework: Streamlit (interactive web app)
        - Data Processing: pandas (match-level → standings snapshots)
        - Database: SQLite (raw matches, standings, gaps)
        - Visualization: Plotly (interactive charts)
        - Environment: conda (`mind-the-gap` environment)
        
        **Critical Implementation Details:**
        - **Date Sensitivity:** Uses actual match dates, not just "matchweek" numbers
        - **Tiebreakers:** Ranks by Points → GD → GF → Alphabetical (official PL rules)
        - **Forward Fill:** Standings carried forward on non-match days for continuous time series
        - **Validation:** Final standings verified against official Premier League results
        
        **Repository:**
        - GitHub: [Mind the Gap](https://github.com/yourusername/mind-the-gap)
        - Project inspired by London Underground warning + points gap to safety
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: gray; font-size: 12px; margin-top: 20px;">
        Mind the Gap © 2025 | Data accuracy not guaranteed for betting purposes | 
        Historical data from Football-Data.co.uk
    </div>
    """, unsafe_allow_html=True)
