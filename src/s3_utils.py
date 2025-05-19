"""
S3 utility functions for the NEO data collection system.
This module provides functionality to save data to Amazon S3 storage.
"""
import os
import logging
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
import pandas as pd
import json
from io import StringIO, BytesIO

logger = logging.getLogger(__name__)

class S3Utils:
    def __init__(self, 
                 bucket_name=None, 
                 aws_access_key_id=None, 
                 aws_secret_access_key=None,
                 region_name=None):
        """
        Initialize S3 client with credentials.
        
        Args:
            bucket_name: The S3 bucket to use
            aws_access_key_id: AWS access key ID (if None, uses environment variables)
            aws_secret_access_key: AWS secret access key (if None, uses environment variables)
            region_name: AWS region (if None, uses environment variables)
        """
        self.bucket_name = bucket_name or os.environ.get('AWS_S3_BUCKET')
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id or os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=aws_secret_access_key or os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=region_name or os.environ.get('AWS_REGION', 'us-east-1')
        )
        logger.info(f"Initialized S3 client for bucket: {self.bucket_name}")

    def upload_file(self, file_path, s3_key=None):
        """
        Upload a local file to S3.
        
        Args:
            file_path: Local path to file
            s3_key: S3 object key (path in the bucket). If None, uses the filename.
            
        Returns:
            bool: True if file was uploaded, else False
        """
        if s3_key is None:
            s3_key = Path(file_path).name
            
        try:
            self.s3_client.upload_file(file_path, self.bucket_name, s3_key)
            logger.info(f"Uploaded {file_path} to s3://{self.bucket_name}/{s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload {file_path} to S3: {str(e)}")
            return False

    def upload_dataframe(self, df, s3_key, file_format='parquet'):
        """
        Upload a pandas DataFrame directly to S3 without saving locally first.
        
        Args:
            df: Pandas DataFrame to upload
            s3_key: S3 object key (path in the bucket)
            file_format: Format to save ('parquet' or 'csv')
            
        Returns:
            bool: True if dataframe was uploaded, else False
        """
        try:
            if file_format.lower() == 'parquet':
                buffer = BytesIO()
                df.to_parquet(buffer, index=False)
                buffer.seek(0)
            elif file_format.lower() == 'csv':
                buffer = StringIO()
                df.to_csv(buffer, index=False)
                buffer_value = buffer.getvalue()
                buffer = BytesIO(buffer_value.encode())
            else:
                raise ValueError(f"Unsupported format: {file_format}")
                
            self.s3_client.put_object(
                Body=buffer,
                Bucket=self.bucket_name,
                Key=s3_key
            )
            logger.info(f"Uploaded DataFrame to s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload DataFrame to S3: {str(e)}")
            return False
    
    def upload_json(self, data, s3_key):
        """
        Upload JSON data directly to S3.
        
        Args:
            data: Dictionary to upload as JSON
            s3_key: S3 object key (path in the bucket)
            
        Returns:
            bool: True if data was uploaded, else False
        """
        try:
            json_data = json.dumps(data)
            self.s3_client.put_object(
                Body=json_data,
                Bucket=self.bucket_name,
                Key=s3_key,
                ContentType='application/json'
            )
            logger.info(f"Uploaded JSON data to s3://{self.bucket_name}/{s3_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to upload JSON to S3: {str(e)}")
            return False
    
    def download_file(self, s3_key, local_path):
        """
        Download a file from S3 to local storage.
        
        Args:
            s3_key: S3 object key to download
            local_path: Local path to save file
            
        Returns:
            bool: True if file was downloaded, else False
        """
        try:
            self.s3_client.download_file(self.bucket_name, s3_key, local_path)
            logger.info(f"Downloaded s3://{self.bucket_name}/{s3_key} to {local_path}")
            return True
        except ClientError as e:
            logger.error(f"Failed to download {s3_key} from S3: {str(e)}")
            return False

    def list_objects(self, prefix=''):
        """
        List objects in the S3 bucket with given prefix.
        
        Args:
            prefix: S3 prefix to filter objects
            
        Returns:
            list: List of object keys
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix
            )
            if 'Contents' in response:
                return [obj['Key'] for obj in response['Contents']]
            return []
        except ClientError as e:
            logger.error(f"Failed to list objects in S3: {str(e)}")
            return []

    def check_bucket_exists(self):
        """
        Check if the configured bucket exists.
        
        Returns:
            bool: True if bucket exists, else False
        """
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            return True
        except ClientError:
            logger.error(f"Bucket {self.bucket_name} not found or not accessible")
            return False
