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
        What percentage of teams survived when needing each gap closure rate?
        
        Shows survival probability based on the PPG advantage over 17th place required to close the gap.
        """)
        
        with st.spinner("Calculating PPG-based survival probabilities..."):
            try:
                conn = sqlite3.connect(db_path)
                heatmap_fig = get_ppg_survival_heatmap(conn, season_start, season_end)
                st.plotly_chart(heatmap_fig, width='stretch', key='ppg_heatmap')
                conn.close()
                
                st.markdown("""
                **💡 How to Read:**
                - **Green bars** = High survival rate at that gap closure rate
                - **Red bars** = Low survival rate (very difficult advantage to maintain)
                - **X-axis**: Gap closure rate in PPG (how much faster you must earn points than 17th)
                - Sample size shown on each bar
                - ⭐ Wolves' current position shown (if in 2025-26 season)
                
                **Interpreting the rates:**
                - <0.5 PPG advantage = Relatively easy (slight outperformance needed)
                - 0.5-1.0 PPG advantage = Moderate (steady good form while 17th is average)
                - 1.0-1.5 PPG advantage = Challenging (excellent form while 17th struggles)
                - >1.5 PPG advantage = Very difficult (requires sustained excellence AND 17th collapse)
                
                **Remember:** This is PPG MORE than 17th place, not your absolute PPG.
                """)
                
            except Exception as e:
                st.error(f"Error building PPG heatmap: {str(e)}")
                st.exception(e)
