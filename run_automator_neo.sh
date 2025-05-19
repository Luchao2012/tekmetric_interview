#!/bin/bash

# Create timestamp for filenames
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create log directory if it doesn't exist
mkdir -p /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs

# Log start time
echo "Job started at $(date)" > /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs/neo_collection_${TIMESTAMP}.log

# Change to project directory
cd /Users/luchaojin/Documents/GitHub/tekmetric_interview

# Use python directly from conda environment
/Users/luchaojin/anaconda3/envs/nasa_neo_env/bin/python run.py --limit 200 --cron --output neo_data_${TIMESTAMP}

# Log completion
echo "Job completed at $(date)" >> /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs/neo_collection_${TIMESTAMP}.log
