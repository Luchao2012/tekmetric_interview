# NASA Near Earth Object (NEO) Data Collection System

This documentation provides a comprehensive guide to the NASA NEO data collection system, including how to run various types of jobs, file structure information, and maintenance procedures.

## Table of Contents

1. [Overview](#overview)
2. [System Requirements](#system-requirements)
3. [Project Structure](#project-structure)
4. [Running Jobs](#running-jobs)
    - [One-time Local Collection](#one-time-local-collection)
    - [Scheduled Cron Jobs](#scheduled-cron-jobs)
    - [S3 Storage Integration](#s3-storage-integration)
5. [Maintenance Operations](#maintenance-operations)
    - [Cleaning Old Files](#cleaning-old-files)
    - [Data Management Best Practices](#data-management-best-practices)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)

## Overview

This system collects data about Near Earth Objects (NEOs) from NASA's public API. It includes features for data collection, processing, storage (both local and S3), and maintenance. The system is designed to be run as either one-time manual jobs or scheduled cron jobs.

Key features:
- Configurable data collection with adjustable limits
- Processing in chunks to manage memory usage
- Support for AWS S3 storage
- Comprehensive logging and error handling
- Maintenance utilities for managing old data files

## System Requirements

- Python 3.7+
- Required Python packages (install via `pip install -r requirements.txt`):
  - pandas
  - requests
  - boto3 (for S3 functionality)
  - python-dotenv
- NASA API key (obtain from [api.nasa.gov](https://api.nasa.gov/))
- (Optional) AWS credentials for S3 storage

## Project Structure

```
tekmetric_interview/
│
├── run.py               # Main CLI entry point for data collection
├── maintenance.py       # Utility for cleaning old data files
├── requirements.txt     # Python dependencies
├── cron_setup.md        # Cron job setup guide
│
├── src/                 # Source code modules
│   ├── __init__.py
│   ├── config.py        # Configuration settings
│   ├── api_client.py    # NASA API client 
│   ├── data_processor.py # Data processing utilities
│   ├── main.py          # Core collection logic
│   └── s3_utils.py      # S3 storage utilities
│
├── data/                # Data storage directory
│   └── neo/             # NEO data files
│       ├── neos_*.parquet # Collected data files
│       └── aggregations.json # Statistical aggregations
│
└── logs/                # Log files
    └── neo_collector_*.log # Date-based log files
```

## Running Jobs

### One-time Local Collection

To run a one-time data collection job that stores data locally:

```bash
python run.py --limit <number_of_records> --chunk-size <processing_chunk_size> --output <custom_filename>
```

#### Parameters:

- `--limit`: Number of NEO records to collect (default: 200)
- `--chunk-size`: Size of processing chunks to manage memory usage (default: 50)
- `--output`: Custom output filename without extension (default: "neos_{limit}")

#### Examples:

Basic collection with default settings:
```bash
python run.py
```

Collect 500 NEOs with a custom output name:
```bash
python run.py --limit 500 --output my_neo_data
```

Collect 1000 NEOs with larger chunk size for faster processing:
```bash
python run.py --limit 1000 --chunk-size 100 --output large_collection
```

### Scheduled Automated Data Collection

For automated data collection, the system supports scheduling with macOS Automator and Calendar:

```bash
python run.py --limit <number_of_records> --chunk-size <processing_chunk_size> --cron
```

The `--cron` flag adds:
- Timestamped filenames (e.g., `neos_200_cron_20250518_123456.parquet`)
- Status files recording job completion
- Separate timestamped aggregation files

#### Setting Up Scheduled Jobs with macOS Automator:

1. Open Automator and create a new Application
2. Add a "Run Shell Script" action
3. Paste the following script (adjust paths as needed):
   ```bash
   #!/bin/bash
   
   # Create timestamp for filenames
   TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
   
   # Change to project directory
   cd /Users/luchaojin/Documents/GitHub/tekmetric_interview
   
   # Use python directly from conda environment
   /Users/luchaojin/anaconda3/envs/nasa_neo_env/bin/python run.py --limit 200 --cron --output neo_data_${TIMESTAMP}
   ```

4. Save the application (e.g., as "RunNEOCollection")
5. Schedule with Calendar:
   - Open Calendar app
   - Create a new event at your desired time (e.g., 2:00 PM daily)
   - Add an alert with "Open file" and select your Automator app
   - Set the alert to occur "At time of event"
   - Set the event to repeat as needed (daily, weekly, monthly)

### S3 Storage Integration

The system can store data in Amazon S3 instead of or in addition to local storage:

```bash
python run.py --limit <number_of_records> --s3 --s3-bucket <bucket_name> [--no-local]
```

#### S3 Parameters:

- `--s3`: Enable S3 storage
- `--s3-bucket`: S3 bucket name (required when using --s3)
- `--s3-prefix`: S3 key prefix (default: "neo-data/")
- `--s3-region`: AWS region (default: from AWS_REGION env var)
- `--no-local`: Skip saving files locally (only save to S3)

#### S3 Examples:

Upload to S3 while keeping local copies:
```bash
python run.py --limit 200 --s3 --s3-bucket my-neo-data-bucket
```

Store data only in S3 (no local files):
```bash
python run.py --limit 500 --s3 --s3-bucket my-neo-data-bucket --no-local
```

Cron job with S3 storage:
```bash
python run.py --limit 200 --cron --s3 --s3-bucket my-neo-data-bucket --s3-prefix "daily-collections/"
```

## Maintenance Operations

### Cleaning Old Files

The system includes a maintenance utility for managing old data files:

```bash
python maintenance.py [--clean-logs <days>] [--clean-data <days>] [--clean-status <days>] [--archive] [--archive-dir <archive_directory>]
```

#### Maintenance Parameters:

- `--clean-logs <days>`: Delete logs older than specified days
- `--clean-data <days>`: Delete data files older than specified days
- `--clean-status <days>`: Delete status/error files older than specified days
- `--archive`: Move files to an archive directory instead of deleting
- `--archive-dir <archive_directory>`: Custom archive directory name (default: "archive")
- `--report`: Generate a report on data collection history

#### Maintenance Examples:

Delete data files older than 30 days:
```bash
python maintenance.py --clean-data 30
```

Archive logs older than 14 days instead of deleting:
```bash
python maintenance.py --clean-logs 14 --archive
```

Clean data files, logs, and status files older than 7 days:
```bash
python maintenance.py --clean-data 7 --clean-logs 7 --clean-status 7
```

### Data Management Best Practices

For optimal performance and disk usage:

1. **Schedule Regular Maintenance**: Set up a weekly maintenance job in Automator to clean or archive old files:
   
   Create a maintenance Automator app similar to the data collection app:
   ```bash
   #!/bin/bash
   
   # Create timestamp for log filename
   TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
   
   # Change to project directory
   cd /Users/luchaojin/Documents/GitHub/tekmetric_interview
   
   # Use python directly from conda environment
   /Users/luchaojin/anaconda3/envs/nasa_neo_env/bin/python maintenance.py --clean-data 30 --clean-logs 30 --clean-status 30 > /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs/maintenance_${TIMESTAMP}.log 2>&1
   ```
   
   Then schedule it in Calendar for weekly execution (e.g., every Saturday).

2. **Monitor Disk Usage**: Regularly check disk usage, especially if collecting large datasets

3. **Backup Strategy**: Consider implementing a backup strategy for important datasets before running maintenance operations

## Troubleshooting

Common issues and solutions:

### API Rate Limiting

The system automatically handles NASA API rate limits, but if you encounter persistent rate limit issues:

- Ensure your API key is valid
- Check for high concurrency in API usage
- Review logs for specific rate limit errors

### S3 Integration Issues

If experiencing problems with S3 storage:

- Verify AWS credentials are properly configured in environment variables
- Check bucket permissions and access policies
- Ensure the bucket exists in the specified region

### Error Messages

- **Missing API Key**: `NASA_API_KEY environment variable not found` - Add your API key to a `.env` file or environment variables
- **S3 Bucket Required**: `S3 bucket name is required when using --s3 flag` - Provide a bucket name with `--s3-bucket`
- **Bucket Not Found**: `S3 bucket not found or not accessible` - Verify bucket name and permissions

## Advanced Usage

### Configuration Customization

Advanced settings can be modified in `src/config.py`:

- `DEFAULT_BATCH_SIZE`: Number of NEOs per API request (currently 20)
- `DEFAULT_CHUNK_SIZE`: Default size for processing chunks (currently 100)
- `MAX_REQUESTS_PER_HOUR`: API rate limit control (currently 1000)

### Processing Customization

For optimal performance based on your environment:

- **Memory-constrained systems**: Use smaller chunk sizes (e.g., `--chunk-size 20`)
- **High-performance systems**: Increase chunk sizes for faster processing (e.g., `--chunk-size 200`)
- **Large collections**: Enable `save_intermediates` for fault tolerance when collecting large datasets

---

This documentation covers the essential aspects of the NASA NEO data collection system. For further assistance, consult the source code comments or contact the system administrator.
