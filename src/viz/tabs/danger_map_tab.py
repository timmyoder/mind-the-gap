"""Danger Map tab: Gap vs games remaining scatter plot."""

import streamlit as st
import sqlite3
from src.viz.analysis import get_danger_map_scatter


def render_danger_map_tab(db_path: str, season_start: str, season_end: str):
    """Render the Danger Map tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
    """
    st.subheader("🎯 The Danger Map")
    st.markdown("""
    **Can Wolves survive from their current position?** This scatter plot shows every historical 
    position by gap and games remaining, colored by outcome.
    
    Look for the "survival frontier" - the boundary between escaped and relegated teams.
    """)
    
    with st.spinner("Plotting historical positions..."):
        try:
            conn = sqlite3.connect(db_path)
            danger_map_fig = get_danger_map_scatter(conn, season_start, season_end)
            
            # Use columns for 10% margins on each side (better mobile scrolling)
            col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
            with col2:
                st.plotly_chart(danger_map_fig, width='stretch', key='danger_map')
            
            conn.close()
            
            st.markdown("""
            **💡 Insights:**
            - **Blue dots** = Teams that survived despite being in danger
            - **Red dots** = Teams that were relegated
            - **Gold squares** = Great escapes (8+ point gaps overcome)
            - **Red star** = Wolves' current position (if in 2025-26 season)
            - X-axis reversed: More games remaining = earlier in season = left side
            - Look for blue dots near Wolves' position to see if similar escapes have happened
            """)
            
        except Exception as e:
            st.error(f"Error building danger map: {str(e)}")
            st.exception(e)
