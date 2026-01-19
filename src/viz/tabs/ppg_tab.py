"""PPG Required tab: Points per game needed to reach safety."""

import streamlit as st
import sqlite3
from src.viz.analysis import get_points_per_game_required


def render_ppg_tab(db_path: str, season_start: str, season_end: str):
    """Render the Required PPG tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
    """
    st.subheader("⚡ Required Points Per Game to Reach Safety")
    st.markdown("""
    What form is needed to survive from different positions?
    
    This shows the points-per-game rate required to overcome the gap (assuming need to 
    reach 3 points above 17th place for safety).
    """)
    
    with st.spinner("Calculating required form..."):
        try:
            conn = sqlite3.connect(db_path)
            ppg_fig = get_points_per_game_required(conn, season_start, season_end)
            st.plotly_chart(ppg_fig, width='stretch', key='ppg_required')
            conn.close()
            
            st.markdown("""
            **💡 Reference Rates:**
            - **1.0 PPG** = Drawing every game (unlikely to survive from large gap)
            - **1.5 PPG** = Good form (roughly 1 win + 1 draw per 2 games)
            - **2.0 PPG** = Title-winning form (2 wins per 3 games)
            - **>2.5 PPG** = Historically very rare, almost impossible to sustain
            
            **Blue dots** show teams that survived despite the required rate.
            **Red dots** show teams that needed that rate but were relegated anyway.
            """)
            
        except Exception as e:
            st.error(f"Error building PPG chart: {str(e)}")
            st.exception(e)
