"""Survival Heatmap tab: Survival probability by position."""

import streamlit as st
import sqlite3
from src.viz.analysis import get_survival_probability_heatmap, get_ppg_survival_heatmap


def render_heatmap_tab(db_path: str, season_start: str, season_end: str):
    """Render the Survival Probability Heatmap tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
    """
    st.subheader("🔥 Survival Probability Heatmap")
    
    # View selector
    view_mode = st.radio(
        "View by:",
        options=['gap', 'ppg'],
        format_func=lambda x: 'Gap to 17th Place' if x == 'gap' else 'Required Points Per Game',
        horizontal=True,
        help="Choose whether to view survival rates by points gap or required PPG"
    )
    
    if view_mode == 'gap':
        st.markdown("""
        What percentage of teams survived from each combination of gap and games remaining?
        
        Darker green = higher survival rate. Dark red = most teams relegated from that position.
        """)
        
        with st.spinner("Calculating survival probabilities..."):
            try:
                conn = sqlite3.connect(db_path)
                heatmap_fig = get_survival_probability_heatmap(conn, season_start, season_end)
                st.plotly_chart(heatmap_fig, width='stretch', key='survival_heatmap')
                conn.close()
                
                st.markdown("""
                **💡 How to Read:**
                - **Green zones** = High survival rate (>50%)
                - **Red zones** = Low survival rate (<50%)
                - Empty cells = Not enough data (fewer than 3 teams in that situation)
                - ⭐ Wolves' current position shown (if in 2025-26 season)
                """)
                
            except Exception as e:
                st.error(f"Error building heatmap: {str(e)}")
                st.exception(e)
    
    else:  # ppg view
        st.markdown("""
        What percentage of teams survived when requiring each PPG rate?
        
        Shows survival probability based on the points-per-game form needed to reach safety.
        """)
        
        with st.spinner("Calculating PPG-based survival probabilities..."):
            try:
                conn = sqlite3.connect(db_path)
                heatmap_fig = get_ppg_survival_heatmap(conn, season_start, season_end)
                st.plotly_chart(heatmap_fig, width='stretch', key='ppg_heatmap')
                conn.close()
                
                st.markdown("""
                **💡 How to Read:**
                - **Green zones** = High survival rate when needing that PPG
                - **Red zones** = Low survival rate (difficult PPG requirement)
                - **Y-axis bins**: PPG ranges (e.g., 1.5-2.0 = need 1.5 to 2.0 points per game)
                - Empty cells = Not enough historical data
                - ⭐ Wolves' current position shown (if in 2025-26 season)
                
                **Reference:**
                - <1.0 PPG = Very easy (drawing/losing most games still survives)
                - 1.0-1.5 PPG = Achievable (mix of wins and draws)
                - 1.5-2.0 PPG = Challenging (need good form)
                - >2.0 PPG = Very difficult (title-winning pace)
                """)
                
            except Exception as e:
                st.error(f"Error building PPG heatmap: {str(e)}")
                st.exception(e)
