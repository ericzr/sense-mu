import json
import shutil
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol

import boto3
from botocore.client import BaseClient

from sensemu_worker.config import WorkerSettings


class ObjectStore(Protocol):
    def read_json(self, uri: str) -> dict[str, Any]: ...

    def materialize(self, uri: str, destination: Path) -> None: ...

    def upload(
        self,
        source: Path,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str: ...


class LocalObjectStore:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()

    def _path_for(self, uri: str) -> Path:
        if not uri.startswith("local://"):
            raise ValueError("非本地对象地址")
        path = (self.root / uri.removeprefix("local://")).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("对象地址越界")
        return path

    def read_json(self, uri: str) -> dict[str, Any]:
        return json.loads(self._path_for(uri).read_text())

    def materialize(self, uri: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self._path_for(uri), destination)

    def upload(
        self,
        source: Path,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        del content_type
        destination = (self.root / key).resolve()
        if not destination.is_relative_to(self.root):
            raise ValueError("产物地址越界")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        return f"local://{key}"


class S3ObjectStore:
    def __init__(self, settings: WorkerSettings) -> None:
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
            raise ValueError("对象地址不属于当前存储桶")
        return uri.removeprefix(prefix)

    def read_json(self, uri: str) -> dict[str, Any]:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key_for(uri))
        return json.loads(response["Body"].read())

    def materialize(self, uri: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        self.client.download_file(self.bucket, self._key_for(uri), str(destination))

    def upload(
        self,
        source: Path,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        self.client.upload_file(
            str(source),
            self.bucket,
            key,
            ExtraArgs={
                "ContentType": content_type,
                "Metadata": {"sha256": _file_sha256(source)},
            },
        )
        return f"s3://{self.bucket}/{key}"


def create_object_store(settings: WorkerSettings) -> ObjectStore:
    if settings.object_storage_endpoint == "local://":
        return LocalObjectStore(settings.object_storage_local_path)
    return S3ObjectStore(settings)


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
