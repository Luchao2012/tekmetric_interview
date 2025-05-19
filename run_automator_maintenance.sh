#!/bin/bash

# Create timestamp for log filename
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Create log directory if it doesn't exist
mkdir -p /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs

# Log start time
echo "Maintenance job started at $(date)" > /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs/maintenance_${TIMESTAMP}.log

# Change to project directory
cd /Users/luchaojin/Documents/GitHub/tekmetric_interview

# Use python directly from conda environment
/Users/luchaojin/anaconda3/envs/nasa_neo_env/bin/python maintenance.py --clean-data 30 --clean-logs 30 --clean-status 30 >> /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs/maintenance_${TIMESTAMP}.log 2>&1

# Log completion
echo "Maintenance job completed at $(date)" >> /Users/luchaojin/Documents/GitHub/tekmetric_interview/logs/maintenance_${TIMESTAMP}.log
