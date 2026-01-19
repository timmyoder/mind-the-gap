# App Structure Documentation

## Overview
The Streamlit app is now organized with a modular tab-based architecture, making it easy to enable/disable tabs and maintain code.

## File Organization

```
mind-the-gap/
├── app.py                          # Main app with tab configuration
├── src/
│   └── viz/
│       ├── analysis.py             # Visualization functions (histograms, scatter, heatmaps)
│       ├── terrain.py              # 3D terrain visualization
│       └── tabs/                   # Tab-specific render functions
│           ├── __init__.py
│           ├── trends_tab.py       # Comeback trajectories
│           ├── analysis_tab.py     # Gap distribution & top escapes
│           ├── terrain_tab.py      # 3D terrain view
│           ├── danger_map_tab.py   # Gap vs games remaining scatter
│           ├── heatmap_tab.py      # Survival probability heatmap
│           └── ppg_tab.py          # Required points per game
```

## How to Enable/Disable Tabs

Edit the `TAB_CONFIG` dictionary at the top of `app.py`:

```python
TAB_CONFIG = {
    'trends': {
        'enabled': True,  # <-- Set to False to hide this tab
        'icon': '📈',
        'title': 'Trends',
        'render_func': render_trends_tab
    },
    'analysis': {
        'enabled': True,
        'icon': '📊',
        'title': 'Analysis',
        'render_func': render_analysis_tab
    },
    # ... more tabs
}
```

**To disable a tab:** Change `'enabled': True` to `'enabled': False`

**Benefits:**
- Code remains in place (no deletion needed)
- Easy to re-enable later
- Clean configuration in one place
- Tab order controlled by dictionary order

## How to Add a New Tab

1. **Create tab file** in `src/viz/tabs/new_tab.py`:
```python
"""Description of new tab."""

import streamlit as st
import sqlite3

def render_new_tab(db_path: str, season_start: str, season_end: str):
    """Render the new tab content."""
    st.subheader("My New Tab")
    
    with st.spinner("Loading..."):
        try:
            conn = sqlite3.connect(db_path)
            # Your code here
            conn.close()
        except Exception as e:
            st.error(f"Error: {str(e)}")
```

2. **Import in app.py:**
```python
from src.viz.tabs.new_tab import render_new_tab
```

3. **Add to TAB_CONFIG:**
```python
TAB_CONFIG = {
    # ... existing tabs ...
    'new_tab': {
        'enabled': True,
        'icon': '🎨',
        'title': 'My New Tab',
        'render_func': render_new_tab
    }
}
```

## Tab Files Explained

### `trends_tab.py`
- Shows comeback trajectories (biggest escape per season)
- Uses `get_biggest_escapes_by_season()` from `analysis.py`
- Has legend toggle option

### `analysis_tab.py`
- Histogram of gaps overcome
- Top 10 escapes table
- Uses `get_survived_gaps_histogram()` and `get_escape_summary_table()`

### `terrain_tab.py`
- 3D visualization of all relegation battles
- Options for danger-only view and team ordering
- Uses `build_terrain_visualization()` from `terrain.py`
- **Special:** Needs season indices for metrics display

### `danger_map_tab.py`
- Scatter plot of gap vs games remaining
- Shows survived (blue) vs relegated (red) positions
- Includes great escapes (gold squares) and current Wolves position (red star)
- Uses `get_danger_map_scatter()`

### `heatmap_tab.py`
- Survival probability by gap and games remaining
- Color-coded: green = high survival rate, red = low
- Uses `get_survival_probability_heatmap()`

### `ppg_tab.py`
- Required points per game to reach safety
- Reference lines for 1.0, 1.5, 2.0 PPG
- Uses `get_points_per_game_required()`

## Visualization Functions Location

All visualization generation functions remain in:
- `src/viz/analysis.py` - Most charts (histograms, scatter, heatmaps)
- `src/viz/terrain.py` - 3D terrain surface plot

Tab files only handle:
- Streamlit layout and UI controls
- Calling visualization functions
- Displaying results and insights

## Common Patterns

### Standard tab (most tabs):
```python
def render_tab(db_path: str, season_start: str, season_end: str):
    # Takes 3 arguments
    # Uses season filters for queries
```

### Special case (terrain tab):
```python
def render_terrain_tab(db_path, season_start, season_end, season_start_idx, season_end_idx):
    # Takes 5 arguments
    # Needs season indices for display metrics
    # Flag in TAB_CONFIG: 'needs_indices': True
```

## Maintenance Tips

**To modify tab content:**
- Edit the corresponding file in `src/viz/tabs/`

**To modify visualizations:**
- Edit functions in `src/viz/analysis.py` or `src/viz/terrain.py`

**To change tab order:**
- Reorder entries in `TAB_CONFIG` dictionary

**To rename a tab:**
- Change `'title'` and `'icon'` in `TAB_CONFIG`
- No need to touch the tab file itself

## Testing Changes

After modifying code:
1. Restart Streamlit: `Ctrl+C` then `streamlit run app.py`
2. Or use Streamlit's auto-reload (if watching files)
3. Check all enabled tabs still work
4. Verify disabled tabs don't appear

## Future Enhancements

Easy to add:
- Tab-specific filters (beyond season range)
- Export/download buttons per tab
- Tab-specific caching for performance
- User preferences for default tab order
