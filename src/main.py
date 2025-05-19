"""
Main data collection script for NASA Near Earth Object data.
This script is designed to be run as a standalone script or imported as a module.
It includes functionality to collect data in chunks, with rate limiting and retries.
"""
import os
import time
import json
import logging
import argparse
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd
from datetime import datetime

from src import config
from src.api_client import NeoApiClient
from src.data_processor import DataProcessor, compute_aggregations

# Get logger for this module
logger = logging.getLogger(__name__)

def collect_neos(
    limit: int = 200,
    output_path: Optional[Path] = None,
    chunk_size: int = None,
    save_intermediates: bool = False,
    job_id: str = None
) -> pd.DataFrame:
    """
    Collect NEO data from NASA API, with support for chunking and rate limiting.
    
    Args:
        limit: Maximum number of NEOs to collect
        output_path: Path to save parquet file, if None uses the default
        chunk_size: Process in chunks of this size to limit memory usage
        save_intermediates: Whether to save intermediate results (for recovery)
        job_id: Optional identifier for this job run (e.g., for cron jobs)
        
    Returns:
        DataFrame of collected NEOs or None if saving in chunks
    """
    # Generate job ID if not provided
    if not job_id:
        job_id = f"neo_collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Log collection start with job details
    logger.info(f"Starting NEO data collection job: {job_id}")
    logger.info(f"Collection parameters: limit={limit}, chunks={chunk_size}, save_intermediates={save_intermediates}")
    
    # Initialize components
    api_client = NeoApiClient()
    processor = DataProcessor(chunk_size)
    
    # Set paths
    output_path = output_path or config.DATA_DIR / f"neos_{limit}.parquet"
    agg_path = config.DATA_DIR / "aggregations.json"
    
    logger.info(f"Output will be saved to: {output_path}")
    logger.info(f"Aggregations will be saved to: {agg_path}")
    
    # Determine chunk size
    chunk_size = chunk_size or config.DEFAULT_CHUNK_SIZE
    if limit < chunk_size:
        chunk_size = limit  # Don't use chunks for small requests
    
    # Track progress
    total_collected = 0
    page = 0
    chunk_dfs = []
    
    # Process data in chunks to limit memory usage
    try:
        # Log collection start time for tracking duration
        collection_start = time.time()
            
        # Main collection loop
        while total_collected < limit:
            loop_start = time.time()
            # Request size for this iteration
            request_size = min(config.DEFAULT_BATCH_SIZE, limit - total_collected)
            
            # Log progress percentage
            progress_pct = (total_collected / limit) * 100
            logger.info(f"Progress: {total_collected}/{limit} ({progress_pct:.1f}%) - Requesting page {page} with size {request_size}")
            
            # Fetch data
            try:
                data = api_client.fetch_neo_page(page=page, size=request_size)
                neos = data['near_earth_objects']
                logger.info(f"Retrieved {len(neos)} NEOs from page {page}")
            except Exception as e:
                logger.error(f"Error fetching page {page}: {str(e)}")
                logger.error(traceback.format_exc())
                # Wait before retrying
                logger.info("Waiting 30 seconds before retrying...")
                time.sleep(30)
                continue
            
            if not neos:
                logger.warning(f"No NEOs returned from page {page}, stopping collection")
                break
                
            # Process records
            records = []
            for rec in neos:
                records.append(rec)
                total_collected += 1
                if total_collected >= limit:
                    logger.info(f"Reached collection limit of {limit}")
                    break
            
            # Convert to DataFrame
            current_df = processor.process_records(records)
            
            # Either accumulate or save chunk
            if save_intermediates:
                # Save this chunk and update aggregations
                chunk_file = config.DATA_DIR / f"neos_chunk_{page}.parquet"
                processor.save_to_parquet(current_df, chunk_file)
                processor.update_aggregations(current_df, agg_path)
                logger.info(f"Saved chunk {page} with {len(current_df)} records. Total so far: {total_collected}/{limit}")
            else:
                # Accumulate in memory
                chunk_dfs.append(current_df)
                memory_used = sum(df.memory_usage(deep=True).sum() for df in chunk_dfs) / (1024 * 1024)
                logger.info(f"Accumulated {len(chunk_dfs)} chunks in memory. Total records: {total_collected}, Memory used: {memory_used:.2f} MB")
            
            # Go to next page
            page += 1
            
            # Log iteration time
            loop_time = time.time() - loop_start
            elapsed_total = time.time() - collection_start
            est_remaining = (elapsed_total / total_collected) * (limit - total_collected) if total_collected > 0 else 0
            
            logger.info(f"Page {page-1} processed in {loop_time:.2f}s. Total elapsed: {elapsed_total:.2f}s. Est. remaining: {est_remaining:.2f}s")
            
            # If we have enough data or reached the chunk size, merge and save
            if (not save_intermediates and 
                len(chunk_dfs) > 0 and
                (total_collected >= limit or 
                 (chunk_size and sum(len(df) for df in chunk_dfs) >= chunk_size))):
                
                # Merge accumulated dataframes
                merged_df = pd.concat(chunk_dfs, ignore_index=True)
                
                if total_collected >= limit:
                    # Final save
                    processor.save_to_parquet(merged_df, output_path)
                    aggs = compute_aggregations(merged_df)
                    with open(agg_path, 'w') as f:
                        json.dump(aggs, f, indent=2)
                    logger.info(f"Final data saved to {output_path}, aggregations saved to {agg_path}")
                    return merged_df
                else:
                    # Intermediate chunk save
                    intermediate_file = config.DATA_DIR / f"neos_intermediate_{page}.parquet"
                    processor.save_to_parquet(merged_df, intermediate_file)
                    processor.update_aggregations(merged_df, agg_path)
                    logger.info(f"Saved intermediate chunk with {len(merged_df)} records. Total collected: {total_collected}/{limit}")
                    chunk_dfs = []  # Clear memory
        
        # Final result if using in-memory processing
        if not save_intermediates and chunk_dfs:
            final_df = pd.concat(chunk_dfs, ignore_index=True)
            processor.save_to_parquet(final_df, output_path)
            aggs = compute_aggregations(final_df)
            with open(agg_path, 'w') as f:
                json.dump(aggs, f, indent=2)
            logger.info(f"Final data saved to {output_path}, aggregations saved to {agg_path}")
            return final_df
            
        # Final step for chunked processing - merge intermediate files
        elif save_intermediates:
            # List all intermediate chunks
            chunk_files = sorted(config.DATA_DIR.glob("neos_chunk_*.parquet"))
            if chunk_files:
                # We could process these in chunks too if they're large
                merged_df = pd.concat([pd.read_parquet(f) for f in chunk_files], ignore_index=True)
                processor.save_to_parquet(merged_df, output_path)
                logger.info(f"Merged {len(chunk_files)} chunks into {output_path}")
                
                # Clean up intermediate files
                for file in chunk_files:
                    file.unlink()
                logger.info("Cleaned up intermediate chunk files")

    except Exception as e:
        logger.error(f"Error during data collection: {str(e)}")
        if not save_intermediates and chunk_dfs:
            # Try to save what we have in case of error
            rescue_path = config.DATA_DIR / "neos_rescue.parquet"
            rescue_df = pd.concat(chunk_dfs, ignore_index=True)
            processor.save_to_parquet(rescue_df, rescue_path)
            logger.info(f"Saved {len(rescue_df)} records to rescue file {rescue_path}")
        raise
    
    return None  # If we're using chunked processing


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Collect NASA Near Earth Object data')
    parser.add_argument('--limit', type=int, default=200,
                        help='Maximum number of NEOs to collect')
    parser.add_argument('--output', type=str, default=None,
                        help='Output path for the parquet file')
    parser.add_argument('--chunk-size', type=int, default=None,
                        help='Process data in chunks of this size')
    parser.add_argument('--save-intermediates', action='store_true',
                        help='Save intermediate results during processing')
    parser.add_argument('--job-id', type=str, default=None,
                        help='Job identifier (useful for cron jobs)')
    parser.add_argument('--log-level', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                        default='INFO', help='Set logging level')
    args = parser.parse_args()
    
    # Configure log level
    logger.setLevel(getattr(logging, args.log_level))
    logger.info(f"Log level set to {args.log_level}")
    
    # Generate job ID if not provided
    job_id = args.job_id or f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    output_path = Path(args.output) if args.output else None
    
    # Log system info
    import platform
    logger.info(f"System: {platform.system()} {platform.release()}, Python: {platform.python_version()}")
    logger.info(f"Job ID: {job_id}")
    logger.info(f"Starting data collection with limit={args.limit}, chunk_size={args.chunk_size}")
    
    start_time = time.time()
    
    try:
        df = collect_neos(
            limit=args.limit,
            output_path=output_path,
            chunk_size=args.chunk_size,
            save_intermediates=args.save_intermediates,
            job_id=job_id
        )
        
        elapsed = time.time() - start_time
        logger.info(f"Data collection completed in {elapsed:.2f} seconds")
        logger.info(f"Job {job_id} completed successfully")
        
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Job {job_id} failed after {elapsed:.2f} seconds: {str(e)}")
        logger.error(traceback.format_exc())
        raise
    
    # If we have an in-memory dataframe, print some summary stats
    if df is not None:
        logger.info(f"Collected {len(df)} records")
        logger.info(f"DataFrame memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        
        # Print the first few rows
        logger.info("\nSample data:")
        print(df.head())
        
        # Print aggregation results
        aggs = compute_aggregations(df)
        logger.info("\nAggregations:")
        logger.info(f"Approaches closer than 0.2 AU: {aggs['total_approaches_lt_0.2_AU']}")
        logger.info("Approaches per year:")
        for year, count in sorted(aggs['approaches_per_year'].items()):
            logger.info(f"  {year}: {count}")


if __name__ == "__main__":
    main()
