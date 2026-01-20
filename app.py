"""Streamlit app for Mind the Gap: Premier League Relegation Analysis."""

import streamlit as st
import sqlite3
from pathlib import Path
from src.viz.terrain import get_available_seasons

# Import tab modules
from src.viz.tabs.trends_tab import render_trends_tab
from src.viz.tabs.analysis_tab import render_analysis_tab
from src.viz.tabs.terrain_tab import render_terrain_tab
from src.viz.tabs.danger_map_tab import render_danger_map_tab
from src.viz.tabs.heatmap_tab import render_heatmap_tab
from src.viz.tabs.ppg_tab import render_ppg_tab
from src.viz.tabs.methodology_tab import render_methodology_tab


# ============================================================================
# TAB CONFIGURATION
# ============================================================================
# Enable/disable tabs by setting their 'enabled' value to True/False
# To hide a tab, set enabled=False (code remains but tab won't appear)

TAB_CONFIG = {
    'trends': {
        'enabled': True,
        'icon': '📈',
        'title': 'Comeback Trajectories',
        'render_func': render_trends_tab
    },
    'analysis': {
        'enabled': True,
        'icon': '📊',
        'title': 'Gap Distribution',
        'render_func': render_analysis_tab
    },
    'terrain': {
        'enabled': False,  # Disabled: slow to generate, too complex to interpret
        'icon': '🗻',
        'title': '3D Terrain',
        'render_func': render_terrain_tab,
        'needs_indices': True  # Special flag for tabs needing season indices
    },
    'danger_map': {
        'enabled': True,
        'icon': '🎯',
        'title': 'Danger Map',
        'render_func': render_danger_map_tab
    },
    'heatmap': {
        'enabled': True,
        'icon': '🔥',
        'title': 'Survival Heatmap',
        'render_func': render_heatmap_tab
    },
    'ppg': {
        'enabled': True,
        'icon': '⚡',
        'title': 'Required PPG',
        'render_func': render_ppg_tab
    },
    'methodology': {
        'enabled': True,
        'icon': '📚',
        'title': 'Methodology',
        'render_func': render_methodology_tab
    }
}

# ============================================================================


# Page configuration
st.set_page_config(
    page_title="Mind the Gap - EPL Relegation Analysis",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Database path
DB_PATH = "data/mind_the_gap.db"

# Check if database exists
if not Path(DB_PATH).exists():
    st.error(f"Database not found at {DB_PATH}. Please run the data pipeline first.")
    st.stop()


def main():
    """Main Streamlit application."""
    
    # Title and description
    st.title("⚽ Mind the Gap: Premier League Relegation Analysis")
    st.markdown("""
    Explore the history of Premier League relegation battles. Track comeback trajectories, 
    analyze survival patterns, and see if Wolves can achieve the unprecedented.
    """)
    
    # Sidebar controls
    st.sidebar.header("Data Controls")
    
    # Get available seasons
    conn = sqlite3.connect(DB_PATH)
    try:
        seasons = get_available_seasons(conn)
    finally:
        conn.close()
    
    if not seasons:
        st.error("No data found in database.")
        st.stop()
    
    # Season range selector
    st.sidebar.subheader("Season Range")
    col1, col2 = st.sidebar.columns(2)
    
    with col1:
        season_start_idx = st.selectbox(
            "From",
            range(len(seasons)),
            index=0,
            format_func=lambda x: seasons[x],
            key="start"
        )
    
    with col2:
        season_end_idx = st.selectbox(
            "To",
            range(len(seasons)),
            index=len(seasons) - 1,
            format_func=lambda x: seasons[x],
            key="end"
        )
    
    # Ensure valid range
    if season_start_idx > season_end_idx:
        st.sidebar.warning("Start season must be before or equal to end season.")
        season_start_idx, season_end_idx = season_end_idx, season_start_idx
    
    season_start = seasons[season_start_idx]
    season_end = seasons[season_end_idx]
    
    # Statistics
    st.sidebar.markdown("---")
    st.sidebar.subheader("Dataset Info")
    st.sidebar.info(f"""
    **Seasons**: {len(seasons)} total  
    **Selected**: {season_start} to {season_end}
    """)
    
    # CSS to make tabs larger and more visible
    st.markdown("""
    <style>
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 60px;
        padding-left: 20px;
        padding-right: 20px;
        font-size: 18px;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Instructional text before tabs
    st.markdown("""  
    ### 📑 Explore Different Perspectives
    Choose a tab below to explore relegation battles from different analytical angles:
    """)
    
    # Build list of enabled tabs
    enabled_tabs = {k: v for k, v in TAB_CONFIG.items() if v['enabled']}
    
    if not enabled_tabs:
        st.error("No tabs are enabled. Please check TAB_CONFIG in app.py")
        st.stop()
    
    # Create tab labels
    tab_labels = [f"{config['icon']} {config['title']}" for config in enabled_tabs.values()]
    
    # Create tabs dynamically based on configuration
    tabs = st.tabs(tab_labels)
    
    # Render each enabled tab
    for tab, (tab_key, tab_config) in zip(tabs, enabled_tabs.items()):
        with tab:
            # Check if this tab needs season indices (special case for terrain)
            if tab_config.get('needs_indices', False):
                tab_config['render_func'](
                    DB_PATH, 
                    season_start, 
                    season_end,
                    season_start_idx,
                    season_end_idx
                )
            else:
                tab_config['render_func'](DB_PATH, season_start, season_end)


if __name__ == "__main__":
    main()
