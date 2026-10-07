"""In-memory S3 (S3Hook method shapes) and DynamoDB table for the storage cleanup tests."""

from __future__ import annotations

from datetime import UTC, datetime

from botocore.exceptions import ClientError


def _error(code: str, op: str, status: int = 400) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": code}, "ResponseMetadata": {"HTTPStatusCode": status}},
        op,
    )


class FakeS3:
    """Buckets of {key: {"body", "metadata"}}. ``fail_copy`` / ``fail_delete`` are keys whose
    copy or delete raises; ``short_copy`` keys are copied truncated (a bad copy)."""

    def __init__(self, *buckets):
        self.buckets = {b: {} for b in buckets}
        self.fail_copy = set()
        self.fail_delete = set()
        self.short_copy = set()
        self.calls = []

    def put(self, bucket, key, body=b"", metadata=None):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.buckets[bucket][key] = {"body": body, "metadata": dict(metadata or {})}

    def keys(self, bucket):
        return sorted(self.buckets[bucket])

    # S3Hook methods
    def get_file_metadata(self, prefix, bucket_name=None, page_size=None, max_items=None):
        stamp = datetime(2026, 6, 1, 1, 0, tzinfo=UTC)
        return [
            {"Key": k, "Size": len(v["body"]), "LastModified": stamp}
            for k, v in sorted(self.buckets[bucket_name].items())
            if k.startswith(prefix)
        ]

    def head_object(self, key, bucket_name=None):
        self.calls.append(("head", bucket_name, key))
        if bucket_name not in self.buckets:
            return None
        obj = self.buckets[bucket_name].get(key)
        return None if obj is None else {"ContentLength": len(obj["body"])}

    def copy_object(
        self,
        source_bucket_key,
        dest_bucket_key,
        source_bucket_name=None,
        dest_bucket_name=None,
        **kwargs,
    ):
        self.calls.append(("copy", source_bucket_name, source_bucket_key, dest_bucket_key))
        assert kwargs == {"MetadataDirective": "COPY"}, kwargs
        if dest_bucket_name not in self.buckets:
            raise _error("NoSuchBucket", "CopyObject", 404)
        if source_bucket_key in self.fail_copy:
            raise _error("SlowDown", "CopyObject", 503)
        src = self.buckets[source_bucket_name][source_bucket_key]
        body = src["body"][:-1] if source_bucket_key in self.short_copy else src["body"]
        self.buckets[dest_bucket_name][dest_bucket_key] = {**src, "body": body}

    def delete_objects(self, bucket, keys):
        keys = [keys] if isinstance(keys, str) else keys
        self.calls.append(("delete", bucket, tuple(keys)))
        for key in keys:
            if key in self.fail_delete:
                self.fail_delete.discard(key)
                raise RuntimeError(f"Errors when deleting: [{key!r}]")
            self.buckets[bucket].pop(key, None)

    def load_bytes(self, bytes_data, key, bucket_name=None, replace=False):
        self.put(bucket_name, key, bytes_data)

    def get_key(self, key, bucket_name=None):
        body = self.buckets[bucket_name][key]["body"]

        class _Obj:
            def get(self):
                import io

                return {"Body": io.BytesIO(body)}

        return _Obj()

    def list_keys(self, bucket_name=None, prefix=""):
        return [k for k in self.buckets[bucket_name] if k.startswith(prefix)]


class FakeTable:
    """Scan pages of ``page_size`` items, projecting ``s3_key`` like the real table."""

    def __init__(self, items, page_size=3, name="otterworks-file-metadata"):
        self.items = [dict(i) for i in items]
        self.page_size = page_size
        self.name = name
        self.scans = []

    def scan(self, ProjectionExpression, **kw):
        assert ProjectionExpression == "s3_key"
        self.scans.append(kw.get("ExclusiveStartKey"))
        start = kw.get("ExclusiveStartKey", {}).get("_pos", 0)
        page = self.items[start : start + self.page_size]
        response = {"Items": [{"s3_key": i["s3_key"]} if "s3_key" in i else {} for i in page]}
        if start + self.page_size < len(self.items):
            response["LastEvaluatedKey"] = {"_pos": start + self.page_size}
        return response
