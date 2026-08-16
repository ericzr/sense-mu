import json
import os
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError

from sensemu_api.config import get_settings


class Storage(Protocol):
    bucket: str

    def presign_put(
        self,
        key: str,
        content_type: str,
        checksum_sha256: str,
        expires_in: int = 900,
    ) -> str: ...

    def uri_for(self, key: str) -> str: ...

    def verify_object(self, key: str, byte_size: int, checksum_sha256: str) -> bool: ...

    def put_json(self, key: str, payload: dict[str, Any]) -> str: ...

    def get_bytes(self, uri: str) -> bytes: ...

    def get_json(self, uri: str) -> dict[str, Any]: ...

    def put_bytes(self, key: str, payload: bytes, content_type: str = "application/octet-stream") -> str: ...

    def check_ready(self) -> None: ...


class S3Storage:
    def __init__(self) -> None:
        settings = get_settings()
        self.bucket = settings.object_storage_bucket
        self.client: BaseClient = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
            region_name=settings.object_storage_region,
        )

    def presign_put(
        self,
        key: str,
        content_type: str,
        checksum_sha256: str,
        expires_in: int = 900,
    ) -> str:
        return self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
                "Metadata": {"sha256": checksum_sha256},
            },
            ExpiresIn=expires_in,
        )

    def uri_for(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    def verify_object(self, key: str, byte_size: int, checksum_sha256: str) -> bool:
        try:
            metadata = self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return False
        return (
            metadata.get("ContentLength") == byte_size
            and metadata.get("Metadata", {}).get("sha256") == checksum_sha256
        )

    def put_json(self, key: str, payload: dict[str, Any]) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(),
            ContentType="application/json",
        )
        return self.uri_for(key)

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=payload,
            ContentType=content_type,
            Metadata={"sha256": sha256(payload).hexdigest()},
        )
        return self.uri_for(key)

    def get_json(self, uri: str) -> dict[str, Any]:
        return json.loads(self.get_bytes(uri))

    def get_bytes(self, uri: str) -> bytes:
        prefix = f"s3://{self.bucket}/"
        if not uri.startswith(prefix):
            raise ValueError("对象地址不属于当前存储桶")
        key = uri.removeprefix(prefix)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code in {"NoSuchKey", "NotFound", "404"} or status_code == 404:
                raise FileNotFoundError(f"对象不存在: {key}") from error
            raise
        return response["Body"].read()

    def check_ready(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


class LocalStorage:
    """Development-only adapter preserving the production presigned-upload contract."""

    bucket = "sensemu-local"

    def __init__(self) -> None:
        settings = get_settings()
        if settings.environment != "development":
            raise RuntimeError("Local object storage is only available in development")
        self.root = Path(settings.object_storage_local_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.api_public_url = settings.api_public_url.rstrip("/")

    def path_for(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Object key escapes local storage root")
        return path

    def presign_put(
        self,
        key: str,
        content_type: str,
        checksum_sha256: str,
        expires_in: int = 900,
    ) -> str:
        del content_type, checksum_sha256, expires_in
        return f"{self.api_public_url}/api/v1/dev-storage/{quote(key, safe='/')}"

    def uri_for(self, key: str) -> str:
        return f"local://{key}"

    def verify_object(self, key: str, byte_size: int, checksum_sha256: str) -> bool:
        path = self.path_for(key)
        if not path.is_file() or path.stat().st_size != byte_size:
            return False
        digest = sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest() == checksum_sha256

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        del content_type
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return self.uri_for(key)

    def put_json(self, key: str, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        return self.put_bytes(key, body)

    def get_json(self, uri: str) -> dict[str, Any]:
        return json.loads(self.get_bytes(uri))

    def get_bytes(self, uri: str) -> bytes:
        if not uri.startswith("local://"):
            raise ValueError("对象地址不是本地存储地址")
        return self.path_for(uri.removeprefix("local://")).read_bytes()

    def check_ready(self) -> None:
        if not self.root.is_dir() or not os.access(self.root, os.R_OK | os.W_OK):
            raise OSError("本地对象存储目录不可读写")


@lru_cache
def get_storage() -> Storage:
    if get_settings().object_storage_endpoint == "local://":
        return LocalStorage()
    return S3Storage()
