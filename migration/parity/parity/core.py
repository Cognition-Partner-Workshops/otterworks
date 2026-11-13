import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext


def canonical(value):
    if value is None:
        return ["null"]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, int | float | Decimal):
        number = Decimal(str(value))
        if not number.is_finite():
            return ["number", str(number)]
        text = format(number, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return ["number", "0" if number == 0 else text]
    if isinstance(value, datetime | date):
        if not isinstance(value, datetime):
            value = datetime.combine(value, datetime.min.time())
        if value.tzinfo:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return ["datetime", value.isoformat(timespec="seconds")]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    return ["string", str(value)]


def packed(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(packed(value).encode()).hexdigest()


def profile(values):
    present = [v for v in values if v is not None]
    numbers = [Decimal(str(v)) for v in present if isinstance(v, int | float | Decimal) and not isinstance(v, bool)]
    with localcontext() as context:
        context.prec = 100
        scales = [max(0, -n.normalize().as_tuple().exponent) for n in numbers if n.is_finite()]
        bounds = sorted(present, key=lambda v: packed(canonical(v)))
        if numbers and len(numbers) == len(present):
            bounds = sorted(numbers, key=lambda n: (n.is_nan(), 0 if n.is_nan() else n))
        if any(n.is_nan() for n in numbers) or (Decimal("Infinity") in numbers and Decimal("-Infinity") in numbers):
            total = Decimal("NaN")
        else:
            total = sum(numbers, Decimal(0))
        return {
            "non_null": len(present), "null": len(values) - len(present),
            "empty_string": sum(isinstance(v, str) and v == "" for v in present),
            "distinct": len({packed(canonical(v)) for v in present}),
            "min": canonical(bounds[0]) if bounds else None,
            "max": canonical(bounds[-1]) if bounds else None,
            "sum": canonical(total) if numbers else None,
            "max_numeric_scale": max(scales, default=None),
        }


def inspect(rows, columns, keys, sample_size):
    rows = list(rows)
    key_indexes = [columns.index(k) for k in keys]
    hashes = Counter()
    samples = []
    for row in rows:
        key = [canonical(row[i]) for i in key_indexes]
        values = [canonical(v) for v in row]
        hashes[packed([key, digest(values)])] += 1
        samples.append((digest([key, values]), {"key": key, "values": values}))
    return {
        "row_count": len(rows),
        "profiles": {c: profile([r[i] for r in rows]) for i, c in enumerate(columns)},
        "keyed_row_hash": digest(sorted(hashes.items())),
        "samples": [row for _, row in sorted(samples, key=lambda s: s[0])[:sample_size]],
    }


def compare(spec, left_rows, right_rows):
    keys = spec.get("keys", [])
    columns = list(dict.fromkeys(keys + spec["compare"]))
    size = int(spec.get("sample_size", 20))
    if size < 0:
        raise ValueError("sample_size must be nonnegative")
    left = inspect(left_rows, columns, keys, size)
    right = inspect(right_rows, columns, keys, size)
    checks = {name: left[name] == right[name] for name in left}
    status = "green" if all(checks.values()) else "red"
    if status == "red" and spec.get("open_question") and spec.get("owner"):
        status = "amber"
    return {
        "name": spec.get("name", spec["left_table"]), "status": status,
        "checks": checks, "left": left, "right": right,
        "open_question": spec.get("open_question"), "owner": spec.get("owner"),
    }
