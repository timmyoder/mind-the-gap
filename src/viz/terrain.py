"""3D terrain visualization for relegation gaps across all Premier League seasons."""

import sqlite3
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from typing import Tuple, List, Optional


def load_terrain_data(
    conn: sqlite3.Connection,
    danger_only: bool = False,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None
) -> pd.DataFrame:
    """Load and prepare data for 3D terrain visualization.
    
    Args:
        conn: SQLite database connection
        danger_only: If True, only include teams with gap > 0 at some point
        season_start: Optional start season filter (e.g., "2000-01")
        season_end: Optional end season filter (e.g., "2024-25")
        
    Returns:
        DataFrame with columns: season, date, team, position, gap, final_position
    """
    # Base query: get all standings and calculate gaps
    query = """
    WITH final_standings AS (
        -- Get each team's final position for the season
        SELECT 
            season,
            team,
            MAX(date) as final_date,
            position as final_position
        FROM standings_snapshots
        GROUP BY season, team
    ),
    safety_line AS (
        -- Get 17th place points for each date
        SELECT 
            season,
            date,
            points as safety_points
        FROM standings_snapshots
        WHERE position = 17
    ),
    all_gaps AS (
        -- Calculate gap for every team on every date
        SELECT 
            s.season,
            s.date,
            s.team,
            s.position,
            s.points,
            COALESCE(s.points - sl.safety_points, 0) as gap_to_17th,
            fs.final_position
        FROM standings_snapshots s
        LEFT JOIN safety_line sl ON s.season = sl.season AND s.date = sl.date
        LEFT JOIN final_standings fs ON s.season = fs.season AND s.team = fs.team
    )
    """
    
    # Add filters based on parameters
    conditions = []
    params = []
    
    if season_start:
        conditions.append("season >= ?")
        params.append(season_start)
    
    if season_end:
        conditions.append("season <= ?")
        params.append(season_end)
    
    if danger_only:
        # Only include teams that had gap < 0 at some point (negative = danger)
        query += """
        , team_max_gaps AS (
            SELECT season, team, MIN(gap_to_17th) as min_gap
            FROM all_gaps
            GROUP BY season, team
            HAVING min_gap < 0
        )
        SELECT ag.*
        FROM all_gaps ag
        INNER JOIN team_max_gaps tmg ON ag.season = tmg.season AND ag.team = tmg.team
        """
        if conditions:
            # Prefix column names with ag. for the joined query
            prefixed_conditions = [c.replace("season", "ag.season") for c in conditions]
            query += " WHERE " + " AND ".join(prefixed_conditions)
    else:
        query += "SELECT * FROM all_gaps"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY ag.season, ag.final_position, ag.date" if danger_only else " ORDER BY season, final_position, date"
    
    df = pd.read_sql_query(query, conn, params=params if params else None)
    
    # Convert date to datetime for better handling
    df['date'] = pd.to_datetime(df['date'])
    
    # Normalize dates within each season to day-of-season
    # Get the earliest date for each season
    season_starts = df.groupby('season')['date'].min().to_dict()
    df['days_into_season'] = df.apply(
        lambda row: (row['date'] - season_starts[row['season']]).days,
        axis=1
    )
    
    return df


def prepare_surface_data(df: pd.DataFrame, sort_by: str = 'season') -> Tuple[np.ndarray, List[str], List[int], np.ndarray]:
    """Convert DataFrame to 3D surface grid format.
    
    Args:
        df: DataFrame from load_terrain_data
        sort_by: How to order teams on X-axis. 'season' (default) groups by season,
                 'position' groups by final position across all seasons
        
    Returns:
        Tuple of (z_matrix, x_labels, y_labels, date_grid):
        - z_matrix: (n_days × n_team_seasons) array of gap values
        - x_labels: List of "Season: Team" labels for X-axis
        - y_labels: List of day numbers for Y-axis
        - date_grid: Corresponding dates for hover info
    """
    # Create unique season-team combinations with flexible sorting
    if sort_by == 'position':
        # Group by position first, then season (all 1st place, then all 2nd, etc.)
        sort_columns = ['final_position', 'season']
    else:
        # Group by season first, then position (default)
        sort_columns = ['season', 'final_position']
    
    season_teams = (
        df[['season', 'team', 'final_position']]
        .drop_duplicates()
        .sort_values(sort_columns)
        .reset_index(drop=True)
    )
    
    # Create X-axis labels
    x_labels = [
        f"{row['season']}: {row['team']}" 
        for _, row in season_teams.iterrows()
    ]
    
    # Create a regular grid of days (0 to max, every day)
    max_day = int(df['days_into_season'].max())
    all_days = list(range(0, max_day + 1))
    y_labels = all_days
    
    # Initialize Z matrix with NaN (will handle missing data)
    z_matrix = np.full((len(all_days), len(season_teams)), np.nan)
    date_grid = np.empty((len(all_days), len(season_teams)), dtype='datetime64[ns]')
    
    # Fill in the matrix with forward-fill for missing days
    for idx, (_, st) in enumerate(season_teams.iterrows()):
        # Get data for this team-season
        season_team_data = df[
            (df['season'] == st['season']) & 
            (df['team'] == st['team'])
        ].sort_values('days_into_season')
        
        if len(season_team_data) == 0:
            continue
            
        # Create a series indexed by days_into_season
        gap_series = season_team_data.set_index('days_into_season')['gap_to_17th']
        date_series = season_team_data.set_index('days_into_season')['date']
        
        # Get min/max days for this team (they don't play every day)
        min_day = int(season_team_data['days_into_season'].min())
        max_day_team = int(season_team_data['days_into_season'].max())
        
        # Fill in the matrix for days where this team exists
        for day in range(min_day, max_day_team + 1):
            day_idx = day  # Since all_days starts at 0
            
            if day in gap_series.index:
                # We have actual data for this day
                z_matrix[day_idx, idx] = gap_series.loc[day]
                date_grid[day_idx, idx] = date_series.loc[day]
            else:
                # Forward-fill from the most recent match day
                previous_days = gap_series.index[gap_series.index < day]
                if len(previous_days) > 0:
                    last_known_day = previous_days.max()
                    z_matrix[day_idx, idx] = gap_series.loc[last_known_day]
                    date_grid[day_idx, idx] = date_series.loc[last_known_day]
    
    return z_matrix, x_labels, y_labels, date_grid


def create_terrain_figure(
    z_matrix: np.ndarray,
    x_labels: List[str],
    y_labels: List[int],
    date_grid: np.ndarray,
    title: str = "Premier League Relegation Terrain"
) -> go.Figure:
    """Create interactive 3D surface plot of relegation gaps.
    
    Args:
        z_matrix: Gap values grid (days × teams)
        x_labels: Team-season labels
        y_labels: Day-of-season labels
        date_grid: Corresponding dates for hover
        title: Figure title
        
    Returns:
        Plotly Figure object
    """
    # Create hover text with detailed info
    hover_text = np.empty_like(z_matrix, dtype=object)
    for i in range(z_matrix.shape[0]):
        for j in range(z_matrix.shape[1]):
            if not np.isnan(z_matrix[i, j]):
                gap = z_matrix[i, j]
                status = "SAFE" if gap >= 0 else "DANGER"
                actual_date = pd.Timestamp(date_grid[i, j]).strftime('%Y-%m-%d') if not pd.isna(date_grid[i, j]) else 'N/A'
                hover_text[i, j] = (
                    f"<b>{x_labels[j]}</b><br>"
                    f"Day {y_labels[i]} of season<br>"
                    f"Date: {actual_date}<br>"
                    f"Gap: {gap:+.0f} points<br>"
                    f"Status: {status}"
                )
            else:
                hover_text[i, j] = "No data"
    
    # Create the 3D surface
    # z_matrix is (n_days, n_teams) where rows=days, cols=teams
    # For Plotly: z[i,j] corresponds to point (x[j], y[i])
    # We want X=teams, Y=days, so no transpose needed!
    surface = go.Surface(
        z=z_matrix,  # Shape: (days, teams) - correct for X=teams, Y=days
        x=list(range(len(x_labels))),  # Team indices
        y=y_labels,  # Day numbers
        colorscale=[
            [0.0, '#d73027'],   # Deep red (deep danger/very negative)
            [0.3, '#fc8d59'],   # Orange
            [0.5, '#fee090'],   # Yellow (near zero/safety line)
            [0.7, '#91cf60'],   # Light green
            [1.0, '#1a9850']    # Deep green (very safe/very positive)
        ],
        colorbar=dict(
            title=dict(
                text="Gap to Safety (points)",
                side="right"
            ),
            tickmode="linear",
            tick0=-30,
            dtick=10
        ),
        hovertext=hover_text,  # Also no transpose needed
        hoverinfo='text',
        showscale=True
    )
    
    fig = go.Figure(data=[surface])
    
    # Update layout for better viewing
    fig.update_layout(
        title={
            'text': title,
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20}
        },
        scene=dict(
            xaxis=dict(
                title="Teams by Season (ordered by final position)",
                tickmode='array',
                tickvals=list(range(0, len(x_labels), max(1, len(x_labels) // 20))),
                ticktext=[x_labels[i] for i in range(0, len(x_labels), max(1, len(x_labels) // 20))],
                tickangle=-45
            ),
            yaxis=dict(
                title="Days into Season",
                tickmode='array',
                tickvals=list(range(0, len(y_labels), max(1, len(y_labels) // 10))),
                ticktext=[f"Day {y_labels[i]}" for i in range(0, len(y_labels), max(1, len(y_labels) // 10))]
            ),
            zaxis=dict(
                title="Gap to 17th Place (points)",
                gridcolor='lightgray'
            ),
            camera=dict(
                eye=dict(x=1.5, y=1.5, z=1.3),
                center=dict(x=0, y=0, z=-0.1)
            ),
            aspectmode='manual',
            aspectratio=dict(x=2, y=1, z=0.5)
        ),
        height=800,
        margin=dict(l=0, r=0, b=0, t=50)
    )
    
    return fig


def get_available_seasons(conn: sqlite3.Connection) -> List[str]:
    """Get list of all seasons in the database.
    
    Args:
        conn: SQLite database connection
        
    Returns:
        Sorted list of season strings
    """
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT season FROM standings_snapshots ORDER BY season")
    return [row[0] for row in cursor.fetchall()]


def build_terrain_visualization(
    db_path: str,
    danger_only: bool = False,
    season_start: Optional[str] = None,
    season_end: Optional[str] = None,
    sort_by: str = 'season'
) -> go.Figure:
    """Main function to build complete terrain visualization.
    
    Args:
        db_path: Path to SQLite database
        danger_only: Only show teams in danger at some point
        season_start: Optional season filter start
        season_end: Optional season filter end
        sort_by: Team ordering - 'season' or 'position'
        
    Returns:
        Plotly Figure ready to display
    """
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    try:
        # Load data
        df = load_terrain_data(conn, danger_only, season_start, season_end)
        
        if df.empty:
            # Return empty figure with message
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for selected filters",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=20)
            )
            return fig
        
        # Prepare surface data
        z_matrix, x_labels, y_labels, date_grid = prepare_surface_data(df, sort_by=sort_by)
        
        # Create figure
        title_parts = ["Premier League Relegation Terrain"]
        if danger_only:
            title_parts.append("(Danger Zone Only)")
        if season_start or season_end:
            season_range = f"{season_start or 'Start'} to {season_end or 'End'}"
            title_parts.append(f"({season_range})")
        
        title = " ".join(title_parts)
        fig = create_terrain_figure(z_matrix, x_labels, y_labels, date_grid, title)
        
        return fig
        
    finally:
        conn.close()
