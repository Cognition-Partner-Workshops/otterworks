"""Audit archive logic, ported from etl/scripts/audit_archive_weekly.py.

The legacy behavior the goldens pin is reproduced on purpose and marked "legacy:": the string
cutoff filter, the DecimalEncoder, the archive layout and the hardcoded compliance fields.
Clients and tables are passed in (boto3 shapes, as returned by the provider hooks), so unit
tests use fakes and nothing here opens a connection on its own.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import time
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from botocore.exceptions import ClientError

# otterworks-audit-events is keyed on `id` alone (scripts/localstack-init.sh,
# infrastructure/terraform/modules/database/main.tf). Legacy deletes by {event_id, timestamp},
# which matches no key schema, so every one of its deletes fails.
KEY_ATTRIBUTE = "id"
MAX_DELETE_BATCH = 25  # DynamoDB BatchWriteItem limit
RESTORE_REQUEST = {"Days": 1, "GlacierJobParameters": {"Tier": "Expedited"}}


class ArchiveMismatchError(RuntimeError):
    """The archive read back from S3 is not the one this run uploaded."""


class ArchiveOverwriteError(RuntimeError):
    """An archive already at the key holds events the new archive would drop."""


class DecimalEncoder(json.JSONEncoder):
    """legacy: DynamoDB Decimals become int when integral, float otherwise, at any depth."""

    def default(self, o):
        if isinstance(o, Decimal):
            if o == int(o):
                return int(o)
            return float(o)
        return super().default(o)


def cutoff_date(ds: str, retention_days: int) -> str:
    """legacy: midnight of ``ds`` minus the retention, ISO with a literal ``Z``."""
    start = datetime.strptime(ds, "%Y-%m-%d") - timedelta(days=retention_days)
    return start.isoformat() + "Z"


def scan_kwargs(cutoff: str) -> dict[str, Any]:
    # legacy: a string comparison, not a time comparison. Spellings such as ".000Z" or "+00:00"
    # of the cutoff instant sort before it and are archived; numeric timestamps never match.
    return {
        "FilterExpression": "#ts < :cutoff",
        "ExpressionAttributeNames": {"#ts": "timestamp"},
        "ExpressionAttributeValues": {":cutoff": cutoff},
    }


def scan_events(table: Any, cutoff: str) -> list[dict[str, Any]]:
    """Every item matching the legacy filter, following ``LastEvaluatedKey``, in scan order."""
    kwargs = scan_kwargs(cutoff)
    events: list[dict[str, Any]] = []
    while True:
        response = table.scan(**kwargs)
        events.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return events
        kwargs["ExclusiveStartKey"] = last_key


def encode_events(events: Iterable[Mapping[str, Any]]) -> list[str]:
    """One archive line per event, exactly as legacy ``json.dumps(event, cls=DecimalEncoder)``."""
    return [json.dumps(event, cls=DecimalEncoder) for event in events]


def archive_key(prefix: str, ds: str) -> str:
    return f"{prefix}/year={ds[:4]}/week={ds}/audit_events.jsonl.gz"


def compress_lines(lines: Sequence[str]) -> bytes:
    """JSONL.gz as legacy writes it (line, then newline); mtime 0 so a retry is byte-identical."""
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        for line in lines:
            gz.write(line.encode("utf-8"))
            gz.write(b"\n")
    return buf.getvalue()


def decompress_lines(body: bytes) -> list[str]:
    text = gzip.decompress(body).decode("utf-8")
    return [line for line in text.split("\n") if line]


def sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def read_object(
    client: Any,
    bucket: str,
    key: str,
    *,
    timeout: float = 600.0,
    poll_seconds: float = 5.0,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> bytes:
    """Read an object back, restoring it first when its storage class is archival (GLACIER).

    Raises ``TimeoutError`` when the restore has not finished within ``timeout``; the task fails
    and its retry asks again (a restore already in progress is not an error).
    """
    try:
        return client.get_object(Bucket=bucket, Key=key)["Body"].read()
    except ClientError as exc:
        if _error_code(exc) != "InvalidObjectState":
            raise
    try:
        client.restore_object(Bucket=bucket, Key=key, RestoreRequest=RESTORE_REQUEST)
    except ClientError as exc:
        if _error_code(exc) != "RestoreAlreadyInProgress":
            raise
    deadline = clock() + timeout
    while 'ongoing-request="false"' not in (
        client.head_object(Bucket=bucket, Key=key).get("Restore") or ""
    ):
        if clock() > deadline:
            raise TimeoutError(f"restore of s3://{bucket}/{key} did not finish in {timeout}s")
        sleep(poll_seconds)
    return client.get_object(Bucket=bucket, Key=key)["Body"].read()


def existing_object(client: Any, bucket: str, key: str) -> bool:
    try:
        client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        if _error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise
    return True


def check_overwrite(existing_lines: Sequence[str], new_lines: Sequence[str]) -> None:
    """Refuse to replace an archive with one that drops any of its events.

    A re-run after a delete-enabled run scans fewer events; overwriting would lose the only copy
    of the deleted ones (etl/RUNBOOK.md 5.3). A retry of the same upload is a subset and passes.
    """
    dropped = set(existing_lines) - set(new_lines)
    if dropped:
        raise ArchiveOverwriteError(
            f"the existing archive holds {len(dropped)} event(s) the new scan does not; "
            "copy it aside (etl/RUNBOOK.md 5.3) before re-running this date"
        )


@dataclass(frozen=True)
class DeletePlan:
    keys: tuple[dict[str, Any], ...]
    skipped_without_id: int = 0
    kept_within_retention: int = 0


def _instant(value: Any) -> datetime | None:
    """A timestamp as an aware UTC instant (naive values are UTC), or None if unparseable."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def delete_plan(lines: Iterable[str], cutoff: str | None = None) -> DeletePlan:
    """Delete keys ``{"id": ...}`` for the archived events, de-duplicated, in archive order.

    Events without ``id`` cannot be addressed and are skipped and counted. With ``cutoff``,
    an archived event is deleted only when its timestamp is provably before the cutoff
    instant: the legacy string filter also archives same-instant spellings and offsets that
    are after it (cutoff_boundary golden); those stay in the table and are counted.
    """
    limit = _instant(cutoff) if cutoff is not None else None
    if cutoff is not None and limit is None:
        raise ValueError(f"cutoff {cutoff!r} is not an ISO timestamp")
    keys: dict[str, dict[str, Any]] = {}
    skipped = kept = 0
    for line in lines:
        event = json.loads(line)
        if not isinstance(event, dict) or event.get(KEY_ATTRIBUTE) is None:
            skipped += 1
            continue
        if limit is not None:
            instant = _instant(event.get("timestamp"))
            if instant is None or instant >= limit:
                kept += 1
                continue
        key = {KEY_ATTRIBUTE: event[KEY_ATTRIBUTE]}
        keys.setdefault(json.dumps(key, sort_keys=True), key)
    return DeletePlan(tuple(keys.values()), skipped, kept)


def verified_delete_plan(
    client: Any,
    bucket: str,
    key: str,
    expected_sha256: str,
    cutoff: str | None = None,
    **read_kwargs: Any,
) -> DeletePlan:
    """The delete plan built from the archive as S3 holds it, after checking it is this run's.

    Only events present in the uploaded archive can be deleted: a key that was never archived,
    or an archive replaced since the upload, never reaches DynamoDB.
    """
    body = read_object(client, bucket, key, **read_kwargs)
    actual = sha256_hex(body)
    if actual != expected_sha256:
        raise ArchiveMismatchError(
            f"s3://{bucket}/{key} sha256 {actual} is not the uploaded {expected_sha256}"
        )
    return delete_plan(decompress_lines(body), cutoff)


def check_key_schema(table: Any) -> None:
    """The delete addresses items by ``id`` only; refuse any other key schema."""
    schema = [(k["AttributeName"], k["KeyType"]) for k in table.key_schema]
    if schema != [(KEY_ATTRIBUTE, "HASH")]:
        raise ValueError(f"{table.name} key schema {schema} is not [({KEY_ATTRIBUTE!r}, 'HASH')]")


def chunks(items: Sequence[Any], size: int) -> Iterator[Sequence[Any]]:
    if size < 1:
        raise ValueError(f"batch size {size} < 1")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def delete_in_batches(
    table: Any,
    keys: Sequence[Mapping[str, Any]],
    batch_size: int,
    on_batch: Callable[[int, int], None] | None = None,
) -> int:
    """Delete ``keys`` in batches of ``batch_size`` (at most 25) and return how many were deleted.

    ``batch_writer`` resends unprocessed items; any other error propagates, so the task fails
    and its retry deletes the same archived keys again (deletes are idempotent).
    """
    if not 1 <= batch_size <= MAX_DELETE_BATCH:
        raise ValueError(f"batch size {batch_size} not in 1..{MAX_DELETE_BATCH}")
    deleted = 0
    for index, batch in enumerate(chunks(keys, batch_size)):
        with table.batch_writer() as writer:
            for key in batch:
                writer.delete_item(Key=dict(key))
        deleted += len(batch)
        if on_batch is not None:
            on_batch(index, len(batch))
    return deleted


def build_report(
    *,
    ds: str,
    generated_at: str,
    retention_days: int,
    cutoff: str,
    events_archived: int,
    events_deleted: int,
    bucket: str,
    key: str,
    storage_class: str,
    compressed_size: int,
) -> dict[str, Any]:
    """The legacy compliance report, field for field."""
    return {
        "report_type": "audit_archive_compliance",
        "execution_date": ds,
        "generated_at": generated_at,
        "retention_policy": {
            "retention_days": retention_days,
            "cutoff_date": cutoff,
        },
        "results": {
            "events_scanned": events_archived,
            "events_archived": events_archived,
            "events_deleted_from_source": events_deleted,
            "archive_location": f"s3://{bucket}/{key}",
            "archive_storage_class": storage_class,
            "compressed_size_bytes": compressed_size,
        },
        # legacy: hardcoded, not checked against anything. A real check is a compliance follow-up.
        "compliance": {
            "gdpr_compliant": True,
            "soc2_compliant": True,
            "data_encrypted_at_rest": True,
            "data_encrypted_in_transit": True,
        },
    }
