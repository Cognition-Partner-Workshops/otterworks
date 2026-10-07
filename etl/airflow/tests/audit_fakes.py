"""In-memory DynamoDB table and S3 client with the boto3 shapes the audit archive uses."""

from __future__ import annotations

import io

from botocore.exceptions import ClientError


def _error(code: str, op: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": code}}, op)


class FakeWriter:
    def __init__(self, table):
        self.table = table
        self.keys = []

    def __enter__(self):
        return self

    def delete_item(self, Key):
        self.keys.append(Key)

    def __exit__(self, exc_type, exc, tb):
        if exc_type is not None:
            return False
        self.table.flush(self.keys)
        return False


class FakeTable:
    """Items in insertion order; scan pages of ``page_size`` with the legacy string filter.

    ``fail_flush`` lists flush indexes that, once each, delete the first half of their batch
    and then raise, like a BatchWriteItem that dies part way through.
    """

    def __init__(self, items, page_size=10, key_schema=None, name="otterworks-audit-events"):
        self.items = [dict(i) for i in items]
        self.page_size = page_size
        self.key_schema = key_schema or [{"AttributeName": "id", "KeyType": "HASH"}]
        self.name = name
        self.fail_flush = set()
        self.flushes = 0
        self.deleted_keys = []
        self.batches = []

    def ids(self):
        return [i.get("id") for i in self.items]

    def scan(self, FilterExpression, ExpressionAttributeNames, ExpressionAttributeValues, **kw):
        assert FilterExpression == "#ts < :cutoff"
        attr = ExpressionAttributeNames["#ts"]
        cutoff = ExpressionAttributeValues[":cutoff"]
        start = kw.get("ExclusiveStartKey", {}).get("_pos", 0)
        page = self.items[start : start + self.page_size]
        matched = [dict(i) for i in page if isinstance(i.get(attr), str) and i[attr] < cutoff]
        response = {"Items": matched}
        if start + self.page_size < len(self.items):
            response["LastEvaluatedKey"] = {"_pos": start + self.page_size}
        return response

    def batch_writer(self):
        return FakeWriter(self)

    def flush(self, keys):
        index = self.flushes
        self.flushes += 1
        self.batches.append(len(keys))
        if len(keys) > 25:
            raise _error("ValidationException", "BatchWriteItem")
        if index in self.fail_flush:
            self.fail_flush.discard(index)
            self._delete(keys[: len(keys) // 2])
            raise _error("ProvisionedThroughputExceededException", "BatchWriteItem")
        self._delete(keys)

    def _delete(self, keys):
        for key in keys:
            assert set(key) == {"id"}, key
            self.deleted_keys.append(key["id"])
            self.items = [i for i in self.items if i.get("id") != key["id"]]


class FakeS3Client:
    """Objects in GLACIER cannot be read until restored; a restore completes after
    ``restore_polls`` head_object calls."""

    def __init__(self, restore_polls=1):
        self.objects = {}
        self.restore_polls = restore_polls
        self.restores = []

    def put(self, bucket, key, body, storage_class="STANDARD"):
        self.objects[(bucket, key)] = {"body": body, "class": storage_class, "restore": None}

    def head_object(self, Bucket, Key):
        obj = self.objects.get((Bucket, Key))
        if obj is None:
            raise _error("404", "HeadObject")
        out = {"StorageClass": obj["class"]}
        if obj["restore"] is not None:
            obj["restore"] -= 1
            done = obj["restore"] <= 0
            out["Restore"] = 'ongoing-request="%s"' % ("false" if done else "true")
        return out

    def get_object(self, Bucket, Key):
        obj = self.objects.get((Bucket, Key))
        if obj is None:
            raise _error("NoSuchKey", "GetObject")
        if obj["class"] == "GLACIER" and (obj["restore"] is None or obj["restore"] > 0):
            raise _error("InvalidObjectState", "GetObject")
        return {"Body": io.BytesIO(obj["body"])}

    def restore_object(self, Bucket, Key, RestoreRequest):
        obj = self.objects[(Bucket, Key)]
        self.restores.append(Key)
        if obj["restore"] is not None and obj["restore"] > 0:
            raise _error("RestoreAlreadyInProgress", "RestoreObject")
        if obj["restore"] is None:
            obj["restore"] = self.restore_polls
