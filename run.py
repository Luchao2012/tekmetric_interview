"""
CLI script for running the NEO data collection process.
Supports both manual execution and scheduled cron jobs with configurable parameters.
Includes support for saving data to Amazon S3 storage.
"""
import os
import sys
import logging
import time
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path so we can import src modules
# Make sure the path is added to sys.path first so imports work correctly
project_root = str(Path(__file__).parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    
from src.main import collect_neos
from src.config import DATA_DIR, LOG_FILE
from src.s3_utils import S3Utils

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="NASA NEO Data Collection Script")
    parser.add_argument("--limit", type=int, default=200, 
                        help="Number of NEOs to collect (default: 200)")
    parser.add_argument("--chunk-size", type=int, default=50,
                        help="Size of processing chunks (default: 50)")
    parser.add_argument("--cron", action="store_true", 
                        help="Flag to indicate running as a cron job")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output filename (without extension)")
                        
    # S3 storage options
    parser.add_argument("--s3", action="store_true", 
                        help="Upload data to S3 storage")
    parser.add_argument("--s3-bucket", type=str, 
                        help="S3 bucket name (required if --s3 is used)")
    parser.add_argument("--s3-prefix", type=str, default="neo-data/", 
                        help="S3 key prefix (default: 'neo-data/')")
    parser.add_argument("--s3-region", type=str, 
                        help="AWS region (default: from AWS_REGION env var)")
    parser.add_argument("--no-local", action="store_true", 
                        help="Skip saving files locally (only save to S3)")
                        
    return parser.parse_args()

def run_collection():
    """Run the data collection process."""
    # Parse command line arguments
    args = parse_args()
    limit = args.limit
    is_cron = args.cron
    
    # Set up timestamp for this run
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Set up a job ID for this run
    job_id = f"{'cron' if is_cron else 'manual'}_{timestamp}"
    
    print(f"NASA Near Earth Object Data Collection - Job ID: {job_id}")
    print("=====================================================")
    print(f"Logs will be written to: {LOG_FILE}")
    
    logger = logging.getLogger("run")
    logger.info(f"Starting collection job: {job_id}, limit={limit} objects")
    
    # Determine output filename
    if args.output:
        # User-specified output name
        output_filename = f"{args.output}.parquet"
    elif is_cron:
        # For cron jobs, include date in filename
        output_filename = f"neos_{limit}_cron_{timestamp}.parquet"
    else:
        # Standard naming
        output_filename = f"neos_{limit}.parquet"
    
    output_path = DATA_DIR / output_filename
    
    start_time = time.time()
    
    # Initialize S3 if needed
    s3_utils = None
    if args.s3:
        if not args.s3_bucket:
            logger.error("S3 bucket name is required when using --s3 flag")
            print("Error: S3 bucket name is required when using --s3 flag")
            return
        
        # Initialize S3Utils with provided bucket and region
        s3_utils = S3Utils(
            bucket_name=args.s3_bucket,
            region_name=args.s3_region
        )
        
        # Check if bucket exists
        if not s3_utils.check_bucket_exists():
            logger.error(f"S3 bucket '{args.s3_bucket}' not found or not accessible")
            print(f"Error: S3 bucket '{args.s3_bucket}' not found or not accessible")
            return
            
        logger.info(f"Will upload data to S3 bucket: {args.s3_bucket}")
        print(f"Will upload data to S3 bucket: {args.s3_bucket}")
    
    # If --no-local flag is set but no S3 flag, warn user
    if args.no_local and not args.s3:
        logger.warning("--no-local flag used without --s3, ignoring and saving locally")
        args.no_local = False
    
    # Skip local output if --no-local is set
    final_output_path = None if args.no_local else output_path
    
    # Collect NEOs with specified limit
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting collection of {limit} NEOs...")
    logger.info(f"Beginning NEO data collection of {limit} objects to {output_path if not args.no_local else 'S3 only'}")
    
    try:
        df = collect_neos(
            limit=limit,
            output_path=final_output_path,
            chunk_size=args.chunk_size,
            save_intermediates=not args.no_local,
            job_id=job_id
        )
        
        elapsed = time.time() - start_time
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Data collection complete in {elapsed:.2f} seconds!")
        logger.info(f"Collection completed successfully in {elapsed:.2f}s")
        
        if not args.no_local:
            print(f"Data saved to: {output_path}")
        
        # Upload to S3 if requested
        if s3_utils:
            s3_base_key = args.s3_prefix.rstrip('/') + '/'
            s3_data_key = s3_base_key + output_filename
            
            if args.no_local:
                # Upload DataFrame directly to S3
                logger.info(f"Uploading DataFrame directly to S3: {s3_data_key}")
                success = s3_utils.upload_dataframe(df, s3_data_key, file_format='parquet')
            else:
                # Upload local file to S3
                logger.info(f"Uploading local file to S3: {s3_data_key}")
                success = s3_utils.upload_file(output_path, s3_data_key)
                
            if success:
                print(f"Data uploaded to S3: s3://{args.s3_bucket}/{s3_data_key}")
                logger.info(f"Data uploaded to S3: s3://{args.s3_bucket}/{s3_data_key}")
            else:
                print("Error uploading data to S3, see logs for details")
        
        # For cron jobs, use timestamped aggregation files
        if is_cron:
            agg_filename = f"aggregations_{timestamp}.json"
            agg_path = DATA_DIR / agg_filename
            
            # Import here to avoid circular imports
            import json
            
            # Create a copy of the aggregations with timestamp
            default_agg_path = DATA_DIR / "aggregations.json"
            
            # Save locally if not skipping local
            if not args.no_local:
                import shutil
                if os.path.exists(default_agg_path):
                    shutil.copy2(default_agg_path, agg_path)
                    logger.info(f"Created timestamped copy of aggregations at {agg_path}")
                print(f"Aggregations saved to: {default_agg_path} and {agg_path}")
            else:
                print("Skipping local aggregation file save (--no-local flag used)")
            
            # Upload aggregations to S3 if requested
            if s3_utils:
                with open(default_agg_path, 'r') as f:
                    aggs_data = json.load(f)
                
                # Upload both the standard and timestamped versions
                s3_agg_key = s3_base_key + "aggregations.json"
                s3_ts_agg_key = s3_base_key + agg_filename
                
                agg_success = s3_utils.upload_json(aggs_data, s3_agg_key)
                ts_agg_success = s3_utils.upload_json(aggs_data, s3_ts_agg_key)
                
                if agg_success and ts_agg_success:
                    print(f"Aggregations uploaded to S3: s3://{args.s3_bucket}/{s3_agg_key}")
                    print(f"Timestamped aggregations: s3://{args.s3_bucket}/{s3_ts_agg_key}")
                    logger.info(f"Uploaded aggregations to S3: {s3_agg_key} and {s3_ts_agg_key}")
        else:
            agg_path = DATA_DIR / "aggregations.json"
            
            if not args.no_local:
                print(f"Aggregations saved to: {agg_path}")
            
            # Upload aggregations to S3 if requested
            if s3_utils:
                with open(agg_path, 'r') as f:
                    aggs_data = json.load(f)
                
                s3_agg_key = s3_base_key + "aggregations.json"
                agg_success = s3_utils.upload_json(aggs_data, s3_agg_key)
                if agg_success:
                    print(f"Aggregations uploaded to S3: s3://{args.s3_bucket}/{s3_agg_key}")
                    logger.info(f"Uploaded aggregations to S3: {s3_agg_key}")
        
        # Load and print aggregations
        import json
        with open(DATA_DIR / "aggregations.json", 'r') as f:
            aggs = json.load(f)
            
        logger.info(f"Loaded aggregations: {len(aggs.get('approaches_per_year', {}))} years of data")
        
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"Error during collection after {elapsed:.2f}s: {str(e)}"
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {error_msg}")
        logger.error(error_msg)
        logger.exception("Exception details:")
        return
    
    print("\n---- Aggregation Results ----")
    print(f"Total approaches less than 0.2 AU: {aggs['total_approaches_lt_0.2_AU']}")
    print("Approaches per year:")
    for year, count in sorted(aggs['approaches_per_year'].items()):
        print(f"  {year}: {count}")


if __name__ == "__main__":
    try:
        # Parse arguments before running
        args = parse_args()
        
        # Initialize S3 client if needed for later use with status files
        s3_utils = None
        if args.s3 and args.s3_bucket:
            s3_utils = S3Utils(
                bucket_name=args.s3_bucket,
                region_name=args.s3_region
            )
        
        # Run collection process
        run_collection()
        
        # If running as a cron job, create a status file to indicate successful completion
        if args.cron:
            status_filename = f"status_{datetime.now().strftime('%Y%m%d')}.txt"
            status_path = DATA_DIR / status_filename
            status_message = f"{datetime.now().isoformat()}: Successfully collected {args.limit} NEOs\n"
            
            # Save locally if not skipping local files
            if not args.no_local:
                with open(status_path, 'a') as f:
                    f.write(status_message)
                    
            # Upload status to S3 if requested
            if s3_utils:
                s3_base_key = args.s3_prefix.rstrip('/') + '/'
                s3_status_key = s3_base_key + f"status/{status_filename}"
                
                # If file exists locally, upload it; otherwise upload just the string
                if not args.no_local and os.path.exists(status_path):
                    s3_utils.upload_file(status_path, s3_status_key)
                else:
                    # Upload the status message directly
                    s3_utils.s3_client.put_object(
                        Body=status_message,
                        Bucket=args.s3_bucket,
                        Key=s3_status_key
                    )
                logger.info(f"Uploaded status file to S3: {s3_status_key}")
            
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
        logger = logging.getLogger("run")
        logger.warning("Process was interrupted by user (KeyboardInterrupt)")
        
    except Exception as e:
        print(f"\nError during data collection: {str(e)}")
        print("Check logs for details.")
        
        logger = logging.getLogger("run")
        logger.critical(f"Unhandled exception in main process: {str(e)}", exc_info=True)
        
        # If running as a cron job, create a status file to indicate failure
        try:
            args = parse_args()
            if args.cron:
                error_filename = f"error_{datetime.now().strftime('%Y%m%d')}.txt"
                error_path = DATA_DIR / error_filename
                error_message = f"{datetime.now().isoformat()}: Error: {str(e)}\n"
                
                # Save locally if not skipping local files
                if not getattr(args, 'no_local', False):  # Use getattr in case args wasn't initialized
                    with open(error_path, 'a') as f:
                        f.write(error_message)
                
                # Upload error to S3 if requested
                if getattr(args, 's3', False) and getattr(args, 's3_bucket', None):
                    s3_utils = S3Utils(
                        bucket_name=args.s3_bucket,
                        region_name=getattr(args, 's3_region', None)
                    )
                    s3_base_key = getattr(args, 's3_prefix', 'neo-data/').rstrip('/') + '/'
                    s3_error_key = s3_base_key + f"status/{error_filename}"
                    
                    try:
                        # If file exists locally, upload it; otherwise upload just the string
                        if not getattr(args, 'no_local', False) and os.path.exists(error_path):
                            s3_utils.upload_file(error_path, s3_error_key)
                        else:
                            # Upload the error message directly
                            s3_utils.s3_client.put_object(
                                Body=error_message,
                                Bucket=args.s3_bucket,
                                Key=s3_error_key
                            )
                        logger.info(f"Uploaded error file to S3: {s3_error_key}")
                    except Exception as s3_error:
                        logger.error(f"Failed to upload error to S3: {str(s3_error)}")
        except Exception as inner_e:
            logger.error(f"Error creating error status file: {str(inner_e)}")
