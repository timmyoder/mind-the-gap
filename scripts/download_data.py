"""Helper script to download historical EPL data from Football-Data.co.uk."""

import requests
from pathlib import Path
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def download_season_csv(season_code: str, output_dir: str = "data/raw") -> bool:
    """Download a single season's CSV from Football-Data.co.uk.
    
    Args:
        season_code: Two-digit season code (e.g., "0607" for 2006/07)
        output_dir: Directory to save CSV file
        
    Returns:
        True if successful, False otherwise
    """
    # Base URL for Premier League data
    base_url = "https://www.football-data.co.uk/mmz4281"
    url = f"{base_url}/{season_code}/E0.csv"
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    file_path = output_path / f"{season_code}.csv"
    
    try:
        logger.info(f"Downloading {season_code}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Save to file
        with open(file_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"✓ Saved to {file_path}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Failed to download {season_code}: {e}")
        return False


def download_all_seasons(start_year: int = 1993, end_year: int = 2025, output_dir: str = "data/raw"):
    """Download all available Premier League seasons.
    
    Args:
        start_year: First season start year (e.g., 1993 for 1993/94)
        end_year: Last season start year (e.g., 2024 for 2024/25)
        output_dir: Directory to save CSV files
    """
    logger.info("="*80)
    logger.info(f"DOWNLOADING EPL DATA: {start_year}/{start_year+1} to {end_year}/{end_year+1}")
    logger.info("="*80 + "\n")
    
    successful = 0
    failed = 0
    
    for year in range(start_year, end_year + 1):
        # Convert year to two-digit code
        year_code = str(year)[-2:]  # e.g., 2006 → "06"
        next_year_code = str(year + 1)[-2:]  # e.g., 2007 → "07"
        season_code = f"{year_code}{next_year_code}"
        
        # Download with small delay to be respectful to server
        if download_season_csv(season_code, output_dir):
            successful += 1
        else:
            failed += 1
        
        time.sleep(0.5)  # 500ms delay between requests
    
    logger.info("\n" + "="*80)
    logger.info(f"DOWNLOAD COMPLETE")
    logger.info(f"Successful: {successful} seasons")
    logger.info(f"Failed: {failed} seasons")
    logger.info("="*80 + "\n")
    
    if failed > 0:
        logger.warning(f"\n⚠️  Some downloads failed. This is normal for:")
        logger.warning("   - Current season (data may not be published yet)")
        logger.warning("   - Very recent matchweeks (data updated weekly)")
        logger.warning("   - Network issues")
        logger.info("\nYou can re-run this script to retry failed downloads.")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Download EPL historical data")
    parser.add_argument(
        "--start",
        type=int,
        default=1993,
        help="Start year (e.g., 1993 for 1993/94 season)"
    )
    parser.add_argument(
        "--end",
        type=int,
        default=2025,
        help="End year (e.g., 2024 for 2024/25 season)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/raw",
        help="Output directory for CSV files"
    )
    
    args = parser.parse_args()
    
    download_all_seasons(
        start_year=args.start,
        end_year=args.end,
        output_dir=args.output
    )
    
    logger.info("\n📊 Next steps:")
    logger.info("   1. Verify CSV files in data/raw/")
    logger.info("   2. Run: python pipeline.py")
    logger.info("   3. Query the database to find the record!\n")
