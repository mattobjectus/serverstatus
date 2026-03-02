from google.cloud import storage
import time
import os
from dotenv import load_dotenv
load_dotenv()

while True:

    bucket_name= os.getenv("BUCKET_NAME")
    bucket_path= os.getenv("BUCKET_FILE_PATH")
    project= os.getenv("PROJECT_NAME")

    print("BUCKET: "+bucket_name)

    # Initialize the client (assumes authentication is set up)
    client = storage.Client(project=project)

    # Get the bucket
    bucket = client.get_bucket(bucket_name)

    # Create a blob object for the file in the bucket
    blob = bucket.blob(bucket_path)  # Destination path in the bucket

    # Upload the local file
    blob.upload_from_filename('serviceChk_finprodcoredc2.txt')  # Local file path
    
    print("File uploaded successfully: "+bucket_path)
    time.sleep(5)