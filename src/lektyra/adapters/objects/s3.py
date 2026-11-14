"""lektyra's own MinIO (compose.yaml) through the S3 API, for pictures (ADR-015). boto3.

Any S3-compatible store works: the address, the login and the bucket come from settings. Path-style addressing,
because a store on localhost has no per-bucket host names. Every failure becomes a LektyraError, so the API answers
in its one shape and never with a stack trace.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Final

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from lektyra.errors import LektyraError

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client

UNREACHABLE: Final = "The picture store (lektyra's MinIO) is not reachable. Start it with: docker compose up -d"
MISSING: Final = ("NoSuchKey", "NoSuchBucket", "404", "NotFound")


def _code(err: ClientError) -> str:
    return str(err.response.get("Error", {}).get("Code", ""))


class S3Objects:
    def __init__(self, url: str, user: str, password: str, bucket: str) -> None:
        self._bucket = bucket
        self._client: S3Client = boto3.client(
            "s3",
            endpoint_url=url,
            aws_access_key_id=user,
            aws_secret_access_key=password,
            region_name="us-east-1",
            config=Config(
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=20,
                retries={"max_attempts": 2},
            ),
        )

    def _call[T](self, action: Callable[[], T], missing: str = "Not in the picture store.") -> T:
        try:
            return action()
        except ClientError as err:
            if _code(err) in MISSING:
                raise LektyraError("not_found", missing) from err
            raise LektyraError("unavailable", f"The picture store refused: {_code(err) or 'unknown error'}.") from err
        except BotoCoreError as err:
            raise LektyraError("unavailable", UNREACHABLE) from err

    def ensure_bucket(self) -> bool:
        """Create the bucket on first use. True when it was created."""
        try:
            self._call(lambda: self._client.head_bucket(Bucket=self._bucket))
            return False
        except LektyraError as err:
            if err.code != "not_found":
                raise
        self._call(lambda: self._client.create_bucket(Bucket=self._bucket))
        return True

    def put(self, key: str, data: bytes, content_type: str) -> None:
        def write() -> None:
            self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)

        try:
            self._call(write)
        except LektyraError as err:
            if err.code != "not_found":  # the first picture ever: no bucket yet
                raise
            self.ensure_bucket()
            self._call(write)

    def get(self, key: str) -> bytes:
        answer = self._call(lambda: self._client.get_object(Bucket=self._bucket, Key=key), "This picture is gone.")
        body: bytes = self._call(lambda: answer["Body"].read())
        return body

    def delete(self, key: str) -> None:
        try:
            self._call(lambda: self._client.delete_object(Bucket=self._bucket, Key=key))
        except LektyraError as err:
            if err.code != "not_found":
                raise

    def keys(self, prefix: str) -> list[str]:
        def collect() -> list[str]:
            pages = self._client.get_paginator("list_objects_v2").paginate(Bucket=self._bucket, Prefix=prefix)
            return [key for page in pages for o in page.get("Contents", []) if (key := o.get("Key")) is not None]

        try:
            return self._call(collect)
        except LektyraError as err:
            if err.code == "not_found":  # no bucket yet: nothing stored
                return []
            raise
