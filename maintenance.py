#!/usr/bin/env python3
"""
Utility script for maintaining the NEO data collection system.
This script provides functionality to rotate log files, clean up old data,
and generate reports on data collection history.
"""
import os
import sys
import glob
import argparse
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import json

# Add parent directory to path so we can import src modules
sys.path.append(str(Path(__file__).parent))
from src.config import DATA_DIR, LOG_DIR

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("maintenance")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="NEO Data Collection System Maintenance")
    parser.add_argument("--clean-logs", type=int, default=0, 
                       help="Delete logs older than specified days")
    parser.add_argument("--clean-data", type=int, default=0,
                       help="Delete timestamped data files older than specified days")
    parser.add_argument("--clean-status", type=int, default=0,
                       help="Delete status/error files older than specified days")
    parser.add_argument("--archive", action="store_true",
                       help="Archive old files instead of deleting them")
    parser.add_argument("--archive-dir", type=str, default="archive",
                       help="Directory to store archived files")
    parser.add_argument("--report", action="store_true",
                       help="Generate a report on data collection history")
    return parser.parse_args()

def clean_old_logs(days, archive=False, archive_dir="archive"):
    """Clean up log files older than the specified number of days."""
    if days <= 0:
        logger.info("Log cleanup skipped (days must be > 0)")
        return
        
    cutoff_date = datetime.now() - timedelta(days=days)
    logger.info(f"Cleaning log files older than {cutoff_date.strftime('%Y-%m-%d')}")
    
    # Create archive directory if needed
    archive_path = None
    if archive:
        archive_path = LOG_DIR.parent / archive_dir / "logs"
        archive_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Archiving logs to: {archive_path}")
    
    # Find and process log files
    log_files = list(LOG_DIR.glob("neo_collector_*.log*"))
    deleted_count = 0
    archived_count = 0
    
    for log_file in log_files:
        try:
            # Extract date from filename (neo_collector_YYYYMMDD.log)
            date_str = log_file.stem.split('_')[2].split('.')[0]
            file_date = datetime.strptime(date_str, '%Y%m%d')
            
            if file_date < cutoff_date:
                if archive and archive_path:
                    # Archive the file
                    shutil.copy2(log_file, archive_path / log_file.name)
                    archived_count += 1
                
                # Delete the original
                os.remove(log_file)
                deleted_count += 1
                
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not process log file {log_file}: {e}")
    
    logger.info(f"Log cleanup complete. Deleted: {deleted_count} files, Archived: {archived_count} files")

def clean_old_data(days, archive=False, archive_dir="archive"):
    """Clean up timestamped data files older than the specified number of days."""
    if days <= 0:
        logger.info("Data cleanup skipped (days must be > 0)")
        return
        
    cutoff_date = datetime.now() - timedelta(days=days)
    logger.info(f"Cleaning data files older than {cutoff_date.strftime('%Y-%m-%d')}")
    
    # Create archive directory if needed
    archive_path = None
    if archive:
        archive_path = DATA_DIR.parent / archive_dir / "data"
        archive_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Archiving data to: {archive_path}")
    
    # Find and process timestamp-based parquet files
    parquet_files = list(DATA_DIR.glob("neos_*_cron_*.parquet"))
    agg_files = list(DATA_DIR.glob("aggregations_*.json"))
    
    deleted_count = 0
    archived_count = 0
    
    for file_path in parquet_files + agg_files:
        try:
            # Extract timestamp from filename (contains YYYYMMDD_HHMMSS)
            filename = file_path.name
            if "_cron_" in filename:
                date_part = filename.split('_cron_')[1].split('.')[0]
            else:
                date_part = filename.split('_')[1].split('.')[0]
            
            # Try different date formats
            try:
                file_date = datetime.strptime(date_part, '%Y%m%d_%H%M%S')
            except ValueError:
                try:
                    # Try just the date portion
                    file_date = datetime.strptime(date_part[:8], '%Y%m%d')
                except ValueError:
                    raise ValueError(f"Could not parse date from {date_part}")
            
            if file_date < cutoff_date:
                if archive and archive_path:
                    # Archive the file
                    shutil.copy2(file_path, archive_path / file_path.name)
                    archived_count += 1
                
                # Delete the original
                os.remove(file_path)
                deleted_count += 1
                
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not process data file {file_path}: {e}")
    
    logger.info(f"Data cleanup complete. Deleted: {deleted_count} files, Archived: {archived_count} files")

def clean_old_status_files(days, archive=False, archive_dir="archive"):
    """Clean up status/error files older than the specified number of days."""
    if days <= 0:
        logger.info("Status file cleanup skipped (days must be > 0)")
        return
        
    cutoff_date = datetime.now() - timedelta(days=days)
    logger.info(f"Cleaning status/error files older than {cutoff_date.strftime('%Y-%m-%d')}")
    
    # Create archive directory if needed
    archive_path = None
    if archive:
        archive_path = DATA_DIR.parent / archive_dir / "status"
        archive_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Archiving status files to: {archive_path}")
    
    # Find and process status/error files
    status_files = list(DATA_DIR.glob("status_*.txt"))
    error_files = list(DATA_DIR.glob("error_*.txt"))
    
    deleted_count = 0
    archived_count = 0
    
    for status_file in status_files + error_files:
        try:
            # Extract date from filename (status_YYYYMMDD.txt)
            date_str = status_file.stem.split('_')[1]
            file_date = datetime.strptime(date_str, '%Y%m%d')
            
            if file_date < cutoff_date:
                if archive and archive_path:
                    # Archive the file
                    shutil.copy2(status_file, archive_path / status_file.name)
                    archived_count += 1
                
                # Delete the original
                os.remove(status_file)
                deleted_count += 1
                
        except (ValueError, IndexError) as e:
            logger.warning(f"Could not process status file {status_file}: {e}")
    
    logger.info(f"Status file cleanup complete. Deleted: {deleted_count} files, Archived: {archived_count} files")

def generate_report():
    """Generate a report on data collection history."""
    logger.info("Generating data collection history report...")
    
    # Find all status files
    status_files = list(DATA_DIR.glob("status_*.txt"))
    error_files = list(DATA_DIR.glob("error_*.txt"))
    
    # Collect run statistics
    runs = []
    for status_file in status_files:
        with open(status_file, 'r') as f:
            for line in f:
                timestamp, message = line.split(': ', 1)
                success = True
                runs.append({
                    'timestamp': timestamp,
                    'date': timestamp.split('T')[0],
                    'success': success,
                    'message': message.strip()
                })
                
    for error_file in error_files:
        with open(error_file, 'r') as f:
            for line in f:
                timestamp, message = line.split(': ', 1)
                success = False
                runs.append({
                    'timestamp': timestamp,
                    'date': timestamp.split('T')[0],
                    'success': success,
                    'message': message.strip()
                })
    
    # Sort by timestamp
    runs.sort(key=lambda x: x['timestamp'])
    
    # Count successes and failures by date
    date_stats = {}
    for run in runs:
        date = run['date']
        if date not in date_stats:
            date_stats[date] = {'success': 0, 'failure': 0}
            
        if run['success']:
            date_stats[date]['success'] += 1
        else:
            date_stats[date]['failure'] += 1
    
    # Print report
    print("\nNEO Data Collection History Report")
    print("=================================")
    print(f"Total runs: {len(runs)}")
    print(f"Successful runs: {sum(1 for run in runs if run['success'])}")
    print(f"Failed runs: {sum(1 for run in runs if not run['success'])}")
    print("\nRuns by date:")
    print("------------")
    
    for date in sorted(date_stats.keys()):
        stats = date_stats[date]
        print(f"{date}: {stats['success']} successful, {stats['failure']} failed")
    
    print("\nLatest 5 runs:")
    print("-------------")
    for run in runs[-5:]:
        status = "SUCCESS" if run['success'] else "FAILED"
        print(f"{run['timestamp']} - {status} - {run['message']}")
    
    # Write report to file
    report_path = DATA_DIR.parent / "collection_report.txt"
    with open(report_path, 'w') as f:
        f.write("NEO Data Collection History Report\n")
        f.write("=================================\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write(f"Total runs: {len(runs)}\n")
        f.write(f"Successful runs: {sum(1 for run in runs if run['success'])}\n")
        f.write(f"Failed runs: {sum(1 for run in runs if not run['success'])}\n\n")
        
        f.write("Runs by date:\n")
        for date in sorted(date_stats.keys()):
            stats = date_stats[date]
            f.write(f"{date}: {stats['success']} successful, {stats['failure']} failed\n")
        
        f.write("\nAll runs:\n")
        for run in runs:
            status = "SUCCESS" if run['success'] else "FAILED"
            f.write(f"{run['timestamp']} - {status} - {run['message']}\n")
    
    logger.info(f"Report generated and saved to {report_path}")
    print(f"\nFull report saved to {report_path}")

def main():
    args = parse_args()
    
    if args.clean_logs > 0:
        clean_old_logs(args.clean_logs, args.archive, args.archive_dir)
        
    if args.clean_data > 0:
        clean_old_data(args.clean_data, args.archive, args.archive_dir)
        
    if args.clean_status > 0:
        clean_old_status_files(args.clean_status, args.archive, args.archive_dir)
        
    if args.report:
        generate_report()
        
    if not (args.clean_logs > 0 or args.clean_data > 0 or args.clean_status > 0 or args.report):
        print("No actions specified. Use --help to see available options.")

if __name__ == "__main__":
    main()
