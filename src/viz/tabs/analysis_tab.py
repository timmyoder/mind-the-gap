"""Analysis tab: Gap distribution and top escapes."""

import streamlit as st
import sqlite3
from src.viz.analysis import get_survived_gaps_histogram, get_escape_summary_table


def render_analysis_tab(db_path: str, season_start: str, season_end: str):
    """Render the Analysis tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
    """
    st.subheader("📊 Relegation Battle Analysis")
    st.markdown("""
    Explore the distribution of relegation escapes and see which gaps have been 
    successfully overcome in Premier League history.
    """)
    
    # Histogram of survived gaps
    st.markdown("### Distribution of Maximum Gaps Overcome")
    st.markdown("""
    This histogram shows all the maximum gaps that teams have overcome to survive. 
    Each bar represents teams that faced a certain gap at their worst point but still survived.
    """)
    
    with st.spinner("Analyzing survived gaps..."):
        try:
            conn = sqlite3.connect(db_path)
            histogram_fig, stats = get_survived_gaps_histogram(conn, season_start, season_end)
            
            # Use columns for 10% margins on each side (better mobile scrolling)
            col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
            with col2:
                st.plotly_chart(histogram_fig, width='stretch', key='analysis_histogram')
            
            # Display statistics below the figure
            st.markdown(f"**Statistics:** Mean: {stats['mean']:.1f} pts | Median: {stats['median']:.1f} pts | Max: {stats['max']:.0f} pts")
            
            # Show top escapes table
            st.markdown("### Top 10 Biggest Escapes")
            escape_table = get_escape_summary_table(conn, season_start, season_end, top_n=10)
            
            # Format the table
            escape_table_display = escape_table.copy()
            escape_table_display.columns = ['Season', 'Team', 'Gap Overcome (pts)', 'Date of Worst Gap']
            escape_table_display['Gap Overcome (pts)'] = escape_table_display['Gap Overcome (pts)'].astype(int)
            
            st.dataframe(
                escape_table_display,
                hide_index=True,
                width='stretch'
            )
            
            conn.close()
            
        except Exception as e:
            st.error(f"Error building histogram: {str(e)}")
            st.exception(e)
