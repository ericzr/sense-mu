from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from sensemu_api.storage import S3Storage


class StubS3Client:
    def __init__(self, error: ClientError | None = None) -> None:
        self.error = error

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        del Bucket, Key
        if self.error:
            raise self.error
        return {"Body": BytesIO(b"report")}


def client_error(code: str, status_code: int) -> ClientError:
    return ClientError(
        {
            "Error": {"Code": code, "Message": code},
            "ResponseMetadata": {"HTTPStatusCode": status_code},
        },
        "GetObject",
    )


def storage_with(client: StubS3Client) -> S3Storage:
    storage = S3Storage.__new__(S3Storage)
    storage.bucket = "sensemu-test"
    storage.client = client
    return storage


@pytest.mark.parametrize("code", ["NoSuchKey", "NotFound", "404"])
def test_s3_get_bytes_maps_missing_objects_to_file_not_found(code: str) -> None:
    storage = storage_with(StubS3Client(client_error(code, 404)))

    with pytest.raises(FileNotFoundError):
        storage.get_bytes("s3://sensemu-test/runs/one/metrics/results.csv")


def test_s3_get_bytes_preserves_non_missing_client_errors() -> None:
    error = client_error("AccessDenied", 403)
    storage = storage_with(StubS3Client(error))

    with pytest.raises(ClientError) as caught:
        storage.get_bytes("s3://sensemu-test/runs/one/metrics/results.csv")

    assert caught.value is error
