import shutil
from pathlib import Path
from typing import Protocol

import boto3
from botocore.client import BaseClient

from sensemu_runtime.config import RuntimeSettings


class ObjectTooLargeError(ValueError):
    pass


class ObjectStore(Protocol):
    def materialize(self, uri: str, destination: Path, max_bytes: int) -> None: ...


class LocalObjectStore:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path_for(self, uri: str) -> Path:
        if not uri.startswith("local://"):
            raise ValueError("对象地址不是本地存储地址")
        source = (self.root / uri.removeprefix("local://")).resolve()
        if not source.is_relative_to(self.root):
            raise ValueError("对象地址越界")
        return source

    def materialize(self, uri: str, destination: Path, max_bytes: int) -> None:
        source = self._path_for(uri)
        if not source.is_file():
            raise FileNotFoundError("对象不存在")
        if source.stat().st_size > max_bytes:
            raise ObjectTooLargeError("对象超过运行时大小限制")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


class S3ObjectStore:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.bucket = settings.object_storage_bucket
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
        )

    def _key_for(self, uri: str) -> str:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ValueError("对象地址不属于运行时存储桶")
        return uri.removeprefix(prefix)

    def materialize(self, uri: str, destination: Path, max_bytes: int) -> None:
        key = self._key_for(uri)
        metadata = self.client.head_object(Bucket=self.bucket, Key=key)
        if int(metadata["ContentLength"]) > max_bytes:
            raise ObjectTooLargeError("对象超过运行时大小限制")
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, key, str(destination))


def create_object_store(settings: RuntimeSettings) -> ObjectStore:
    if settings.object_storage_endpoint == "local://":
        return LocalObjectStore(settings.object_storage_local_path)
    return S3ObjectStore(settings)
