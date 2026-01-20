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
    st.subheader("⚡ Gap Closure Rate to Reach Safety")
    st.markdown("""
    How much faster must you earn points than 17th place to survive?
    
    This shows the **gap closure rate** - the PPG advantage over 17th place needed to overcome 
    the deficit. For example, 0.82 PPG means you must earn 0.82 points per game MORE than 17th 
    place to close the gap before the season ends.
    """)
    
    with st.spinner("Calculating required form..."):
        try:
            conn = sqlite3.connect(db_path)
            ppg_fig = get_points_per_game_required(conn, season_start, season_end)
            
            # Use columns for 10% margins on each side (better mobile scrolling)
            col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
            with col2:
                st.plotly_chart(ppg_fig, width='stretch', key='ppg_required')
            
            conn.close()
            
            st.markdown("""
            **💡 Interpreting Gap Closure Rates:**
            - **0.5 PPG advantage** = Earn 0.5 more per game than 17th (e.g., you get 1.5, they get 1.0)
            - **1.0 PPG advantage** = Earn 1 point more per game (difficult to sustain)
            - **1.5 PPG advantage** = Earn 1.5 more per game (requires excellent form while 17th struggles)
            - **>2.0 PPG advantage** = Historically very rare, almost impossible
            
            **Note:** This assumes 17th place continues their current form. If they collapse, your 
            required advantage decreases. If they improve, you need even better form.
            
            **Blue dots** show teams that achieved the needed advantage and survived.
            **Red dots** show teams that couldn't maintain the advantage and were relegated.
            """)
            
        except Exception as e:
            st.error(f"Error building PPG chart: {str(e)}")
            st.exception(e)
