"""
Amazon S3 Storage Backend for PyPhotoOrganizer.

Implements the StorageBackend interface for Amazon S3, enabling cloud storage
of photos and videos in S3 buckets.

Features:
- Multipart upload for large files
- Retry logic with exponential backoff
- Hash verification using S3 checksums
- Support for different storage classes (Standard, Intelligent-Tiering, Glacier)
- Range requests for partial file reads

Requirements:
    pip install boto3

Usage:
    from storage_backend_s3 import S3StorageBackend

    backend = S3StorageBackend(
        bucket='my-photo-archive',
        prefix='photos',
        region='us-west-2'
    )

    # Upload a file
    backend.copy_from_local('/path/to/photo.jpg', '2024/01/photo.jpg')

    # Check if exists
    if backend.exists('2024/01/photo.jpg'):
        print("File exists in S3")
"""

import hashlib
import io
import logging
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO, Dict, Iterator, Optional, Tuple

from storage_backend import StorageBackend, FileInfo, StorageProviderRegistry

logger = logging.getLogger(__name__)

# Check if boto3 is available
try:
    import boto3
    from botocore.config import Config as BotoConfig
    from botocore.exceptions import ClientError, BotoCoreError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed. S3 storage backend will not be available.")


# Default configuration values
DEFAULT_MULTIPART_THRESHOLD = 8 * 1024 * 1024  # 8 MB
DEFAULT_MULTIPART_CHUNKSIZE = 8 * 1024 * 1024  # 8 MB
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_DELAY = 1.0  # seconds
DEFAULT_RETRY_BACKOFF = 2.0  # exponential backoff multiplier

# S3 storage classes
STORAGE_CLASS_STANDARD = 'STANDARD'
STORAGE_CLASS_INTELLIGENT_TIERING = 'INTELLIGENT_TIERING'
STORAGE_CLASS_STANDARD_IA = 'STANDARD_IA'
STORAGE_CLASS_ONEZONE_IA = 'ONEZONE_IA'
STORAGE_CLASS_GLACIER_IR = 'GLACIER_IR'
STORAGE_CLASS_GLACIER = 'GLACIER'
STORAGE_CLASS_DEEP_ARCHIVE = 'DEEP_ARCHIVE'


@dataclass
class S3Config:
    """Configuration for S3 storage backend."""
    bucket: str
    prefix: str = ''
    region: str = 'us-east-1'
    credentials_profile: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    endpoint_url: Optional[str] = None  # For S3-compatible services
    storage_class: str = STORAGE_CLASS_INTELLIGENT_TIERING
    multipart_threshold: int = DEFAULT_MULTIPART_THRESHOLD
    multipart_chunksize: int = DEFAULT_MULTIPART_CHUNKSIZE
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS
    retry_delay: float = DEFAULT_RETRY_DELAY
    retry_backoff: float = DEFAULT_RETRY_BACKOFF


class S3StorageBackend(StorageBackend):
    """
    Amazon S3 storage backend implementation.

    Supports all standard StorageBackend operations with S3-specific optimizations
    like multipart uploads and storage class selection.
    """

    def __init__(self,
                 bucket: str,
                 prefix: str = '',
                 region: str = 'us-east-1',
                 credentials_profile: Optional[str] = None,
                 access_key: Optional[str] = None,
                 secret_key: Optional[str] = None,
                 endpoint_url: Optional[str] = None,
                 storage_class: str = STORAGE_CLASS_INTELLIGENT_TIERING,
                 multipart_threshold: int = DEFAULT_MULTIPART_THRESHOLD,
                 multipart_chunksize: int = DEFAULT_MULTIPART_CHUNKSIZE,
                 max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
                 retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
                 retry_delay: float = DEFAULT_RETRY_DELAY,
                 retry_backoff: float = DEFAULT_RETRY_BACKOFF,
                 **kwargs):
        """
        Initialize S3 storage backend.

        Args:
            bucket: S3 bucket name
            prefix: Optional prefix (folder) for all objects
            region: AWS region (default: us-east-1)
            credentials_profile: AWS credentials profile name
            access_key: AWS access key (alternative to profile)
            secret_key: AWS secret key (alternative to profile)
            endpoint_url: Custom endpoint URL for S3-compatible services
            storage_class: Default storage class for uploaded objects
            multipart_threshold: Size threshold for multipart uploads
            multipart_chunksize: Chunk size for multipart uploads
            max_concurrency: Max concurrent upload threads
            retry_attempts: Number of retry attempts for failed operations
            retry_delay: Initial delay between retries (seconds)
            retry_backoff: Exponential backoff multiplier
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required for S3 storage backend. "
                "Install with: pip install boto3"
            )

        self._bucket = bucket
        self._prefix = prefix.strip('/') if prefix else ''
        self._region = region
        self._storage_class = storage_class
        self._multipart_threshold = multipart_threshold
        self._multipart_chunksize = multipart_chunksize
        self._max_concurrency = max_concurrency
        self._retry_attempts = retry_attempts
        self._retry_delay = retry_delay
        self._retry_backoff = retry_backoff
        self._endpoint_url = endpoint_url

        # Configure boto3 client
        boto_config = BotoConfig(
            region_name=region,
            retries={
                'max_attempts': retry_attempts,
                'mode': 'adaptive'
            }
        )

        # Create session with credentials
        if credentials_profile:
            session = boto3.Session(profile_name=credentials_profile)
        elif access_key and secret_key:
            session = boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key
            )
        else:
            # Use default credential chain
            session = boto3.Session()

        # Create S3 client
        client_kwargs = {
            'config': boto_config
        }
        if endpoint_url:
            client_kwargs['endpoint_url'] = endpoint_url

        self._s3 = session.client('s3', **client_kwargs)
        self._s3_resource = session.resource('s3', **client_kwargs)

        logger.info(f"S3StorageBackend initialized: bucket={bucket}, prefix={prefix}, region={region}")

    @property
    def storage_type(self) -> str:
        return 's3'

    @property
    def base_path(self) -> str:
        """Return S3 URI for this backend."""
        if self._prefix:
            return f"s3://{self._bucket}/{self._prefix}"
        return f"s3://{self._bucket}"

    @property
    def bucket(self) -> str:
        """Return the bucket name."""
        return self._bucket

    @property
    def prefix(self) -> str:
        """Return the prefix."""
        return self._prefix

    def _full_key(self, path: str) -> str:
        """Convert relative path to full S3 key."""
        # Normalize path separators to forward slashes
        path = path.replace('\\', '/').strip('/')
        if self._prefix:
            return f"{self._prefix}/{path}"
        return path

    def _retry_operation(self, operation, *args, **kwargs):
        """
        Execute an operation with retry logic.

        Args:
            operation: Callable to execute
            *args, **kwargs: Arguments to pass to operation

        Returns:
            Result of the operation

        Raises:
            Last exception if all retries fail
        """
        last_exception = None
        delay = self._retry_delay

        for attempt in range(self._retry_attempts):
            try:
                return operation(*args, **kwargs)
            except (ClientError, BotoCoreError) as e:
                last_exception = e
                error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', '')

                # Don't retry client errors (4xx) except throttling
                if error_code and error_code.startswith('4') and error_code not in ('429', 'SlowDown', 'Throttling'):
                    raise

                if attempt < self._retry_attempts - 1:
                    logger.warning(f"S3 operation failed (attempt {attempt + 1}/{self._retry_attempts}): {e}")
                    time.sleep(delay)
                    delay *= self._retry_backoff

        raise last_exception

    def exists(self, path: str) -> bool:
        """Check if object exists in S3."""
        key = self._full_key(path)
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

    def get_size(self, path: str) -> int:
        """Get object size in bytes."""
        key = self._full_key(path)
        try:
            response = self._s3.head_object(Bucket=self._bucket, Key=key)
            return response['ContentLength']
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"Object not found: {path}")
            raise

    def get_file_info(self, path: str) -> Optional[FileInfo]:
        """Get object metadata."""
        key = self._full_key(path)
        try:
            response = self._s3.head_object(Bucket=self._bucket, Key=key)
            return FileInfo(
                path=path,
                size=response['ContentLength'],
                modified_time=response['LastModified'],
                content_hash=response.get('ETag', '').strip('"'),
                storage_type='s3'
            )
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return None
            raise

    def read_file(self, path: str) -> bytes:
        """Read entire object into memory."""
        key = self._full_key(path)
        try:
            response = self._retry_operation(
                self._s3.get_object,
                Bucket=self._bucket,
                Key=key
            )
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"Object not found: {path}")
            raise

    def read_file_stream(self, path: str) -> BinaryIO:
        """Get object as a readable stream."""
        key = self._full_key(path)
        try:
            response = self._retry_operation(
                self._s3.get_object,
                Bucket=self._bucket,
                Key=key
            )
            return response['Body']
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"Object not found: {path}")
            raise

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        """Read a range of bytes from object using S3 range requests."""
        key = self._full_key(path)

        # Handle negative offset (from end)
        if offset < 0:
            # Get file size first
            size = self.get_size(path)
            offset = size + offset
            if offset < 0:
                offset = 0

        # Construct range header
        range_header = f"bytes={offset}-{offset + length - 1}"

        try:
            response = self._retry_operation(
                self._s3.get_object,
                Bucket=self._bucket,
                Key=key,
                Range=range_header
            )
            return response['Body'].read()
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"Object not found: {path}")
            raise

    def write_file(self, path: str, data: bytes) -> bool:
        """Write data to S3 object."""
        key = self._full_key(path)

        extra_args = {
            'StorageClass': self._storage_class
        }

        try:
            if len(data) >= self._multipart_threshold:
                # Use multipart upload for large data
                return self._multipart_upload_bytes(key, data, extra_args)
            else:
                self._retry_operation(
                    self._s3.put_object,
                    Bucket=self._bucket,
                    Key=key,
                    Body=data,
                    **extra_args
                )
            return True
        except Exception as e:
            logger.error(f"Failed to write to S3: {e}")
            raise

    def write_file_stream(self, path: str, stream: BinaryIO, size: int) -> bool:
        """Write stream to S3 object."""
        key = self._full_key(path)

        extra_args = {
            'StorageClass': self._storage_class
        }

        try:
            if size >= self._multipart_threshold:
                return self._multipart_upload_stream(key, stream, size, extra_args)
            else:
                data = stream.read(size)
                self._retry_operation(
                    self._s3.put_object,
                    Bucket=self._bucket,
                    Key=key,
                    Body=data,
                    **extra_args
                )
            return True
        except Exception as e:
            logger.error(f"Failed to write stream to S3: {e}")
            raise

    def _multipart_upload_bytes(self, key: str, data: bytes, extra_args: dict) -> bool:
        """Upload large data using multipart upload."""
        # Create multipart upload
        response = self._s3.create_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            **extra_args
        )
        upload_id = response['UploadId']

        try:
            parts = []
            offset = 0
            part_number = 1

            while offset < len(data):
                chunk = data[offset:offset + self._multipart_chunksize]
                offset += len(chunk)

                response = self._retry_operation(
                    self._s3.upload_part,
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk
                )

                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                })
                part_number += 1

            # Complete multipart upload
            self._s3.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return True

        except Exception as e:
            # Abort multipart upload on failure
            try:
                self._s3.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id
                )
            except Exception:
                pass
            raise

    def _multipart_upload_stream(self, key: str, stream: BinaryIO,
                                  size: int, extra_args: dict) -> bool:
        """Upload stream using multipart upload."""
        # Create multipart upload
        response = self._s3.create_multipart_upload(
            Bucket=self._bucket,
            Key=key,
            **extra_args
        )
        upload_id = response['UploadId']

        try:
            parts = []
            part_number = 1
            bytes_uploaded = 0

            while bytes_uploaded < size:
                chunk_size = min(self._multipart_chunksize, size - bytes_uploaded)
                chunk = stream.read(chunk_size)
                if not chunk:
                    break

                response = self._retry_operation(
                    self._s3.upload_part,
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    Body=chunk
                )

                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['ETag']
                })
                part_number += 1
                bytes_uploaded += len(chunk)

            # Complete multipart upload
            self._s3.complete_multipart_upload(
                Bucket=self._bucket,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return True

        except Exception as e:
            # Abort multipart upload on failure
            try:
                self._s3.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=key,
                    UploadId=upload_id
                )
            except Exception:
                pass
            raise

    def copy_from_local(self, local_path: str, remote_path: str,
                        preserve_metadata: bool = True) -> bool:
        """Upload local file to S3."""
        key = self._full_key(remote_path)

        extra_args = {
            'StorageClass': self._storage_class
        }

        file_size = os.path.getsize(local_path)

        try:
            if file_size >= self._multipart_threshold:
                # Use multipart upload for large files
                return self._multipart_upload_file(local_path, key, extra_args)
            else:
                # Simple upload for small files
                with open(local_path, 'rb') as f:
                    self._retry_operation(
                        self._s3.put_object,
                        Bucket=self._bucket,
                        Key=key,
                        Body=f.read(),
                        **extra_args
                    )

            logger.debug(f"Uploaded {local_path} -> s3://{self._bucket}/{key}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload to S3: {e}")
            raise

    def _multipart_upload_file(self, local_path: str, key: str, extra_args: dict) -> bool:
        """Upload file using multipart upload."""
        # Use boto3's managed transfer for efficient multipart upload
        from boto3.s3.transfer import TransferConfig

        config = TransferConfig(
            multipart_threshold=self._multipart_threshold,
            multipart_chunksize=self._multipart_chunksize,
            max_concurrency=self._max_concurrency,
            use_threads=True
        )

        self._s3_resource.Bucket(self._bucket).upload_file(
            local_path,
            key,
            ExtraArgs=extra_args,
            Config=config
        )
        return True

    def copy_to_local(self, remote_path: str, local_path: str) -> bool:
        """Download S3 object to local filesystem."""
        key = self._full_key(remote_path)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        try:
            # Use managed transfer for efficient download
            from boto3.s3.transfer import TransferConfig

            config = TransferConfig(
                multipart_threshold=self._multipart_threshold,
                multipart_chunksize=self._multipart_chunksize,
                max_concurrency=self._max_concurrency,
                use_threads=True
            )

            self._s3_resource.Bucket(self._bucket).download_file(
                key,
                local_path,
                Config=config
            )

            logger.debug(f"Downloaded s3://{self._bucket}/{key} -> {local_path}")
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"Object not found: {remote_path}")
            raise

    def copy(self, source: str, dest: str) -> bool:
        """Copy object within S3."""
        source_key = self._full_key(source)
        dest_key = self._full_key(dest)

        copy_source = {
            'Bucket': self._bucket,
            'Key': source_key
        }

        try:
            # Check file size to determine if multipart copy is needed
            size = self.get_size(source)

            if size >= self._multipart_threshold:
                # Use multipart copy for large objects
                return self._multipart_copy(copy_source, dest_key, size)
            else:
                self._retry_operation(
                    self._s3.copy_object,
                    CopySource=copy_source,
                    Bucket=self._bucket,
                    Key=dest_key,
                    StorageClass=self._storage_class
                )

            logger.debug(f"Copied s3://{self._bucket}/{source_key} -> {dest_key}")
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise FileNotFoundError(f"Source object not found: {source}")
            raise

    def _multipart_copy(self, copy_source: dict, dest_key: str, size: int) -> bool:
        """Copy large object using multipart copy."""
        # Create multipart upload
        response = self._s3.create_multipart_upload(
            Bucket=self._bucket,
            Key=dest_key,
            StorageClass=self._storage_class
        )
        upload_id = response['UploadId']

        try:
            parts = []
            part_number = 1
            offset = 0

            while offset < size:
                end = min(offset + self._multipart_chunksize - 1, size - 1)

                response = self._retry_operation(
                    self._s3.upload_part_copy,
                    Bucket=self._bucket,
                    Key=dest_key,
                    UploadId=upload_id,
                    PartNumber=part_number,
                    CopySource=copy_source,
                    CopySourceRange=f"bytes={offset}-{end}"
                )

                parts.append({
                    'PartNumber': part_number,
                    'ETag': response['CopyPartResult']['ETag']
                })
                part_number += 1
                offset = end + 1

            # Complete multipart upload
            self._s3.complete_multipart_upload(
                Bucket=self._bucket,
                Key=dest_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            return True

        except Exception as e:
            try:
                self._s3.abort_multipart_upload(
                    Bucket=self._bucket,
                    Key=dest_key,
                    UploadId=upload_id
                )
            except Exception:
                pass
            raise

    def move(self, source: str, dest: str) -> bool:
        """Move object within S3 (copy then delete)."""
        # S3 doesn't have native move, so copy then delete
        if self.copy(source, dest):
            return self.delete(source)
        return False

    def delete(self, path: str) -> bool:
        """Delete object from S3."""
        key = self._full_key(path)

        try:
            self._retry_operation(
                self._s3.delete_object,
                Bucket=self._bucket,
                Key=key
            )
            logger.debug(f"Deleted s3://{self._bucket}/{key}")
            return True
        except ClientError:
            return False

    def makedirs(self, path: str) -> bool:
        """
        Create directory structure (no-op for S3).

        S3 doesn't have real directories - they're implied by object keys.
        This method exists for interface compatibility.
        """
        # S3 doesn't need directory creation
        return True

    def list_files(self, prefix: str = '') -> Iterator[FileInfo]:
        """List objects with the given prefix."""
        full_prefix = self._full_key(prefix) if prefix else self._prefix

        paginator = self._s3.get_paginator('list_objects_v2')

        for page in paginator.paginate(Bucket=self._bucket, Prefix=full_prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']

                # Convert back to relative path
                if self._prefix:
                    rel_path = key[len(self._prefix):].lstrip('/')
                else:
                    rel_path = key

                yield FileInfo(
                    path=rel_path,
                    size=obj['Size'],
                    modified_time=obj['LastModified'],
                    content_hash=obj.get('ETag', '').strip('"'),
                    storage_type='s3'
                )

    def compute_hash(self, path: str, algorithm: str = 'sha256') -> str:
        """
        Compute hash of S3 object.

        Downloads the object in chunks to compute hash without loading
        entire file into memory.
        """
        key = self._full_key(path)

        hasher = hashlib.new(algorithm)

        try:
            response = self._retry_operation(
                self._s3.get_object,
                Bucket=self._bucket,
                Key=key
            )

            # Stream the body and hash in chunks
            for chunk in response['Body'].iter_chunks(chunk_size=65536):
                hasher.update(chunk)

            return hasher.hexdigest()

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"Object not found: {path}")
            raise

    def get_presigned_url(self, path: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for temporary access.

        Args:
            path: Relative path to object
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL string
        """
        key = self._full_key(path)

        url = self._s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': self._bucket,
                'Key': key
            },
            ExpiresIn=expiration
        )
        return url

    def set_storage_class(self, path: str, storage_class: str) -> bool:
        """
        Change the storage class of an existing object.

        Args:
            path: Relative path to object
            storage_class: Target storage class

        Returns:
            True if successful
        """
        key = self._full_key(path)

        try:
            self._retry_operation(
                self._s3.copy_object,
                CopySource={'Bucket': self._bucket, 'Key': key},
                Bucket=self._bucket,
                Key=key,
                StorageClass=storage_class,
                MetadataDirective='COPY'
            )
            return True
        except Exception as e:
            logger.error(f"Failed to change storage class: {e}")
            return False

    def get_storage_class(self, path: str) -> Optional[str]:
        """
        Get the storage class of an object.

        Args:
            path: Relative path to object

        Returns:
            Storage class string or None if not found
        """
        key = self._full_key(path)

        try:
            response = self._s3.head_object(Bucket=self._bucket, Key=key)
            return response.get('StorageClass', STORAGE_CLASS_STANDARD)
        except ClientError:
            return None


def register_s3_backend():
    """Register S3 backend with the StorageProviderRegistry."""
    if BOTO3_AVAILABLE:
        StorageProviderRegistry.register('s3', S3StorageBackend)
        logger.info("S3 storage backend registered")
    else:
        logger.warning("Cannot register S3 backend: boto3 not available")


# Auto-register when module is imported
if BOTO3_AVAILABLE:
    register_s3_backend()


if __name__ == '__main__':
    """Test S3 backend (requires AWS credentials and bucket)."""
    import sys

    if not BOTO3_AVAILABLE:
        print("boto3 not installed. Install with: pip install boto3")
        sys.exit(1)

    print("S3 Storage Backend Module")
    print("=" * 50)
    print(f"boto3 available: {BOTO3_AVAILABLE}")
    print(f"Registered providers: {StorageProviderRegistry.get_available_providers()}")
    print()
    print("To test with a real bucket:")
    print("  backend = S3StorageBackend(bucket='your-bucket', region='us-west-2')")
    print("  backend.write_file('test.txt', b'Hello S3!')")
    print("  print(backend.read_file('test.txt'))")
