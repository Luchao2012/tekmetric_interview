"""
Data processing utilities for NASA Near Earth Object data.
"""
import logging
import time
import json
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime
import psutil
import os

# Get logger for this module
logger = logging.getLogger(__name__)

def parse_neo_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract required fields from a single NEO record.
    
    Args:
        record: JSON data for a single NEO
        
    Returns:
        Dictionary containing parsed and transformed NEO data
    """
    # Basic fields
    out = {
        'id': record['id'],
        'neo_reference_id': record['neo_reference_id'],
        'name': record['name'],
        # name_limited: take the part after first space or full name if none
        'name_limited': record['name'].split()[-1] if ' ' in record['name'] else record['name'],
        'designation': record['designation'],
        'nasa_jpl_url': record['nasa_jpl_url'],
        'absolute_magnitude_h': record['absolute_magnitude_h'],
        'is_potentially_hazardous_asteroid': record['is_potentially_hazardous_asteroid'],
        # estimated diameter in meters
        'est_diam_min_m': record['estimated_diameter']['meters']['estimated_diameter_min'],
        'est_diam_max_m': record['estimated_diameter']['meters']['estimated_diameter_max']
    }
    
    # Check if close_approach_data is empty
    if record['close_approach_data']:
        # Find the closest approach data entry (minimum miss_distance.kilometers)
        cad = min(
            record['close_approach_data'],
            key=lambda x: float(x['miss_distance']['kilometers'])
        )
        out.update({
            'close_approach_date': cad['close_approach_date'],
            'miss_distance_km': float(cad['miss_distance']['kilometers']),
            'miss_distance_au': float(cad['miss_distance']['astronomical']),  # Used for aggregation
            'relative_velocity_kps': float(cad['relative_velocity']['kilometers_per_second'])
        })
    else:
        # Handle case where no close approach data exists
        out.update({
            'close_approach_date': None,
            'miss_distance_km': None,
            'miss_distance_au': None,  # Used for aggregation
            'relative_velocity_kps': None
        })
    
    # Orbital data
    orb = record['orbital_data']
    out.update({
        'first_observation_date': orb['first_observation_date'],
        'last_observation_date': orb['last_observation_date'],
        'observations_used': orb['observations_used'],
        'orbital_period': float(orb['orbital_period'])
    })
    return out


def compute_aggregations(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Compute required aggregations:
      - total approaches closer than 0.2 AU
      - number of close approaches per year
      
    Args:
        df: DataFrame containing NEO records
        
    Returns:
        Dictionary with aggregation results
    """
    # Count of records with miss_distance_au < 0.2
    total_close = (df['miss_distance_au'] < 0.2).sum()
    
    # Extract year from close_approach_date and ensure it's an integer
    df['approach_year'] = pd.to_datetime(df['close_approach_date'], errors='coerce').dt.year
    
    # Drop NaN years and convert to int
    df = df.dropna(subset=['approach_year'])
    df['approach_year'] = df['approach_year'].astype(int)
    
    # Count approaches by year
    counts_per_year = df['approach_year'].value_counts().sort_index().to_dict()
    
    return {
        'total_approaches_lt_0.2_AU': int(total_close),
        'approaches_per_year': counts_per_year
    }


class DataProcessor:
    """
    Process NEO data in a scalable, chunked manner.
    This allows processing large volumes of data without loading everything into memory.
    """
    
    def __init__(self, chunk_size: int = None):
        """
        Initialize the data processor.
        
        Args:
            chunk_size: Number of records to process at once
        """
        self.chunk_size = chunk_size
        
    def process_records(self, records: List[Dict[str, Any]]) -> pd.DataFrame:
        """
        Process a list of NEO records into a DataFrame.
        
        Args:
            records: List of raw NEO JSON records
            
        Returns:
            DataFrame of processed records
        """
        start_time = time.time()
        logger.info(f"Processing {len(records)} NEO records")
        
        processed_records = []
        for i, rec in enumerate(records):
            try:
                processed_record = parse_neo_record(rec)
                processed_records.append(processed_record)
                
                # Log progress for large batches
                if (i+1) % 50 == 0:
                    logger.debug(f"Processed {i+1}/{len(records)} records")
                    
            except Exception as e:
                logger.error(f"Error processing record {i}: {str(e)}")
                logger.error(f"Problematic record: {json.dumps(rec)[:200]}...")  # Log beginning of record
        
        elapsed = time.time() - start_time
        df = pd.DataFrame(processed_records)
        
        # Log memory usage
        memory_usage = df.memory_usage(deep=True).sum() / (1024 * 1024)  # MB
        process = psutil.Process(os.getpid())
        total_memory = process.memory_info().rss / (1024 * 1024)  # MB
        
        logger.info(f"Processed {len(df)} records in {elapsed:.2f}s. DataFrame size: {memory_usage:.2f} MB, Process memory: {total_memory:.2f} MB")
        return df
    
    def save_to_parquet(self, df: pd.DataFrame, path: str, append: bool = False) -> None:
        """
        Save DataFrame to Parquet file, excluding miss_distance_au column.
        
        Args:
            df: DataFrame to save
            path: Path to save to
            append: If True, append to existing file
        """
        start_time = time.time()
        logger.info(f"Saving data to {path} (append={append})")
        
        # Create a copy of the DataFrame without the miss_distance_au column
        save_df = df.drop(columns=['miss_distance_au'], errors='ignore')
        logger.info(f"Columns being saved: {', '.join(save_df.columns)}")
        
        if append:
            # For appending, we need to handle the file existence check
            try:
                existing_df = pd.read_parquet(path)
                logger.info(f"Loaded existing file with {len(existing_df)} rows")
                
                # Check for schema mismatch
                missing_cols = set(existing_df.columns) - set(save_df.columns)
                extra_cols = set(save_df.columns) - set(existing_df.columns)
                if missing_cols or extra_cols:
                    logger.warning(f"Schema mismatch - Missing: {missing_cols}, Extra: {extra_cols}")
                
                combined_df = pd.concat([existing_df, save_df], ignore_index=True)
                combined_df.to_parquet(path, index=False)
                
                elapsed = time.time() - start_time
                file_size_mb = os.path.getsize(path) / (1024 * 1024)
                logger.info(f"Appended {len(save_df)} rows to {path} in {elapsed:.2f}s (total: {len(combined_df)} rows, {file_size_mb:.2f} MB)")
            except Exception as e:
                logger.warning(f"Error appending to existing file: {str(e)}")
                save_df.to_parquet(path, index=False)
                elapsed = time.time() - start_time
                file_size_mb = os.path.getsize(path) / (1024 * 1024)
                logger.info(f"Created new parquet file with {len(save_df)} rows at {path} in {elapsed:.2f}s ({file_size_mb:.2f} MB)")
        else:
            save_df.to_parquet(path, index=False)
            elapsed = time.time() - start_time
            file_size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info(f"Saved {len(save_df)} rows to {path} in {elapsed:.2f}s ({file_size_mb:.2f} MB)")
            
    def update_aggregations(self, df: pd.DataFrame, agg_path: str) -> Dict[str, Any]:
        """
        Update aggregations file with new data.
        
        Args:
            df: New data to incorporate into aggregations
            agg_path: Path to save aggregations
            
        Returns:
            Dictionary of updated aggregations
        """
        import json
        import os
        
        start_time = time.time()
        logger.info(f"Updating aggregations at {agg_path}")
        
        # Compute aggregations for the new chunk
        new_aggs = compute_aggregations(df)
        logger.info(f"New chunk aggregations: {new_aggs['total_approaches_lt_0.2_AU']} approaches < 0.2AU, "
                   f"{len(new_aggs['approaches_per_year'])} years with approaches")
        
        # If aggregations file exists, update it
        if os.path.exists(agg_path):
            try:
                with open(agg_path, 'r') as f:
                    existing_aggs = json.load(f)
                
                previous_total = existing_aggs.get('total_approaches_lt_0.2_AU', 0)
                previous_years = len(existing_aggs.get('approaches_per_year', {}))
                    
                # Update total_approaches_lt_0.2_AU
                new_aggs['total_approaches_lt_0.2_AU'] += previous_total
                
                # Merge approaches_per_year
                for year, count in existing_aggs.get('approaches_per_year', {}).items():
                    year_int = int(year)  # Convert string key to int
                    if year_int in new_aggs['approaches_per_year']:
                        new_aggs['approaches_per_year'][year_int] += count
                    else:
                        new_aggs['approaches_per_year'][year_int] = count
                
                logger.info(f"Updated aggregations from previous: {previous_total} -> {new_aggs['total_approaches_lt_0.2_AU']} approaches < 0.2AU, "
                           f"{previous_years} -> {len(new_aggs['approaches_per_year'])} years with approaches")
            except Exception as e:
                logger.warning(f"Could not read existing aggregations from {agg_path}, creating new file: {str(e)}")
        else:
            logger.info(f"No existing aggregations found at {agg_path}, creating new file")
        
        # Write updated aggregations
        with open(agg_path, 'w') as f:
            json.dump(new_aggs, f, indent=2)
        
        elapsed = time.time() - start_time
        logger.info(f"Saved updated aggregations in {elapsed:.2f}s")
        
        return new_aggs
