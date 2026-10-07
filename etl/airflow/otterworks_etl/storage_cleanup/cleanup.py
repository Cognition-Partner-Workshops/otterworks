"""Storage cleanup logic, ported from etl/scripts/storage_cleanup_daily.py.

The legacy behavior the goldens pin is reproduced on purpose and marked "legacy:": exact-string
matching of metadata ``s3_key`` values (unless normalization is switched on), the
``<prefix>/<ds>/<key>`` quarantine layout, and the report fields and rounding. Hooks and tables
are passed in, so unit tests use fakes and nothing here opens a connection on its own.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from otterworks_etl.common import get_logger, log_event

GIB = 1024**3

logger = get_logger(__name__)


class QuarantineHook(Protocol):
    """The ``S3Hook`` methods the quarantine uses."""

    def head_object(self, key: str, bucket_name: str | None = ...) -> dict | None: ...

    def copy_object(
        self,
        source_bucket_key: str,
        dest_bucket_key: str,
        source_bucket_name: str | None = ...,
        dest_bucket_name: str | None = ...,
        **kwargs: Any,
    ) -> Any: ...

    def delete_objects(self, bucket: str, keys: str | list) -> None: ...


def object_record(content: Mapping[str, Any]) -> dict[str, Any]:
    """A ``list_objects_v2`` ``Contents`` entry as legacy keeps it."""
    last_modified = content.get("LastModified")
    return {
        "key": content["Key"],
        "size": int(content["Size"]),
        "last_modified": last_modified.isoformat()
        if hasattr(last_modified, "isoformat")
        else last_modified,
    }


def scan_references(table: Any) -> list[Any]:
    """Every item's ``s3_key`` (projection only), following ``LastEvaluatedKey``."""
    kwargs: dict[str, Any] = {"ProjectionExpression": "s3_key"}
    values: list[Any] = []
    while True:
        response = table.scan(**kwargs)
        values.extend(item.get("s3_key", "") for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return values
        kwargs["ExclusiveStartKey"] = last_key


def referenced_keys(values: Iterable[Any]) -> list[str]:
    """legacy: every non-empty ``s3_key``, deduplicated.

    Only strings are kept: a numeric ``s3_key`` can never equal an object key, so dropping it
    matches nothing legacy would have matched.
    """
    return sorted({v for v in values if isinstance(v, str) and v})


def normalize_reference(reference: str, file_storage_bucket: str) -> str:
    """Strip an ``s3://<file storage bucket>/`` prefix or one leading ``/``. Never folds case:
    S3 keys are case-sensitive, so two keys that differ only by case can be two real files."""
    uri_prefix = f"s3://{file_storage_bucket}/"
    if reference.startswith(uri_prefix):
        return reference[len(uri_prefix) :]
    if reference.startswith("/"):
        return reference[1:]
    return reference


@dataclass(frozen=True)
class OrphanResult:
    orphans: list[dict[str, Any]]
    orphaned_bytes: int
    # References that match no object as written but match one once normalized.
    normalizable_references: int


def find_orphans(
    objects: Sequence[Mapping[str, Any]],
    references: Iterable[str],
    *,
    normalize: bool,
    file_storage_bucket: str,
) -> OrphanResult:
    """Objects no reference points at, in listing order.

    ``normalize=False`` is legacy exact-string matching; ``normalize=True`` also matches a
    reference after ``normalize_reference``.
    """
    exact = set(references)
    object_keys = {o["key"] for o in objects}
    normalized = {normalize_reference(r, file_storage_bucket) for r in exact}
    normalizable = sum(
        1
        for r in exact
        if r not in object_keys and normalize_reference(r, file_storage_bucket) in object_keys
    )
    matched = exact | normalized if normalize else exact
    orphans = [dict(o) for o in objects if o["key"] not in matched]
    return OrphanResult(
        orphans=orphans,
        orphaned_bytes=sum(o["size"] for o in orphans),
        normalizable_references=normalizable,
    )


def quarantine_key(prefix: str, ds: str, key: str) -> str:
    """legacy: ``<quarantine prefix>/<ds>/<source key>``."""
    return f"{prefix}/{ds}/{key}"


@dataclass
class QuarantineResult:
    moved: int = 0
    already_quarantined: int = 0
    failed_keys: list[str] = field(default_factory=list)

    @property
    def quarantined(self) -> int:
        return self.moved + self.already_quarantined

    @property
    def failed(self) -> int:
        return len(self.failed_keys)


class QuarantineVerifyError(RuntimeError):
    """The copy in the quarantine bucket is missing or not the size of the source."""


def quarantine_object(
    hook: QuarantineHook,
    obj: Mapping[str, Any],
    *,
    file_storage_bucket: str,
    quarantine_bucket: str,
    dest_key: str,
) -> bool:
    """Copy, verify the copy, then delete the source. Returns False when a previous attempt
    already moved it (source gone, copy present). A same-day copy is overwritten, as legacy."""
    source_key = obj["key"]
    if hook.head_object(source_key, bucket_name=file_storage_bucket) is None:
        if hook.head_object(dest_key, bucket_name=quarantine_bucket) is not None:
            return False
        raise QuarantineVerifyError(
            f"s3://{file_storage_bucket}/{source_key} is gone and "
            f"s3://{quarantine_bucket}/{dest_key} does not exist"
        )
    hook.copy_object(
        source_key,
        dest_key,
        source_bucket_name=file_storage_bucket,
        dest_bucket_name=quarantine_bucket,
        MetadataDirective="COPY",
    )
    copy = hook.head_object(dest_key, bucket_name=quarantine_bucket)
    copied_size = None if copy is None else copy.get("ContentLength")
    if copied_size is None or int(copied_size) != int(obj["size"]):
        raise QuarantineVerifyError(
            f"copy s3://{quarantine_bucket}/{dest_key} has size {copied_size}, "
            f"source has {obj['size']}; source kept"
        )
    hook.delete_objects(file_storage_bucket, [source_key])
    return True


def quarantine_orphans(
    hook: QuarantineHook,
    orphans: Iterable[Mapping[str, Any]],
    *,
    file_storage_bucket: str,
    quarantine_bucket: str,
    quarantine_prefix: str,
    ds: str,
) -> QuarantineResult:
    """legacy: a per-object failure is counted and the rest continue; logged here at ERROR."""
    result = QuarantineResult()
    for obj in orphans:
        dest_key = quarantine_key(quarantine_prefix, ds, obj["key"])
        try:
            moved = quarantine_object(
                hook,
                obj,
                file_storage_bucket=file_storage_bucket,
                quarantine_bucket=quarantine_bucket,
                dest_key=dest_key,
            )
        except Exception as exc:
            log_event(
                logger,
                "quarantine_failed",
                logging.ERROR,
                source="s3://{}/{}".format(file_storage_bucket, obj["key"]),
                destination=f"s3://{quarantine_bucket}/{dest_key}",
                error=str(exc),
            )
            result.failed_keys.append(obj["key"])
            continue
        if moved:
            result.moved += 1
        else:
            result.already_quarantined += 1
            log_event(logger, "already_quarantined", key=obj["key"], destination=dest_key)
    return result


def build_report(
    *,
    ds: str,
    generated_at: str,
    total_objects: int,
    total_size_bytes: int,
    orphaned_objects: int,
    orphaned_bytes: int,
    objects_quarantined: int,
    objects_failed: int,
    quarantine_bucket: str,
    price_per_gb_month_usd: float,
) -> dict[str, Any]:
    """legacy: field order, rounding, int ``0`` percentage with no objects, and
    ``storage_freed_gb`` from the orphaned bytes even when copies failed."""
    savings_gb = orphaned_bytes / GIB
    return {
        "report_type": "storage_cleanup",
        "report_date": ds,
        "generated_at": generated_at,
        "inventory": {
            "total_objects": total_objects,
            "total_size_bytes": total_size_bytes,
            "total_size_gb": round(total_size_bytes / GIB, 4),
        },
        "orphans": {
            "orphaned_objects": orphaned_objects,
            "orphaned_bytes": orphaned_bytes,
            "orphaned_size_gb": round(savings_gb, 4),
            "orphan_percentage": round(
                (orphaned_objects / total_objects * 100) if total_objects else 0, 2
            ),
        },
        "cleanup": {
            "objects_quarantined": objects_quarantined,
            "objects_failed": objects_failed,
            "quarantine_bucket": quarantine_bucket,
        },
        "savings": {
            "storage_freed_gb": round(savings_gb, 4),
            "estimated_monthly_savings_usd": round(savings_gb * price_per_gb_month_usd, 4),
        },
    }
