"""CSV data loading and validation for EPL match results."""

import pandas as pd
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


def load_season_csv(file_path: str) -> pd.DataFrame:
    """Load a single season CSV from Football-Data.co.uk.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with standardized columns
        
    Raises:
        FileNotFoundError: If CSV doesn't exist
        ValueError: If required columns are missing
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV not found: {file_path}")

    # Load CSV - Football-Data.co.uk uses various encodings
    # Use usecols to only load columns we need, avoiding issues with variable column counts
    required_columns = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']
    
    try:
        df = pd.read_csv(file_path, encoding='utf-8', usecols=required_columns)
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding='latin-1', usecols=required_columns)
    except Exception:
        # Try with ISO-8859-1 encoding for very old files
        try:
            df = pd.read_csv(file_path, encoding='iso-8859-1', usecols=required_columns)
        except Exception as e:
            logger.error(f"Could not read {file_path}: {e}")
            return pd.DataFrame()
    
    # Check if dataframe is empty or has no rows
    if df.empty or len(df) == 0:
        logger.warning(f"Empty dataframe from {file_path}")
        return pd.DataFrame()
    
    # Note: required_columns already specified above in usecols
    # Verify all required columns were loaded
    missing = [col for col in required_columns if col not in df.columns]
    
    if missing:
        logger.error(f"Missing required columns in {file_path}: {missing}")
        return pd.DataFrame()

    # Select and rename columns for consistency
    df = df[required_columns].copy()
    
    # Clean team names (trim whitespace)
    df['HomeTeam'] = df['HomeTeam'].str.strip()
    df['AwayTeam'] = df['AwayTeam'].str.strip()
    
    # Validate result codes
    invalid_results = ~df['FTR'].isin(['H', 'D', 'A'])
    if invalid_results.any():
        invalid_count = invalid_results.sum()
        if invalid_count > len(df) * 0.5:  # More than 50% invalid
            logger.error(f"Too many invalid results ({invalid_count}/{len(df)}) in {file_path}")
            return pd.DataFrame()
        logger.warning(f"Found {invalid_count} invalid result codes in {file_path}")
        df = df[~invalid_results]
    
    # Convert date to datetime - try multiple formats
    # Save original string column before conversion attempts
    original_date_str = df['Date'].astype(str).copy()
    
    # Try 4-digit year first (modern format: DD/MM/YYYY)
    df['Date'] = pd.to_datetime(original_date_str, format='%d/%m/%Y', errors='coerce')
    
    # If most dates failed, try 2-digit year format (older files: DD/MM/YY)
    if df['Date'].isna().sum() > len(df) * 0.5:
        # For 2-digit years, pandas defaults to 1969-2068 range
        # 93-99 will be 1993-1999, 00-68 will be 2000-2068
        df['Date'] = pd.to_datetime(original_date_str, format='%d/%m/%y', errors='coerce')
    
    # If still failing, try dayfirst=True auto-detection
    if df['Date'].isna().sum() > len(df) * 0.5:
        df['Date'] = pd.to_datetime(original_date_str, dayfirst=True, errors='coerce')
    
    # Remove rows with invalid dates
    df = df.dropna(subset=['Date'])
    
    if df.empty:
        logger.warning(f"No valid dates found in {file_path}")
        return pd.DataFrame()
    
    # Sort by date
    df = df.sort_values('Date').reset_index(drop=True)
    
    logger.info(f"Loaded {len(df)} matches from {file_path}")
    
    return df


def infer_season_from_filename(file_path: str) -> Optional[str]:
    """Extract season from filename (e.g., '0607.csv' -> '2006-07').
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Season string in format 'YYYY-YY', or None if cannot parse
    """
    filename = Path(file_path).stem
    
    # Try to extract 4-digit year pattern (e.g., '0607' or '0607')
    if len(filename) >= 4 and filename[:4].isdigit():
        year1 = int(filename[:2])
        year2 = int(filename[2:4])
        
        # Handle century rollover (92-99 = 1992-1999, 00-25 = 2000-2025)
        if year1 >= 92:
            full_year1 = 1900 + year1
        else:
            full_year1 = 2000 + year1
            
        full_year2 = full_year1 + 1
        
        return f"{full_year1}-{str(full_year2)[-2:]}"
    
    return None


def load_all_seasons(data_dir: str = "data/raw") -> pd.DataFrame:
    """Load all season CSVs from directory.
    
    Args:
        data_dir: Directory containing season CSV files
        
    Returns:
        Combined DataFrame with 'Season' column added
    """
    data_path = Path(data_dir)
    
    if not data_path.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")
    
    csv_files = sorted(data_path.glob("*.csv"))
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {data_dir}")
    
    logger.info(f"Found {len(csv_files)} CSV files\n")
    
    all_seasons = []
    successful_loads = []
    failed_loads = []
    
    for csv_file in csv_files:
        season = infer_season_from_filename(csv_file)
        
        if season is None:
            logger.warning(f"✗ {csv_file.name}: Could not infer season from filename")
            failed_loads.append((csv_file.name, "Invalid filename format"))
            continue
        
        try:
            df = load_season_csv(csv_file)
            
            # Skip empty dataframes
            if df.empty:
                logger.warning(f"✗ {csv_file.name} ({season}): No valid data after parsing")
                failed_loads.append((csv_file.name, "No valid data"))
                continue
                
            df['Season'] = season
            all_seasons.append(df)
            successful_loads.append((csv_file.name, season, len(df)))
            logger.info(f"✓ {csv_file.name} ({season}): {len(df)} matches")
        except Exception as e:
            logger.error(f"✗ {csv_file.name} ({season}): {str(e)}")
            failed_loads.append((csv_file.name, str(e)))
            continue
    
    # Summary report
    logger.info(f"\n{'='*70}")
    logger.info(f"LOADING SUMMARY:")
    logger.info(f"  ✓ Successful: {len(successful_loads)}/{len(csv_files)} seasons")
    logger.info(f"  ✗ Failed: {len(failed_loads)}/{len(csv_files)} seasons")
    
    if failed_loads:
        logger.warning(f"\n  Failed seasons (will NOT be included in analysis):")
        for filename, reason in failed_loads:
            logger.warning(f"    • {filename}: {reason}")
    
    logger.info(f"{'='*70}\n")
    
    if not all_seasons:
        raise ValueError("No valid season data loaded - cannot proceed")
    
    combined = pd.concat(all_seasons, ignore_index=True)
    
    return combined


def normalize_team_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize team names for consistency across seasons.
    
    Common variations:
    - "Man United" vs "Manchester Utd" vs "Manchester United"
    - "Leicester" vs "Leicester City"
    - "Wolves" vs "Wolverhampton"
    
    Args:
        df: DataFrame with 'HomeTeam' and 'AwayTeam' columns
        
    Returns:
        DataFrame with normalized team names
    """
    # Mapping of variations to canonical names
    name_mapping = {
        'Man United': 'Manchester Utd',
        'Manchester United': 'Manchester Utd',
        'Man City': 'Manchester City',
        'Leicester': 'Leicester City',
        'Wolves': 'Wolverhampton',
        'Wolverhampton Wanderers': 'Wolverhampton',
        'Tottenham': 'Tottenham Hotspur',
        'Spurs': 'Tottenham Hotspur',
        'Newcastle': 'Newcastle Utd',
        'Newcastle United': 'Newcastle Utd',
        'West Ham': 'West Ham United',
    }
    
    df = df.copy()
    df['HomeTeam'] = df['HomeTeam'].replace(name_mapping)
    df['AwayTeam'] = df['AwayTeam'].replace(name_mapping)
    
    return df


if __name__ == "__main__":
    # Quick test: load sample CSV
    logging.basicConfig(level=logging.INFO)
    
    # Test with all seasons if available
    try:
        df = load_all_seasons()
        print(f"\nLoaded {len(df)} matches across {df['Season'].nunique()} seasons")
        print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
        print(f"\nFirst few rows:")
        print(df.head())
    except FileNotFoundError as e:
        print(f"No data found: {e}")
        print("Download CSVs from https://www.football-data.co.uk/englandm.php")
