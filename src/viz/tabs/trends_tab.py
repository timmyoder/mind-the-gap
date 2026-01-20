"""Trends tab: Comeback trajectories visualization."""

import streamlit as st
import sqlite3
from src.viz.analysis import get_biggest_escapes_by_season


def render_trends_tab(db_path: str, season_start: str, season_end: str):
    """Render the Trends tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
    """
    st.subheader("📈 Comeback Trajectories by Season")
    st.markdown("""
    Track the biggest successful escape from each season. Lines show how teams climbed 
    from their worst position back to safety. Darker lines represent more severe gaps overcome.
    """)
    
    # Legend toggle
    show_legend = st.checkbox(
        "Show legend",
        value=False,
        help="Toggle legend visibility (note: with many seasons, legend can be very large)"
    )
    
    with st.spinner("Loading comeback stories..."):
        try:
            conn = sqlite3.connect(db_path)
            trajectories_fig = get_biggest_escapes_by_season(conn, season_start, season_end, show_legend=show_legend)
            
            # Use columns for 10% margins on each side (better mobile scrolling)
            col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
            with col2:
                st.plotly_chart(trajectories_fig, width='stretch', key='trends_trajectory')
            
            # Always-visible legend for current season
            st.markdown("""
            <div style="background-color: rgba(255, 0, 0, 0.1); border-left: 4px solid red; padding: 10px; margin-top: 10px; margin-bottom: 15px;">
                <strong>🔴 Red Line:</strong> Wolves 2025-26 current season trajectory
            </div>
            """, unsafe_allow_html=True)
            
            conn.close()
            
            # Insights
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("""
                **🔍 What to Look For:**
                - Peak danger points (highest gaps)
                - Timing of turnarounds
                - Different escape patterns (gradual vs. sudden)
                """)
            
            with col2:
                st.markdown("""
                **📊 Insights:**
                - Orange line = safety threshold (17th place)
                - Dark blue lines = biggest historical escapes
                - Light blue lines = minor dips into danger
                - Red line = Wolves 2025-26 current season
                """)
            
        except Exception as e:
            st.error(f"Error building trajectories: {str(e)}")
            st.exception(e)
