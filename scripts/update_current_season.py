"""Update current season data with latest match results."""

import requests
from pathlib import Path
from datetime import datetime
import sys

def update_current_season():
    """Download latest 2025-26 season data and update database."""
    
    # URL for current season
    season_code = "2526"
    url = f"https://www.football-data.co.uk/mmz4281/{season_code}/E0.csv"
    csv_path = Path("data/raw/2526.csv")
    
    print("=" * 60)
    print("📊 Mind the Gap - Current Season Update")
    print("=" * 60)
    print()
    
    # Download latest data
    print(f"🔄 Downloading latest 2025-26 data from Football-Data.co.uk...")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading data: {e}")
        print("\n💡 Tip: Check if the URL is correct or try again later")
        sys.exit(1)
    
    # Save CSV
    csv_path.write_bytes(response.content)
    print(f"✅ Downloaded and saved to {csv_path}")
    print(f"📅 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Show file info
    lines = len(response.text.strip().split('\n')) - 1  # Subtract header
    print(f"📈 Total matches in file: {lines}")
    print()
    
    # Re-run pipeline
    print("🔧 Re-running data pipeline to update database...")
    print("-" * 60)
    print()
    
    # Import pipeline directly (assumes script is run in conda env)
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from scripts.pipeline import run_full_pipeline
        run_full_pipeline()
        
        print()
        print("-" * 60)
        print()
        print("✅ Database updated successfully!")
        print()
        print("🚀 Next steps:")
        print("   1. Restart Streamlit app: streamlit run app.py")
        print("   2. Check Wolves' updated position in the visualizations")
    except Exception as e:
        print()
        print(f"❌ Pipeline failed: {e}")
        print("\n💡 Make sure you're running this in the 'mind-the-gap' conda environment")
        print("   Run: conda activate mind-the-gap")
        sys.exit(1)

if __name__ == "__main__":
    update_current_season()
