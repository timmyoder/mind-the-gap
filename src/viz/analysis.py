"""Analysis visualizations for relegation gap data."""

import sqlite3
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Optional


def get_survived_gaps_histogram(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None
) -> go.Figure:
    """Create histogram of maximum gaps overcome by teams that survived.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        
    Returns:
        Plotly Figure with histogram
    """
    # Query to get maximum gap for each team that survived
    # Database stores positive = danger, we'll negate for display
    query = """
    SELECT 
        season,
        team,
        MAX(gap_to_17th) as max_gap
    FROM relegation_gaps
    WHERE eventually_survived = 1
        AND gap_to_17th > 0
    """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("season <= ?")
        params.append(season_end)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += " GROUP BY season, team ORDER BY max_gap DESC"
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    
    # Database has positive=danger, so max_gap is already the gap overcome
    df['gap_overcome'] = df['max_gap']
    
    # Create histogram with better binning
    fig = go.Figure()
    
    # Use 1-point bins for better resolution
    fig.add_trace(go.Histogram(
        x=df['gap_overcome'],
        xbins=dict(start=0, end=df['gap_overcome'].max() + 1, size=1),
        marker=dict(
            color='#2E86AB',
            line=dict(color='white', width=1)
        ),
        hovertemplate='<b>Gap overcome: %{x} points</b><br>Teams: %{y}<extra></extra>'
    ))
    
    # Add summary statistics as annotations
    mean_gap = df['gap_overcome'].mean()
    median_gap = df['gap_overcome'].median()
    max_gap = df['gap_overcome'].max()
    
    fig.update_layout(
        title=dict(
            text=f"Distribution of Maximum Gaps Overcome by Survivors<br><sub>Total escapes: {len(df)} | Data is heavily skewed - most escapes are small gaps</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Maximum Gap Overcome (points behind 17th)",
        yaxis_title="Number of Teams",
        bargap=0.05,
        showlegend=False,
        hovermode='x',
        annotations=[
            dict(
                x=0.98, y=0.98,
                xref='paper', yref='paper',
                text=f"Mean: {mean_gap:.1f} pts<br>Median: {median_gap:.1f} pts<br>Max: {max_gap:.0f} pts",
                showarrow=False,
                bgcolor='rgba(255,255,255,0.8)',
                bordercolor='#2E86AB',
                borderwidth=2,
                font=dict(size=12),
                align='left',
                xanchor='right',
                yanchor='top'
            )
        ]
    )
    
    return fig


def get_biggest_escapes_by_season(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None,
    show_legend: bool = False
) -> go.Figure:
    """Create line plot showing biggest escape trajectory for each season.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        show_legend: Whether to display the legend (can be very large with many seasons)
        
    Returns:
        Plotly Figure with line plot
    """
    # First, find the team with biggest survived gap in each season
    # Database stores positive = danger
    max_gap_query = """
    SELECT 
        season,
        team,
        MAX(gap_to_17th) as max_gap
    FROM relegation_gaps
    WHERE eventually_survived = 1
        AND gap_to_17th > 0
    """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("season <= ?")
        params.append(season_end)
    
    if conditions:
        max_gap_query += " AND " + " AND ".join(conditions)
    
    max_gap_query += " GROUP BY season ORDER BY season"
    
    max_gaps = pd.read_sql_query(max_gap_query, conn, params=params if params else None)
    
    if len(max_gaps) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig
    
    # Calculate opacity based on max gap (normalize between min and max)
    min_gap = max_gaps['max_gap'].min()
    max_gap_overall = max_gaps['max_gap'].max()
    gap_range = max_gap_overall - min_gap if max_gap_overall > min_gap else 1
    
    # Now get the full trajectory for each of these teams
    fig = go.Figure()
    
    for _, row in max_gaps.iterrows():
        # Get gap history for this team
        trajectory_query = """
        SELECT 
            season,
            team,
            date,
            gap_to_17th,
            days_into_season
        FROM (
            SELECT 
                rg.season,
                rg.team,
                rg.date,
                rg.gap_to_17th,
                -- Calculate days into season
                CAST((JULIANDAY(rg.date) - JULIANDAY(
                    (SELECT MIN(date) FROM relegation_gaps WHERE season = rg.season)
                )) AS INTEGER) as days_into_season
            FROM relegation_gaps rg
            WHERE rg.season = ? AND rg.team = ?
            ORDER BY rg.date
        )
        """
        
        trajectory = pd.read_sql_query(
            trajectory_query, 
            conn, 
            params=(row['season'], row['team'])
        )
        
        if len(trajectory) == 0:
            continue
        
        # Negate gaps so negative = danger for display
        trajectory['gap_display'] = -trajectory['gap_to_17th']
        
        # Calculate opacity: bigger gaps = more opaque (darker)
        # Use exponential scaling (power of 5) for extremely dramatic difference
        # Small gaps (1-5 pts) will be nearly invisible, big gaps very dark
        normalized = (row['max_gap'] - min_gap) / gap_range
        opacity = 0.01 + 0.99 * (normalized ** 5)  # Exponential curve
        
        # Add line for this season - all black with varying opacity
        fig.add_trace(go.Scatter(
            x=trajectory['days_into_season'],
            y=trajectory['gap_display'],
            mode='lines',
            name=f"{row['season']}: {row['team']} ({row['max_gap']:.0f} pts)",
            hovertemplate=(
                f"<b>{row['season']}: {row['team']}</b><br>"
                f"Max gap: {row['max_gap']:.0f} points<br>"
                "Day %{x}<br>"
                "Gap: %{y} points<br>"
                "<extra></extra>"
            ),
            line=dict(
                color=f'rgba(0, 0, 0, {opacity})',
                width=2
            ),
            showlegend=True
        ))
    
    # Add current season Wolves trajectory in red (2025-26)
    # Try both 'Wolves' and 'Wolverhampton' as team names
    wolves_query = """
    SELECT 
        season,
        team,
        date,
        gap_to_17th,
        days_into_season
    FROM (
        SELECT 
            rg.season,
            rg.team,
            rg.date,
            rg.gap_to_17th,
            CAST((JULIANDAY(rg.date) - JULIANDAY(
                (SELECT MIN(date) FROM relegation_gaps WHERE season = rg.season)
            )) AS INTEGER) as days_into_season
        FROM relegation_gaps rg
        WHERE rg.season = '2025-26' 
            AND (rg.team LIKE '%Wolves%' OR rg.team LIKE '%Wolverhampton%')
        ORDER BY rg.date
    )
    """
    
    try:
        wolves_trajectory = pd.read_sql_query(wolves_query, conn)
        
        if len(wolves_trajectory) > 0:
            # Negate for display
            wolves_trajectory['gap_display'] = -wolves_trajectory['gap_to_17th']
            wolves_max_gap = abs(wolves_trajectory['gap_display'].min())
            wolves_team_name = wolves_trajectory['team'].iloc[0]
            
            # Add Wolves trajectory in red - add FIRST so it's on top
            fig.add_trace(go.Scatter(
                x=wolves_trajectory['days_into_season'],
                y=wolves_trajectory['gap_display'],
                mode='lines',
                name=f"2025-26: {wolves_team_name} ({wolves_max_gap:.0f} pts) ⚠️ CURRENT",
                hovertemplate=(
                    f"<b>2025-26: {wolves_team_name} (CURRENT SEASON)</b><br>"
                    f"Current worst gap: {wolves_max_gap:.0f} points<br>"
                    "Day %{x}<br>"
                    "Gap: %{y} points<br>"
                    "<extra></extra>"
                ),
                line=dict(
                    color='red',
                    width=4
                ),
                showlegend=True
            ))
    except Exception as e:
        # If no Wolves data or season doesn't exist, just skip
        print(f"Could not load Wolves data: {e}")
        pass
    
    # Add reference line at y=0 (safety) - add LAST so it's on top
    if len(max_gaps) > 0:
        fig.add_hline(
            y=0, 
            line_color="orange",
            line_width=2,
            annotation_text="Safety Line (17th place)",
            annotation_position="right"
        )
    
    fig.update_layout(
        title=dict(
            text=f"Biggest Escape Trajectory by Season<br><sub>Line darkness = severity of gap (darkest = {max_gap_overall:.0f} pts) | Click legend to isolate lines</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Days into Season",
        yaxis_title="Gap to 17th Place (points)",
        hovermode='closest',
        showlegend=show_legend,
        legend=dict(
            title="Season: Team (Max Gap)",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='gray',
            borderwidth=1
        ) if show_legend else None
    )
    
    return fig


def get_escape_summary_table(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None,
    top_n: int = 10
) -> pd.DataFrame:
    """Get top N biggest escapes with details.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        top_n: Number of top escapes to return
        
    Returns:
        DataFrame with escape details
    """
    query = """
    WITH max_gaps AS (
        SELECT 
            season,
            team,
            MAX(gap_to_17th) as max_gap,
            date as date_of_max_gap
        FROM relegation_gaps
        WHERE eventually_survived = 1
            AND gap_to_17th > 0
        """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("season <= ?")
        params.append(season_end)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += f"""
        GROUP BY season, team
    )
    SELECT * FROM max_gaps
    ORDER BY max_gap DESC
    LIMIT {top_n}
    """
    
    return pd.read_sql_query(query, conn, params=params if params else None)


def get_danger_map_scatter(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None
) -> go.Figure:
    """Create scatter plot of gap vs games remaining (Danger Map).
    
    Shows all historical positions colored by outcome (survived vs relegated).
    Helps identify which gap/time combinations are survivable.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        
    Returns:
        Plotly Figure with scatter plot
    """
    # Get all relegation gap data points with games remaining
    # Calculate games remaining from date (approximate based on days into season)
    query = """
    WITH season_info AS (
        SELECT 
            season,
            MIN(date) as season_start,
            MAX(date) as season_end,
            CASE 
                WHEN season LIKE '%-94' OR season LIKE '%-95' THEN 42
                ELSE 38
            END as total_games
        FROM relegation_gaps
        GROUP BY season
    )
    SELECT 
        rg.season,
        rg.team,
        rg.date,
        rg.gap_to_17th,
        rg.eventually_survived,
        CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER) as games_remaining
    FROM relegation_gaps rg
    JOIN season_info si ON rg.season = si.season
    WHERE rg.gap_to_17th > 0
    """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("rg.season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("rg.season <= ?")
        params.append(season_end)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    
    if len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig
    
    # Separate survived and relegated
    survived = df[df['eventually_survived'] == 1]
    relegated = df[df['eventually_survived'] == 0]
    
    fig = go.Figure()
    
    # Add relegated points (red)
    if len(relegated) > 0:
        fig.add_trace(go.Scatter(
            x=relegated['games_remaining'],
            y=relegated['gap_to_17th'],
            mode='markers',
            name='Relegated',
            marker=dict(
                color='rgba(239, 71, 111, 0.4)',
                size=6,
                line=dict(width=0.5, color='rgba(239, 71, 111, 0.8)')
            ),
            hovertemplate=(
                "<b>%{customdata[0]}: %{customdata[1]}</b><br>"
                "Gap: %{y} points<br>"
                "Games remaining: %{x}<br>"
                "Outcome: RELEGATED<br>"
                "<extra></extra>"
            ),
            customdata=relegated[['season', 'team']].values
        ))
    
    # Add survived points (green)
    if len(survived) > 0:
        fig.add_trace(go.Scatter(
            x=survived['games_remaining'],
            y=survived['gap_to_17th'],
            mode='markers',
            name='Survived',
            marker=dict(
                color='rgba(17, 138, 178, 0.4)',
                size=6,
                line=dict(width=0.5, color='rgba(17, 138, 178, 0.8)')
            ),
            hovertemplate=(
                "<b>%{customdata[0]}: %{customdata[1]}</b><br>"
                "Gap: %{y} points<br>"
                "Games remaining: %{x}<br>"
                "Outcome: SURVIVED<br>"
                "<extra></extra>"
            ),
            customdata=survived[['season', 'team']].values
        ))
    
    # Add markers for other great escapes (8+ points survived)
    great_escapes_query = """
    WITH season_info AS (
        SELECT 
            season,
            MIN(date) as season_start,
            MAX(date) as season_end,
            CASE 
                WHEN season LIKE '%-94' OR season LIKE '%-95' THEN 42
                ELSE 38
            END as total_games
        FROM relegation_gaps
        GROUP BY season
    ),
    max_gaps AS (
        SELECT 
            season,
            team,
            MAX(gap_to_17th) as max_gap
        FROM relegation_gaps
        WHERE eventually_survived = 1
            AND gap_to_17th >= 8
        GROUP BY season, team
    )
    SELECT DISTINCT
        rg.season,
        rg.team,
        rg.gap_to_17th,
        CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER) as games_remaining,
        mg.max_gap
    FROM relegation_gaps rg
    JOIN season_info si ON rg.season = si.season
    JOIN max_gaps mg ON rg.season = mg.season AND rg.team = mg.team
    WHERE rg.gap_to_17th = mg.max_gap
    ORDER BY mg.max_gap DESC
    LIMIT 10
    """
    
    try:
        great_escapes_df = pd.read_sql_query(great_escapes_query, conn)
        if len(great_escapes_df) > 0:
            fig.add_trace(go.Scatter(
                x=great_escapes_df['games_remaining'],
                y=great_escapes_df['gap_to_17th'],
                mode='markers',
                name='Great Escapes (8+ pts)',
                marker=dict(
                    color='gold',
                    size=12,
                    symbol='square',
                    line=dict(width=2, color='darkorange')
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}: %{customdata[1]}</b><br>"
                    "Max gap overcome: %{y:.0f} points<br>"
                    "Games remaining: %{x}<br>"
                    "Outcome: SURVIVED<br>"
                    "<extra></extra>"
                ),
                customdata=great_escapes_df[['season', 'team']].values
            ))
    except Exception as e:
        print(f"Could not load great escapes: {e}")
    
    # Add Wolves current position if in date range
    # Count actual matches from raw_matches table
    wolves_query = """
    WITH wolves_matches AS (
        SELECT COUNT(*) as matches_played
        FROM raw_matches
        WHERE season = '2025-26'
            AND (home_team LIKE '%Wolves%' OR home_team LIKE '%Wolverhampton%'
                 OR away_team LIKE '%Wolves%' OR away_team LIKE '%Wolverhampton%')
    ),
    wolves_latest AS (
        SELECT 
            rg.season,
            rg.team,
            rg.date,
            rg.gap_to_17th
        FROM relegation_gaps rg
        WHERE rg.season = '2025-26'
            AND (rg.team LIKE '%Wolves%' OR rg.team LIKE '%Wolverhampton%')
        ORDER BY rg.date DESC
        LIMIT 1
    )
    SELECT 
        wl.season,
        wl.team,
        wl.date,
        wl.gap_to_17th,
        38 - wm.matches_played as games_remaining
    FROM wolves_latest wl, wolves_matches wm
    """
    
    try:
        wolves_df = pd.read_sql_query(wolves_query, conn)
        if len(wolves_df) > 0:
            fig.add_trace(go.Scatter(
                x=wolves_df['games_remaining'],
                y=wolves_df['gap_to_17th'],
                mode='markers',
                name=f"2025-26 {wolves_df['team'].iloc[0]} (CURRENT)",
                marker=dict(
                    color='red',
                    size=15,
                    symbol='star',
                    line=dict(width=2, color='darkred')
                ),
                hovertemplate=(
                    f"<b>CURRENT: {wolves_df['team'].iloc[0]}</b><br>"
                    f"Gap: {wolves_df['gap_to_17th'].iloc[0]:.0f} points<br>"
                    f"Games remaining: {wolves_df['games_remaining'].iloc[0]}<br>"
                    "<extra></extra>"
                )
            ))
    except:
        pass
    
    fig.update_layout(
        title=dict(
            text="The Danger Map: Gap vs Games Remaining<br><sub>Can Wolves survive from their position? Has anyone done it before?</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Games Remaining in Season",
        yaxis_title="Gap to 17th Place (points)",
        hovermode='closest',
        xaxis=dict(autorange='reversed'),  # More games = earlier in season = left side
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5
        )
    )
    
    return fig


def get_survival_probability_heatmap(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None
) -> go.Figure:
    """Create heatmap showing survival probability by gap and games remaining.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        
    Returns:
        Plotly Figure with heatmap
    """
    # Get all data points - calculate games remaining from dates
    query = """
    WITH season_info AS (
        SELECT 
            season,
            MIN(date) as season_start,
            MAX(date) as season_end,
            CASE 
                WHEN season LIKE '%-94' OR season LIKE '%-95' THEN 42
                ELSE 38
            END as total_games
        FROM relegation_gaps
        GROUP BY season
    )
    SELECT 
        rg.gap_to_17th,
        rg.eventually_survived,
        CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER) as games_remaining
    FROM relegation_gaps rg
    JOIN season_info si ON rg.season = si.season
    WHERE rg.gap_to_17th > 0
    """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("rg.season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("rg.season <= ?")
        params.append(season_end)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    
    if len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig
    
    # Create bins for games remaining and gap
    df['games_bin'] = pd.cut(df['games_remaining'], bins=range(0, 40, 2), labels=range(1, 39, 2))
    df['gap_bin'] = pd.cut(df['gap_to_17th'], bins=range(0, int(df['gap_to_17th'].max()) + 2), 
                           labels=range(1, int(df['gap_to_17th'].max()) + 2))
    
    # Calculate survival rate for each bin
    survival_rate = df.groupby(['games_bin', 'gap_bin'], observed=True)['eventually_survived'].agg(['mean', 'count']).reset_index()
    survival_rate = survival_rate[survival_rate['count'] >= 3]  # Filter bins with too few samples
    
    # Pivot for heatmap
    heatmap_data = survival_rate.pivot(index='gap_bin', columns='games_bin', values='mean')
    
    # Get Wolves current position for overlay
    wolves_position = None
    try:
        wolves_query = """
        WITH wolves_matches AS (
            SELECT COUNT(*) as matches_played
            FROM raw_matches
            WHERE season = '2025-26'
                AND (home_team LIKE '%Wolves%' OR home_team LIKE '%Wolverhampton%'
                     OR away_team LIKE '%Wolves%' OR away_team LIKE '%Wolverhampton%')
        ),
        wolves_latest AS (
            SELECT 
                rg.gap_to_17th,
                38 - wm.matches_played as games_remaining
            FROM relegation_gaps rg, wolves_matches wm
            WHERE rg.season = '2025-26'
                AND (rg.team LIKE '%Wolves%' OR rg.team LIKE '%Wolverhampton%')
            ORDER BY rg.date DESC
            LIMIT 1
        )
        SELECT * FROM wolves_latest
        """
        wolves_df = pd.read_sql_query(wolves_query, conn)
        if len(wolves_df) > 0:
            wolves_position = {
                'gap': wolves_df['gap_to_17th'].iloc[0],
                'games_remaining': wolves_df['games_remaining'].iloc[0]
            }
    except:
        pass
    
    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values * 100,  # Convert to percentage
        x=heatmap_data.columns.astype(int),
        y=heatmap_data.index.astype(int),
        colorscale='RdYlGn',
        text=[[f'{val:.0f}%' if not pd.isna(val) else '' for val in row] for row in heatmap_data.values * 100],
        texttemplate='%{text}',
        textfont={"size": 10},
        colorbar=dict(title="Survival<br>Rate (%)"),
        hovertemplate=(
            "Games remaining: ~%{x}<br>"
            "Gap: ~%{y} points<br>"
            "Survival rate: %{z:.1f}%<br>"
            "<extra></extra>"
        )
    ))
    
    layout_kwargs = {
        'title': dict(
            text="Survival Probability Heatmap<br><sub>What % of teams survived from each position?</sub>",
            x=0.5,
            xanchor='center'
        ),
        'xaxis_title': "Games Remaining (binned)",
        'yaxis_title': "Gap to 17th Place (points)",
        'xaxis': dict(autorange='reversed')
    }
    
    # Add Wolves marker if available
    if wolves_position:
        # Approximate bin for Wolves position
        wolves_games_bin = wolves_position['games_remaining'] - (wolves_position['games_remaining'] % 2) + 1
        wolves_gap_bin = wolves_position['gap']
        
        layout_kwargs['annotations'] = [{
            'x': wolves_games_bin,
            'y': wolves_gap_bin,
            'text': '⭐<br>Wolves',
            'showarrow': True,
            'arrowhead': 2,
            'arrowsize': 1,
            'arrowwidth': 2,
            'arrowcolor': 'red',
            'ax': 40,
            'ay': -40,
            'font': dict(size=14, color='red', family='Arial Black'),
            'bgcolor': 'rgba(255,255,255,0.8)',
            'bordercolor': 'red',
            'borderwidth': 2
        }]
    
    fig.update_layout(**layout_kwargs)
    
    return fig


def get_ppg_survival_heatmap(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None
) -> go.Figure:
    """Create heatmap showing survival probability by required PPG and games remaining.
    
    Similar to survival_probability_heatmap but from a PPG perspective instead of gap.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        
    Returns:
        Plotly Figure with heatmap
    """
    # Get all data points with PPG calculations
    query = """
    WITH season_info AS (
        SELECT 
            season,
            MIN(date) as season_start,
            MAX(date) as season_end,
            CASE 
                WHEN season LIKE '%-94' OR season LIKE '%-95' THEN 42
                ELSE 38
            END as total_games
        FROM relegation_gaps
        GROUP BY season
    )
    SELECT 
        rg.eventually_survived,
        CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER) as games_remaining,
        CAST(rg.gap_to_17th AS FLOAT) / 
        NULLIF(CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER), 0) as required_ppg
    FROM relegation_gaps rg
    JOIN season_info si ON rg.season = si.season
    WHERE rg.gap_to_17th > 0
        AND JULIANDAY(rg.date) > JULIANDAY(si.season_start)
    """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("rg.season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("rg.season <= ?")
        params.append(season_end)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    
    if len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig
    
    # Filter reasonable PPG values
    df = df[df['required_ppg'] <= 3.0]
    
    # Create bins for PPG only (every 0.25)
    df['ppg_bin'] = pd.cut(df['required_ppg'], 
                           bins=[0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0], 
                           labels=['0-0.25', '0.25-0.5', '0.5-0.75', '0.75-1.0', '1.0-1.25', '1.25-1.5', 
                                   '1.5-1.75', '1.75-2.0', '2.0-2.25', '2.25-2.5', '2.5-2.75', '2.75-3.0'])
    
    # Calculate survival rate for each PPG bin
    survival_by_ppg = df.groupby('ppg_bin', observed=True)['eventually_survived'].agg(['mean', 'count']).reset_index()
    survival_by_ppg = survival_by_ppg[survival_by_ppg['count'] >= 5]  # Filter bins with too few samples
    
    # Convert to percentage
    survival_by_ppg['survival_pct'] = survival_by_ppg['mean'] * 100
    
    # Get Wolves current position
    wolves_ppg = None
    wolves_survival_rate = None
    try:
        wolves_query = """
        WITH wolves_matches AS (
            SELECT COUNT(*) as matches_played
            FROM raw_matches
            WHERE season = '2025-26'
                AND (home_team LIKE '%Wolves%' OR home_team LIKE '%Wolverhampton%'
                     OR away_team LIKE '%Wolves%' OR away_team LIKE '%Wolverhampton%')
        ),
        wolves_latest AS (
            SELECT 
                rg.gap_to_17th,
                38 - wm.matches_played as games_remaining,
                CAST(rg.gap_to_17th AS FLOAT) / NULLIF(38 - wm.matches_played, 0) as required_ppg
            FROM relegation_gaps rg, wolves_matches wm
            WHERE rg.season = '2025-26'
                AND (rg.team LIKE '%Wolves%' OR rg.team LIKE '%Wolverhampton%')
            ORDER BY rg.date DESC
            LIMIT 1
        )
        SELECT * FROM wolves_latest
        """
        wolves_df = pd.read_sql_query(wolves_query, conn)
        if len(wolves_df) > 0 and wolves_df['required_ppg'].iloc[0] <= 3.0:
            wolves_ppg = wolves_df['required_ppg'].iloc[0]
            # Find which bin Wolves falls into and get that survival rate
            for _, row in survival_by_ppg.iterrows():
                bin_label = str(row['ppg_bin'])
                bin_min, bin_max = map(float, bin_label.split('-'))
                if bin_min <= wolves_ppg < bin_max:
                    wolves_survival_rate = row['survival_pct']
                    break
    except:
        pass
    
    # Create bar chart
    colors = ['red' if pct < 30 else 'orange' if pct < 60 else 'green' 
              for pct in survival_by_ppg['survival_pct']]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=survival_by_ppg['ppg_bin'].astype(str),
        y=survival_by_ppg['survival_pct'],
        marker=dict(color=colors, line=dict(color='white', width=1)),
        text=[f"{pct:.0f}%<br>({count} teams)" for pct, count in zip(survival_by_ppg['survival_pct'], survival_by_ppg['count'])],
        textposition='outside',
        hovertemplate=(
            "Required PPG: %{x}<br>"
            "Survival rate: %{y:.1f}%<br>"
            "Sample size: %{customdata}<br>"
            "<extra></extra>"
        ),
        customdata=survival_by_ppg['count'],
        showlegend=False
    ))
    
    # Add annotation for Wolves
    annotations = []
    if wolves_ppg is not None and wolves_survival_rate is not None:
        # Find the x position (which bar)
        x_pos = None
        for idx, row in survival_by_ppg.iterrows():
            bin_label = str(row['ppg_bin'])
            bin_min, bin_max = map(float, bin_label.split('-'))
            if bin_min <= wolves_ppg < bin_max:
                x_pos = bin_label
                break
        
        if x_pos is not None:
            # Find the max bar height to position text above all bars
            max_bar_height = survival_by_ppg['survival_pct'].max()
            text_y_position = max(65, max_bar_height + 10)  # At least 65% or above tallest bar
            
            annotations.append({
                'x': x_pos,
                'y': wolves_survival_rate,  # Point to top of Wolves' bar
                'text': f'⭐ Wolves<br>needs {wolves_ppg:.2f} PPG',
                'showarrow': True,
                'arrowhead': 2,
                'arrowsize': 1,
                'arrowwidth': 2,
                'arrowcolor': 'red',
                'ax': 80,  # Move 80 pixels to the right
                'ay': -80,  # Move 80 pixels up (45-degree angle)
                'font': dict(size=12, color='red', family='Arial Black'),
                'bgcolor': 'rgba(255,255,255,0.9)',
                'bordercolor': 'red',
                'borderwidth': 2
            })
    
    fig.update_layout(
        title=dict(
            text="Survival Probability by Required PPG<br><sub>What % of teams survived needing each form level?</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Required Points Per Game",
        yaxis_title="Survival Rate (%)",
        yaxis=dict(range=[0, 105]),
        showlegend=False,
        annotations=annotations
    )
    
    return fig


def get_points_per_game_required(
    conn: sqlite3.Connection,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None
) -> go.Figure:
    """Show required points-per-game rate to reach safety from various positions.
    
    Args:
        conn: SQLite database connection
        season_start: Optional season filter
        season_end: Optional season filter
        
    Returns:
        Plotly Figure with scatter plot
    """
    # Get positions with gap, games remaining, and calculate required PPG
    # Calculate games remaining from dates
    query = """
    WITH season_info AS (
        SELECT 
            season,
            MIN(date) as season_start,
            MAX(date) as season_end,
            CASE 
                WHEN season LIKE '%-94' OR season LIKE '%-95' THEN 42
                ELSE 38
            END as total_games
        FROM relegation_gaps
        GROUP BY season
    )
    SELECT 
        rg.season,
        rg.team,
        rg.gap_to_17th,
        rg.eventually_survived,
        CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER) as games_remaining,
        CAST(rg.gap_to_17th AS FLOAT) / 
        NULLIF(CAST(
            si.total_games * (1.0 - 
                (JULIANDAY(rg.date) - JULIANDAY(si.season_start)) / 
                (JULIANDAY(si.season_end) - JULIANDAY(si.season_start))
            )
        AS INTEGER), 0) as required_ppg
    FROM relegation_gaps rg
    JOIN season_info si ON rg.season = si.season
    WHERE rg.gap_to_17th > 0
        AND JULIANDAY(rg.date) > JULIANDAY(si.season_start)
    """
    
    params = []
    conditions = []
    
    if season_start:
        conditions.append("rg.season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("rg.season <= ?")
        params.append(season_end)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    
    if len(df) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data available for selected filters",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=20)
        )
        return fig
    
    # Filter reasonable values (can't require > 3 PPG)
    df = df[df['required_ppg'] <= 3]
    
    survived = df[df['eventually_survived'] == 1]
    relegated = df[df['eventually_survived'] == 0]
    
    fig = go.Figure()
    
    # Add relegated teams
    if len(relegated) > 0:
        fig.add_trace(go.Scatter(
            x=relegated['games_remaining'],
            y=relegated['required_ppg'],
            mode='markers',
            name='Relegated',
            marker=dict(
                color='rgba(239, 71, 111, 0.3)',
                size=5
            ),
            hovertemplate=(
                "<b>%{customdata[0]}: %{customdata[1]}</b><br>"
                "Required PPG: %{y:.2f}<br>"
                "Games remaining: %{x}<br>"
                "Gap: %{customdata[2]:.0f} points<br>"
                "Outcome: RELEGATED<br>"
                "<extra></extra>"
            ),
            customdata=relegated[['season', 'team', 'gap_to_17th']].values
        ))
    
    # Add survived teams
    if len(survived) > 0:
        fig.add_trace(go.Scatter(
            x=survived['games_remaining'],
            y=survived['required_ppg'],
            mode='markers',
            name='Survived',
            marker=dict(
                color='rgba(17, 138, 178, 0.3)',
                size=5
            ),
            hovertemplate=(
                "<b>%{customdata[0]}: %{customdata[1]}</b><br>"
                "Required PPG: %{y:.2f}<br>"
                "Games remaining: %{x}<br>"
                "Gap: %{customdata[2]:.0f} points<br>"
                "Outcome: SURVIVED<br>"
                "<extra></extra>"
            ),
            customdata=survived[['season', 'team', 'gap_to_17th']].values
        ))
    
    # Add reference lines for common PPG rates
    max_games = df['games_remaining'].max()
    fig.add_hline(y=1.0, line_dash="dash", line_color="gray", opacity=0.5,
                  annotation_text="1.0 PPG (draw every game)", annotation_position="right")
    fig.add_hline(y=1.5, line_dash="dash", line_color="orange", opacity=0.5,
                  annotation_text="1.5 PPG (good form)", annotation_position="right")
    fig.add_hline(y=2.0, line_dash="dash", line_color="red", opacity=0.5,
                  annotation_text="2.0 PPG (title-winning form)", annotation_position="right")
    
    # Add Wolves current position
    wolves_query = """
    WITH wolves_matches AS (
        SELECT COUNT(*) as matches_played
        FROM raw_matches
        WHERE season = '2025-26'
            AND (home_team LIKE '%Wolves%' OR home_team LIKE '%Wolverhampton%'
                 OR away_team LIKE '%Wolves%' OR away_team LIKE '%Wolverhampton%')
    )
    SELECT 
        rg.season,
        rg.team,
        rg.gap_to_17th,
        38 - wm.matches_played as games_remaining,
        CAST(rg.gap_to_17th AS FLOAT) / NULLIF(38 - wm.matches_played, 0) as required_ppg
    FROM relegation_gaps rg, wolves_matches wm
    WHERE rg.season = '2025-26'
        AND (rg.team LIKE '%Wolves%' OR rg.team LIKE '%Wolverhampton%')
    ORDER BY rg.date DESC
    LIMIT 1
    """
    
    try:
        wolves_df = pd.read_sql_query(wolves_query, conn)
        if len(wolves_df) > 0:
            fig.add_trace(go.Scatter(
                x=wolves_df['games_remaining'],
                y=wolves_df['required_ppg'],
                mode='markers',
                name=f"Wolves 2025-26",
                marker=dict(
                    color='red',
                    size=20,
                    symbol='star',
                    line=dict(width=2, color='darkred')
                ),
                hovertemplate=(
                    f"<b>Wolves 2025-26</b><br>"
                    f"Required PPG: {wolves_df['required_ppg'].iloc[0]:.2f}<br>"
                    f"Games remaining: {wolves_df['games_remaining'].iloc[0]}<br>"
                    f"Gap: {wolves_df['gap_to_17th'].iloc[0]:.0f} points<br>"
                    "<extra></extra>"
                )
            ))
    except Exception as e:
        pass
    
    fig.update_layout(
        title=dict(
            text="Required Points Per Game to Reach Safety<br><sub>What form is needed to survive?</sub>",
            x=0.5,
            xanchor='center'
        ),
        xaxis_title="Games Remaining",
        yaxis_title="Required Points Per Game",
        xaxis=dict(autorange='reversed'),
        yaxis=dict(range=[0, 3]),
        showlegend=True
    )
    
    return fig
