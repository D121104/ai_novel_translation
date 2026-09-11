import asyncio
from typing import Protocol
from urllib.parse import urlsplit

from minio import Minio

from src.core.config import Settings


class ObjectStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> str: ...

    async def get(self, path: str) -> bytes: ...


class MinioStorage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def put(self, key: str, data: bytes, content_type: str) -> str:
        def upload() -> str:
            from io import BytesIO

            client = Minio(
                self._settings.minio_endpoint,
                self._settings.minio_access_key,
                self._settings.minio_secret_key.get_secret_value(),
                secure=self._settings.minio_secure,
            )
            if not client.bucket_exists(self._settings.minio_bucket):
                client.make_bucket(self._settings.minio_bucket)
            client.put_object(
                self._settings.minio_bucket,
                key,
                BytesIO(data),
                len(data),
                content_type=content_type,
            )
            return f"s3://{self._settings.minio_bucket}/{key}"

        return await asyncio.to_thread(upload)

    async def get(self, path: str) -> bytes:
        def download() -> bytes:
            client = Minio(
                self._settings.minio_endpoint,
                self._settings.minio_access_key,
                self._settings.minio_secret_key.get_secret_value(),
                secure=self._settings.minio_secure,
            )
            parsed = urlsplit(path)
            bucket = parsed.netloc or self._settings.minio_bucket
            key = parsed.path.lstrip("/") if parsed.scheme == "s3" else path.lstrip("/")
            response = client.get_object(bucket, key)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()

        return await asyncio.to_thread(download)
