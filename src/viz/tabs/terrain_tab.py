"""Terrain tab: 3D visualization of relegation battles."""

import streamlit as st
from src.viz.terrain import build_terrain_visualization


def render_terrain_tab(db_path: str, season_start: str, season_end: str, season_start_idx: int, season_end_idx: int):
    """Render the 3D Terrain tab content.
    
    Args:
        db_path: Path to SQLite database
        season_start: Start season filter
        season_end: End season filter
        season_start_idx: Index of start season (for metrics)
        season_end_idx: Index of end season (for metrics)
    """
    st.subheader("🗻 3D Relegation Terrain")
    st.markdown("""
    Explore the landscape of relegation battles. Rotate and zoom to see how teams 
    navigate danger throughout each season.
    """)
    
    # Display options for 3D terrain
    col1, col2 = st.columns(2)
    
    with col1:
        danger_only = st.checkbox(
            "Show danger zone only",
            value=False,
            help="Only display teams that had a positive gap to 17th place at some point"
        )
    
    with col2:
        sort_by = st.radio(
            "Order teams by",
            options=['season', 'position'],
            index=0,
            format_func=lambda x: 'Season' if x == 'season' else 'Final position',
            help="Choose how to arrange teams on the X-axis",
            horizontal=True
        )
    
    # Info expander
    with st.expander("ℹ️ About the 3D Terrain", expanded=False):
        st.markdown("""
        **X-axis**: Teams (grouped by season or final position)
        
        **Y-axis**: Days into the season
        
        **Z-axis**: Points gap to 17th place (safety line)
        - Positive = safe (more points than 17th)
        - Zero = on the safety line  
        - Negative = in danger (fewer points than 17th)
        
        **Colors**:
        - 🔴 Red = Deep danger (very negative)
        - 🟡 Yellow = Near safety line
        - 🟢 Green = Very safe (very positive)
        
        **Navigation**:
        - Click & drag to rotate
        - Scroll to zoom
        - Hover for details
        """)
    
    # Build visualization
    with st.spinner("Building 3D terrain... This may take a moment for large season ranges."):
        try:
            fig = build_terrain_visualization(
                db_path,
                danger_only=danger_only,
                season_start=season_start,
                season_end=season_end,
                sort_by=sort_by
            )
            
            # Display the figure
            st.plotly_chart(fig, width='stretch', key='terrain_3d')
            
            # Quick insights
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    "View Mode",
                    "Danger Only" if danger_only else "All Teams"
                )
            
            with col2:
                st.metric(
                    "Ordering",
                    "By Position" if sort_by == 'position' else "By Season"
                )
            
            with col3:
                st.metric(
                    "Season Range",
                    f"{season_end_idx - season_start_idx + 1}"
                )
            
        except Exception as e:
            st.error(f"Error building visualization: {str(e)}")
            st.exception(e)
