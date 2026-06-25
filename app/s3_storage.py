import os
import logging
import boto3
from botocore.exceptions import ClientError
from typing import Optional

logger = logging.getLogger(__name__)

class S3FileRepository:
    """
    A file storage repository implementing file uploads and secure presigned URL generation.
    Stores unstructured binary files (like BOL docs, images, invoices) in Amazon S3.
    """
    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.environ.get("S3_BUCKET_NAME", "dispatch-private")
        self.s3_client = boto3.client("s3")

    def upload_file(self, file_key: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> bool:
        """
        Uploads raw file bytes to S3 at the specified key.
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_bytes,
                ContentType=content_type
            )
            logger.info(f"Successfully uploaded file to S3: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {file_key}: {e}")
            raise e

    def delete_file(self, file_key: str) -> bool:
        """
        Deletes a file from the S3 bucket.
        """
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            logger.info(f"Successfully deleted file from S3: {file_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {file_key}: {e}")
            raise e

    def generate_presigned_url(self, file_key: str, expiration_seconds: int = 3600, method: str = "get_object") -> Optional[str]:
        """
        Generates a secure, temporary pre-signed URL to read or write an S3 object directly.
        Methods: "get_object" (read), "put_object" (write)
        """
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod=method,
                Params={
                    "Bucket": self.bucket_name,
                    "Key": file_key
                },
                ExpiresIn=expiration_seconds
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate pre-signed URL for {file_key}: {e}")
            return None
