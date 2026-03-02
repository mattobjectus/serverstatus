"""
storebucket.py

This script continuously uploads a local file to a Google Cloud Storage bucket.
It runs in an infinite loop, uploading the file every 5 seconds.

Environment Variables Required:
    - BUCKET_NAME: The name of the Google Cloud Storage bucket
    - BUCKET_FILE_PATH: The destination path/filename in the bucket
    - PROJECT_NAME: The Google Cloud project ID

Dependencies:
    - google-cloud-storage: Google Cloud Storage Python client library
    - python-dotenv: For loading environment variables from .env file
"""

from google.cloud import storage
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Infinite loop to continuously upload the file
while True:

    # Retrieve configuration from environment variables
    bucket_name = os.getenv("BUCKET_NAME")  # Name of the GCS bucket
    bucket_path = os.getenv("BUCKET_FILE_PATH")  # Destination path in the bucket
    project = os.getenv("PROJECT_NAME")  # Google Cloud project ID

    # Initialize the Google Cloud Storage client
    # Assumes authentication is set up via GOOGLE_APPLICATION_CREDENTIALS environment variable
    # or default credentials (gcloud auth application-default login)
    client = storage.Client(project=project)

    # Get a reference to the specified bucket
    bucket = client.get_bucket(bucket_name)

    # Create a blob object representing the file in the bucket
    # This is the destination path where the file will be stored
    blob = bucket.blob(bucket_path)

    # Upload the local file to the bucket
    # The file 'serviceChk_finprodcoredc2.txt' must exist in the current working directory
    blob.upload_from_filename('test/demo/serviceChk_finprodcoredc2.txt')
    
    # Log successful upload with the destination path
    print("File uploaded successfully: " + bucket_path)
    
    # Wait 5 seconds before the next upload iteration
    time.sleep(5)
