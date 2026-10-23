#!/usr/bin/env python3
"""Generate deterministic extracts for the legacy warehouse fixture."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import uuid
from collections.abc import Iterable, Iterator, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).resolve().parent
UTC_START = datetime(2026, 9, 1, tzinfo=UTC)
DAY_COUNT = 31
REGION_CODES = (
    "us-east-1",
    "us-west-2",
    "eu-west-1",
    "eu-central-1",
    "ap-southeast-2",
)
TIER_COUNTS = (("starter", 30), ("growth", 20), ("scale", 10))
FIRST_WORDS = (
    "Amber",
    "Copper",
    "Cedar",
    "Quiet",
    "Silver",
    "Moss",
    "Harbor",
    "Willow",
    "Lantern",
    "Maple",
)
SECOND_WORDS = (
    "Basin",
    "Meadow",
    "Harbor",
    "Parcel",
    "Lantern",
    "Cove",
    "Orchard",
    "Creek",
    "Ridge",
    "Grove",
)
SUFFIXES = ("Studio", "Workshop", "Collective", "Atelier", "House", "Works")
GIVEN_NAMES = (
    "Ada",
    "Avery",
    "Cameron",
    "Drew",
    "Elliot",
    "Emery",
    "Finley",
    "Harper",
    "Jordan",
    "Kai",
    "Morgan",
    "Quinn",
    "Riley",
    "Rowan",
    "Sage",
    "Taylor",
)
FAMILY_NAMES = (
    "Bennett",
    "Brooks",
    "Carter",
    "Ellis",
    "Hayes",
    "James",
    "Kelly",
    "Morgan",
    "Parker",
    "Reed",
    "Rivera",
    "Sullivan",
    "Turner",
    "Wells",
    "Young",
    "Zeller",
)
DOCUMENT_TYPES = ("text/markdown", "application/pdf", "text/plain", "application/word")
FILE_TYPES = (
    ("application/pdf", "pdf"),
    ("image/jpeg", "jpg"),
    ("image/png", "png"),
    ("text/csv", "csv"),
    ("application/zip", "zip"),
)
EVENT_TYPES = ("document.view", "file.download", "workspace.open", "usage.recorded")
USER_AGENTS = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/605.1.15 Safari/17.5",
    "InternalClient/2.4",
)
HOUR_WEIGHTS = tuple(0.056 if hour in {23, 0, 1, 2, 3} else 0.72 / 19 for hour in range(24))
CSV_FILES: dict[str, tuple[str, ...]] = {
    "billing_tenants.csv": ("id", "name", "tax_exempt", "status"),
    "billing_tenant_regions.csv": ("tenant_id", "region_code"),
    "billing_plans.csv": (
        "id",
        "code",
        "tier",
        "monthly_fee",
        "included_units",
        "overage_rate",
        "active",
    ),
    "billing_subscriptions.csv": (
        "id",
        "tenant_id",
        "plan_id",
        "starts_on",
        "ends_on",
        "status",
        "suspended_on",
    ),
    "billing_usage_events.csv": ("id", "tenant_id", "occurred_at", "units", "kind"),
    "billing_rating_periods.csv": ("id", "tenant_id", "period_start", "period_end"),
    "billing_invoices.csv": (
        "id",
        "tenant_id",
        "period_id",
        "issued_at",
        "subtotal",
        "tax",
        "total",
        "status",
    ),
    "billing_invoice_lines.csv": (
        "id",
        "invoice_id",
        "line_no",
        "line_type",
        "description",
        "amount",
    ),
    "auth_users.csv": (
        "id",
        "email",
        "display_name",
        "email_verified",
        "mfa_enabled",
        "created_at",
        "updated_at",
        "last_login_at",
    ),
    "auth_workspace_members.csv": (
        "user_id",
        "workspace_id",
        "workspace_name",
        "tenant_id",
        "role",
        "joined_at",
    ),
    "documents.csv": (
        "id",
        "title",
        "content_type",
        "owner_id",
        "folder_id",
        "workspace_id",
        "is_deleted",
        "is_template",
        "archived",
        "word_count",
        "version",
        "created_at",
        "updated_at",
    ),
    "document_versions.csv": (
        "id",
        "document_id",
        "version_number",
        "title",
        "created_by",
        "created_at",
        "content_length",
    ),
    "files.csv": (
        "id",
        "name",
        "mime_type",
        "size_bytes",
        "folder_id",
        "owner_id",
        "workspace_id",
        "version",
        "is_trashed",
        "archived",
        "created_at",
        "updated_at",
    ),
    "file_versions.csv": ("file_id", "version", "size_bytes", "created_by", "created_at"),
    "collab_events.csv": (
        "id",
        "event_type",
        "document_id",
        "user_id",
        "session_id",
        "created_at",
    ),
    "audit_events.csv": (
        "id",
        "user_id",
        "action",
        "resource_type",
        "resource_id",
        "details",
        "ip_address",
        "user_agent",
        "timestamp",
    ),
    "analytics_events.csv": (
        "event_id",
        "event_type",
        "user_id",
        "resource_id",
        "resource_type",
        "metadata",
        "occurred_at",
    ),
}


def _read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def _table_body(sql: str, table_name: str) -> str:
    match = re.search(
        rf"CREATE TABLE(?: IF NOT EXISTS)?\s+(?:billing\.)?{re.escape(table_name)}\s*"
        r"\((.*?)\);",
        sql,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Could not find source table {table_name}")
    return match.group(1)


def _sql_columns(body: str) -> set[str]:
    columns: set[str] = set()
    for line in body.splitlines():
        match = re.match(r"\s*([a-zA-Z_]\w*)\s+", line)
        if match and match.group(1).upper() not in {
            "CHECK",
            "CONSTRAINT",
            "PRIMARY",
            "UNIQUE",
            "FOREIGN",
        }:
            columns.add(match.group(1))
    return columns


def _mapped_columns(source: str, class_name: str) -> set[str]:
    match = re.search(
        rf"class {re.escape(class_name)}\(Base\):(.*?)(?=\nclass |\Z)",
        source,
        re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Could not find model {class_name}")
    return set(re.findall(r"^\s{4}([a-zA-Z_]\w*): Mapped\[", match.group(1), re.MULTILINE))


def _rust_fields(source: str, struct_name: str) -> set[str]:
    match = re.search(rf"pub struct {re.escape(struct_name)}\s*\{{(.*?)\n\}}", source, re.DOTALL)
    if match is None:
        raise ValueError(f"Could not find Rust model {struct_name}")
    return set(re.findall(r"^\s*pub\s+([a-zA-Z_]\w*):", match.group(1), re.MULTILINE))


def _enum_values(body: str, column: str) -> tuple[str, ...]:
    match = re.search(
        rf"\b{re.escape(column)}\s+\w+.*?CHECK\s*\(\s*{re.escape(column)}\s+IN\s*\(([^)]*)\)",
        body,
        re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"Could not find enum values for {column}")
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def _snake_case(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def _validate_source_shapes() -> dict[str, tuple[str, ...]]:
    billing = _read_text("services/legacy-billing/db/schema.sql")
    tenant_body = _table_body(billing, "tenants")
    plan_body = _table_body(billing, "plans")
    subscription_body = _table_body(billing, "subscriptions")
    usage_body = _table_body(billing, "usage_events")
    invoice_body = _table_body(billing, "invoices")
    invoice_line_body = _table_body(billing, "invoice_lines")

    auth_root = "services/auth-service/src/main/resources/db/migration/"
    users_sql = _read_text(f"{auth_root}V1__create_users_table.sql")
    roles_sql = _read_text(f"{auth_root}V2__create_roles_table.sql")
    users_body = _table_body(users_sql, "users")
    roles = tuple(re.findall(r"\('([^']+)',\s*'[^']*'\)", roles_sql))

    document_source = _read_text("services/document-service/app/models/document.py")
    document_columns = _mapped_columns(document_source, "Document")
    document_version_columns = _mapped_columns(document_source, "DocumentVersion")
    file_source = _read_text("services/file-service/src/models.rs")
    file_columns = _rust_fields(file_source, "FileMetadata")
    file_version_columns = _rust_fields(file_source, "FileVersion")

    audit_source = _read_text("services/audit-service/src/Services/AuditEvent.cs")
    action_match = re.search(r"Action.*?//\s*([^\n]+)", audit_source)
    resource_match = re.search(r"ResourceType.*?//\s*([^\n]+)", audit_source)
    if action_match is None or resource_match is None:
        raise ValueError("Could not find audit action and resource type comments")
    audit_actions = tuple(value.strip() for value in action_match.group(1).split(","))
    audit_resources = tuple(value.strip() for value in resource_match.group(1).split(","))
    audit_columns = {
        _snake_case(name)
        for name in re.findall(r"public\s+.+?\s+([A-Z]\w*)\s*\{", audit_source, re.MULTILINE)
        if name not in {"Events", "Total", "Page", "PageSize"}
    }

    analytics_source = _read_text(
        "services/analytics-service/src/main/resources/db/migration/"
        "V1__create_analytics_tables.sql"
    )
    analytics_body = _table_body(analytics_source, "analytics_events")
    analytics_columns = _sql_columns(analytics_body)

    shapes = {
        "billing_tenants.csv": _sql_columns(tenant_body),
        "billing_plans.csv": _sql_columns(plan_body),
        "billing_subscriptions.csv": _sql_columns(subscription_body),
        "billing_usage_events.csv": _sql_columns(usage_body),
        "billing_invoices.csv": _sql_columns(invoice_body),
        "billing_invoice_lines.csv": _sql_columns(invoice_line_body),
        "auth_users.csv": _sql_columns(users_body),
        "documents.csv": document_columns,
        "document_versions.csv": document_version_columns,
        "files.csv": file_columns,
        "file_versions.csv": file_version_columns,
        "audit_events.csv": audit_columns,
        "analytics_events.csv": analytics_columns,
    }
    export_additions = {
        "documents.csv": {"workspace_id", "archived"},
        "document_versions.csv": {"content_length"},
        "files.csv": {"workspace_id", "archived"},
    }
    for filename, columns in shapes.items():
        missing = set(CSV_FILES[filename]) - export_additions.get(filename, set()) - columns
        if missing:
            raise ValueError(
                f"{filename} columns are absent from the service schema: "
                f"{', '.join(sorted(missing))}"
            )
    if "workspace_id" in document_columns or "archived" in document_columns:
        raise ValueError(
            "The document export fields workspace_id and archived are service additions"
        )
    if "content_length" in document_version_columns:
        raise ValueError("The document version export field content_length is derived")
    if "workspace_id" in file_columns or "archived" in file_columns:
        raise ValueError("The file export fields workspace_id and archived are service additions")
    if not roles or not audit_actions or not audit_resources:
        raise ValueError("A source enum list is empty")
    enum_values = {
        "billing_tenants.csv": _enum_values(tenant_body, "status"),
        "billing_plans.csv": _enum_values(plan_body, "tier"),
        "billing_subscriptions.csv": _enum_values(subscription_body, "status"),
        "billing_usage_events.csv": _enum_values(usage_body, "kind"),
        "billing_invoices.csv": _enum_values(invoice_body, "status"),
        "billing_invoice_lines.csv": _enum_values(invoice_line_body, "line_type"),
        "auth_workspace_members.csv": roles,
        "audit_actions": audit_actions,
        "audit_resources": audit_resources,
    }
    if set(enum_values["billing_plans.csv"]) != {"starter", "growth", "scale"}:
        raise ValueError("The billing plan tiers differ from the expected source contract")
    return enum_values


def _new_id(rng: random.Random) -> str:
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _format_pg_timestamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S.%f+00")


def _format_rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _format_dotnet_timestamp(value: datetime, rng: random.Random) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + str(rng.randrange(10)) + "Z"


def _event_timestamp(rng: random.Random) -> datetime:
    day = rng.randrange(DAY_COUNT)
    hour = rng.choices(range(24), weights=HOUR_WEIGHTS, k=1)[0]
    return UTC_START + timedelta(
        days=day,
        hours=hour,
        minutes=rng.randrange(60),
        seconds=rng.randrange(60),
        microseconds=rng.randrange(1_000_000),
    )


def _random_timestamp(rng: random.Random, start: datetime, end: datetime) -> datetime:
    span_microseconds = int((end - start).total_seconds() * 1_000_000)
    return start + timedelta(microseconds=rng.randrange(max(span_microseconds, 1)))


def _write_csv(path: Path, header: Sequence[str], rows: Iterable[Sequence[object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def _plan_catalog(rng: random.Random) -> tuple[list[dict[str, object]], dict[str, str]]:
    plan_definitions = (
        ("starter-monthly", "starter", "49.00", "0.250000", 50, True),
        ("starter-annual", "starter", "490.00", "0.250000", 50, True),
        ("growth-monthly", "growth", "199.00", "0.180000", 500, True),
        ("growth-annual", "growth", "1990.00", "0.180000", 500, True),
        ("scale-monthly", "scale", "799.00", "0.100000", 5000, True),
        ("scale-annual", "scale", "7990.00", "0.100000", 5000, True),
        ("growth-2019", "growth", "149.00", "0.220000", 500, False),
    )
    plans = [
        {
            "id": _new_id(rng),
            "code": code,
            "tier": tier,
            "monthly_fee": fee,
            "included_units": units,
            "overage_rate": rate,
            "active": active,
        }
        for code, tier, fee, rate, units, active in plan_definitions
    ]
    plan_by_tier = {
        tier: next(
            str(plan["id"])
            for plan in plans
            if plan["tier"] == tier and plan["code"] == f"{tier}-monthly"
        )
        for tier, _ in TIER_COUNTS
    }
    return plans, plan_by_tier


def _tenant_names() -> list[str]:
    names = [
        f"{first} {second} {suffix}"
        for first in FIRST_WORDS
        for second in SECOND_WORDS
        for suffix in SUFFIXES
    ]
    return [f"{names[index]} {index + 1:03d}" for index in range(60)]


def _subscription_rows(
    rng: random.Random, tenants: list[dict[str, object]], plan_by_tier: dict[str, str]
) -> list[list[object]]:
    rows: list[list[object]] = []
    for index, tenant in enumerate(tenants):
        tier = str(tenant["tier"])
        plan_id = plan_by_tier[tier]
        rows.append(
            [
                _new_id(rng),
                tenant["id"],
                plan_id,
                "2025-09-01",
                "",
                "active",
                "",
            ]
        )
        if index % 5 == 1:
            earlier_plan = plan_by_tier[TIER_COUNTS[(index // 7) % 3][0]]
            rows.append(
                [
                    _new_id(rng),
                    tenant["id"],
                    earlier_plan,
                    "2024-01-01",
                    "2026-07-31",
                    "cancelled",
                    "",
                ]
            )
    return rows


def _billing_usage_rows(
    rng: random.Random, tenants: list[dict[str, object]]
) -> Iterator[list[object]]:
    growth_ranges = {
        "starter": ((30, 60), (0.3, 1.2)),
        "growth": ((350, 550), (2.0, 8.0)),
        "scale": ((3000, 5000), (10.0, 40.0)),
    }
    for tenant in tenants:
        (base_min, base_max), (growth_min, growth_max) = growth_ranges[str(tenant["tier"])]
        starting_gb = rng.uniform(base_min, base_max)
        growth_gb = rng.uniform(growth_min, growth_max)
        for day_offset in range(DAY_COUNT):
            for kind, low, high in (("api", 40, 120), ("compute", 10, 40)):
                for _ in range(rng.randint(low, high)):
                    yield [
                        _new_id(rng),
                        tenant["id"],
                        _format_pg_timestamp(_event_timestamp(rng)),
                        rng.randint(1, 25) if kind == "api" else rng.randint(1, 80),
                        kind,
                    ]
            daily_growth = growth_gb * day_offset
            for sample in range(24):
                sample_time = UTC_START + timedelta(days=day_offset, hours=sample)
                sample_time += timedelta(minutes=rng.randint(-12, 12))
                storage_gb = max(1.0, starting_gb + daily_growth + rng.uniform(-0.75, 0.75))
                yield [
                    _new_id(rng),
                    tenant["id"],
                    _format_pg_timestamp(sample_time),
                    int(storage_gb * 1024),
                    "storage",
                ]


def _invoice_data(
    rng: random.Random,
    tenants: list[dict[str, object]],
    plan_by_tier: dict[str, str],
    periods_by_tenant: dict[str, dict[str, str]],
    enum_values: dict[str, tuple[str, ...]],
) -> tuple[list[list[object]], list[list[object]]]:
    invoices: list[list[object]] = []
    lines: list[list[object]] = []
    line_types = enum_values["billing_invoice_lines.csv"]
    invoice_statuses = enum_values["billing_invoices.csv"]
    for _tenant_index, tenant in enumerate(tenants):
        tier = str(tenant["tier"])
        monthly_fee = Decimal({"starter": "49.00", "growth": "199.00", "scale": "799.00"}[tier])
        for period_name, issued_day, status_values in (
            ("2026-08-01", 1, ("paid", "overdue")),
            ("2026-09-01", 30, ("issued", "draft")),
        ):
            invoice_id = _new_id(rng)
            period_id = periods_by_tenant[str(tenant["id"])][period_name]
            if issued_day == 1:
                issued_at = datetime(2026, 9, 1, tzinfo=UTC) + timedelta(
                    hours=rng.randint(1, 3), minutes=rng.randrange(60)
                )
            else:
                issued_at = datetime(2026, 9, 30, tzinfo=UTC) + timedelta(
                    hours=22, minutes=rng.randrange(120)
                )
                if issued_at.date() != date(2026, 9, 30):
                    issued_at = datetime(2026, 9, 30, 23, 59, tzinfo=UTC)
            usage_amount = Decimal(rng.randrange(0, 3500)) / Decimal(100)
            credit = (
                -Decimal(rng.randrange(100, 1501)) / Decimal(100)
                if rng.random() < 0.16
                else Decimal(0)
            )
            subtotal = max(Decimal("0.00"), monthly_fee + usage_amount + credit)
            tax = (
                Decimal("0.00")
                if bool(tenant["tax_exempt"])
                else (subtotal * Decimal("0.0825")).quantize(Decimal("0.01"))
            )
            total = subtotal + tax
            status = rng.choice([value for value in invoice_statuses if value in status_values])
            invoices.append(
                [
                    invoice_id,
                    tenant["id"],
                    period_id,
                    _format_pg_timestamp(issued_at),
                    f"{subtotal:.2f}",
                    f"{tax:.2f}",
                    f"{total:.2f}",
                    status,
                ]
            )
            invoice_lines = [
                ("plan", f"{monthly_fee:.2f}", f"{tier.title()} plan"),
                ("usage", f"{usage_amount:.2f}", "Usage charges"),
            ]
            if credit < 0:
                invoice_lines.append(("credit", f"{credit:.2f}", "Service credit"))
            invoice_lines.append(("tax", f"{tax:.2f}", "Sales tax"))
            if any(kind not in line_types for kind, _, _ in invoice_lines):
                raise ValueError("An invoice line type is absent from the billing schema")
            for line_no, (line_type, amount, description) in enumerate(invoice_lines, start=1):
                lines.append(
                    [_new_id(rng), invoice_id, line_no, line_type, description, amount]
                )
    return invoices, lines


def _build_workspaces(
    rng: random.Random, tenants: list[dict[str, object]]
) -> tuple[list[dict[str, object]], list[list[object]], dict[str, list[dict[str, object]]]]:
    counts = [1] * len(tenants)
    for _ in range(120):
        candidates = [index for index, count in enumerate(counts) if count < 6]
        counts[rng.choice(candidates)] += 1
    workspaces: list[dict[str, object]] = []
    regions: dict[str, list[dict[str, object]]] = {}
    for tenant_index, tenant in enumerate(tenants):
        tenant_workspaces: list[dict[str, object]] = []
        for workspace_index in range(counts[tenant_index]):
            workspace = {
                "id": _new_id(rng),
                "name": f"Workspace {workspace_index + 1:02d}",
                "tenant_id": tenant["id"],
                "tenant_index": tenant_index,
                "folder_id": _new_id(rng),
            }
            workspaces.append(workspace)
            tenant_workspaces.append(workspace)
        regions[str(tenant["id"])] = tenant_workspaces
    if len(workspaces) != 180:
        raise ValueError("The workspace allocation did not produce 180 workspaces")
    return workspaces, [], regions


def _build_users_and_memberships(
    rng: random.Random,
    tenants: list[dict[str, object]],
    tenant_workspaces: dict[str, list[dict[str, object]]],
    roles: tuple[str, ...],
) -> tuple[list[dict[str, object]], list[list[object]], dict[str, list[dict[str, object]]]]:
    users: list[dict[str, object]] = []
    memberships: list[list[object]] = []
    members_by_workspace: dict[str, list[dict[str, object]]] = {}
    members_by_tenant: dict[str, list[dict[str, object]]] = {}
    for tenant_index, tenant in enumerate(tenants):
        tenant_id = str(tenant["id"])
        workspaces = tenant_workspaces[tenant_id]
        members_by_tenant[tenant_id] = []
        for user_index in range(40):
            user_id = _new_id(rng)
            user = {
                "id": user_id,
                "tenant_id": tenant_id,
                "display_name": (
                    f"{GIVEN_NAMES[(tenant_index + user_index) % len(GIVEN_NAMES)]} "
                    f"{FAMILY_NAMES[(tenant_index * 3 + user_index) % len(FAMILY_NAMES)]}"
                ),
                "email": f"person{user_index + 1:03d}@tenant-{tenant_index + 1:03d}.invalid",
            }
            users.append(user)
            members_by_tenant[tenant_id].append(user)

        for workspace_index, workspace in enumerate(workspaces):
            assigned_users = [
                members_by_tenant[tenant_id][member_index]
                for member_index in range(workspace_index, 40, len(workspaces))
            ]
            members_by_workspace[str(workspace["id"])] = assigned_users
            for user in assigned_users:
                memberships.append(
                    [
                        user["id"],
                        workspace["id"],
                        workspace["name"],
                        tenant_id,
                        rng.choice(roles),
                        _format_pg_timestamp(
                            datetime(2024, 1, 1, tzinfo=UTC)
                            + timedelta(days=rng.randrange(1000))
                        ),
                    ]
                )

        for user_index, user in enumerate(members_by_tenant[tenant_id]):
            if user_index % 8 == 0 and len(workspaces) > 1:
                first_workspace = workspaces[user_index % len(workspaces)]
                second_workspace = workspaces[(user_index + 1) % len(workspaces)]
                if first_workspace["id"] == second_workspace["id"]:
                    second_workspace = workspaces[(user_index + 2) % len(workspaces)]
                if user in members_by_workspace[str(first_workspace["id"])]:
                    memberships.append(
                        [
                            user["id"],
                            second_workspace["id"],
                            second_workspace["name"],
                            tenant_id,
                            rng.choice(roles),
                            _format_pg_timestamp(
                                datetime(2024, 1, 1, tzinfo=UTC)
                                + timedelta(days=rng.randrange(1000))
                            ),
                        ]
                    )
                    members_by_workspace[str(second_workspace["id"])].append(user)
    return users, memberships, members_by_workspace


def _auth_user_rows(rng: random.Random, users: list[dict[str, object]]) -> Iterator[list[object]]:
    for index, user in enumerate(users):
        created = _random_timestamp(
            rng, datetime(2018, 1, 1, tzinfo=UTC), datetime(2026, 10, 2, tzinfo=UTC)
        )
        updated = min(
            created + timedelta(days=rng.randrange(0, 500)),
            datetime(2026, 10, 2, tzinfo=UTC),
        )
        last_login = (
            _random_timestamp(rng, created, datetime(2026, 10, 2, tzinfo=UTC))
            if rng.random() < 0.86
            else None
        )
        yield [
            user["id"],
            user["email"],
            user["display_name"],
            "t" if index % 7 else "f",
            "t" if index % 3 == 0 else "f",
            _format_pg_timestamp(created),
            _format_pg_timestamp(updated),
            _format_pg_timestamp(last_login) if last_login is not None else "",
        ]


def _document_rows(
    rng: random.Random,
    users: list[dict[str, object]],
    workspaces: list[dict[str, object]],
    members_by_workspace: dict[str, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], Iterator[list[object]], Iterator[list[object]]]:
    document_records: list[dict[str, object]] = []
    rows: list[list[object]] = []
    versions: list[list[object]] = []
    old_count = 1200
    old_start = datetime(2016, 1, 1, tzinfo=UTC)
    old_end = datetime(2018, 3, 1, tzinfo=UTC)
    current_start = datetime(2018, 3, 1, tzinfo=UTC)
    current_end = datetime(2026, 10, 2, tzinfo=UTC)
    for index in range(40_000):
        workspace = rng.choice(workspaces)
        workspace_id = str(workspace["id"])
        owner = rng.choice(members_by_workspace[workspace_id])
        created = (
            _random_timestamp(rng, old_start, old_end)
            if index < old_count
            else _random_timestamp(rng, current_start, current_end)
        )
        updated = min(
            created + timedelta(days=rng.randrange(0, 365)),
            datetime(2026, 10, 1, 23, 59, 59, tzinfo=UTC),
        )
        version_count = 1 + index % 4
        document_id = _new_id(rng)
        archived: str | None = (
            ""
            if created < datetime(2018, 3, 1, tzinfo=UTC)
            else ("t" if rng.random() < 0.12 else "f")
        )
        title = f"{workspace['name']} working notes {index + 1:05d}"
        record = {
            "id": document_id,
            "workspace": workspace,
            "owner": owner,
            "created": created,
            "updated": updated,
            "version": version_count,
            "title": title,
        }
        document_records.append(record)
        rows.append(
            [
                document_id,
                title,
                rng.choice(DOCUMENT_TYPES),
                owner["id"],
                workspace["folder_id"] if index % 6 else "",
                workspace_id,
                "t" if index % 25 == 0 else "f",
                "t" if index % 31 == 0 else "f",
                archived,
                rng.randint(40, 12000),
                version_count,
                _format_pg_timestamp(created),
                _format_pg_timestamp(updated),
            ]
        )
        span = updated - created
        for version_number in range(1, version_count + 1):
            version_created = (
                created
                if version_count == 1
                else created + span * ((version_number - 1) / (version_count - 1))
            )
            versions.append(
                [
                    _new_id(rng),
                    document_id,
                    version_number,
                    title,
                    owner["id"],
                    _format_pg_timestamp(version_created),
                    rng.randint(100, 80_000),
                ]
            )
    return document_records, iter(rows), iter(versions)


def _file_rows(
    rng: random.Random,
    users: list[dict[str, object]],
    workspaces: list[dict[str, object]],
    members_by_workspace: dict[str, list[dict[str, object]]],
) -> tuple[list[dict[str, object]], Iterator[list[object]], Iterator[list[object]]]:
    file_records: list[dict[str, object]] = []
    rows: list[list[object]] = []
    versions: list[list[object]] = []
    old_start = datetime(2016, 1, 1, tzinfo=UTC)
    old_end = datetime(2018, 3, 1, tzinfo=UTC)
    current_start = datetime(2018, 3, 1, tzinfo=UTC)
    current_end = datetime(2026, 10, 2, tzinfo=UTC)
    for index in range(25_000):
        workspace = rng.choice(workspaces)
        workspace_id = str(workspace["id"])
        owner = rng.choice(members_by_workspace[workspace_id])
        created = (
            _random_timestamp(rng, old_start, old_end)
            if index < 750
            else _random_timestamp(rng, current_start, current_end)
        )
        updated = min(
            created + timedelta(days=rng.randrange(0, 365)),
            datetime(2026, 10, 1, 23, 59, 59, tzinfo=UTC),
        )
        file_id = _new_id(rng)
        version_count = 1 + index % 3
        mime_type, extension = rng.choice(FILE_TYPES)
        size_bytes = rng.randint(2_000, 1_750_000_000)
        if index < 8:
            size_bytes = rng.randint(2_150_000_000, 4_000_000_000)
        archived = (
            ""
            if created < datetime(2018, 3, 1, tzinfo=UTC)
            else ("true" if rng.random() < 0.12 else "false")
        )
        name = f"{workspace['name'].lower().replace(' ', '-')}-{index + 1:05d}.{extension}"
        file_records.append(
            {
                "id": file_id,
                "workspace": workspace,
                "owner": owner,
                "created": created,
                "updated": updated,
                "version": version_count,
            }
        )
        rows.append(
            [
                file_id,
                name,
                mime_type,
                size_bytes,
                workspace["folder_id"] if index % 5 else "",
                owner["id"],
                workspace_id,
                version_count,
                "true" if index % 20 == 0 else "false",
                archived,
                _format_rfc3339(created),
                _format_rfc3339(updated),
            ]
        )
        for version_number in range(1, version_count + 1):
            version_created = created + (updated - created) * (
                (version_number - 1) / max(version_count - 1, 1)
            )
            versions.append(
                [
                    file_id,
                    version_number,
                    max(1, int(size_bytes * (0.72 + version_number * 0.12))),
                    owner["id"],
                    _format_rfc3339(version_created),
                ]
            )
    return file_records, iter(rows), iter(versions)


def _event_rows(
    rng: random.Random,
    users: list[dict[str, object]],
    documents: list[dict[str, object]],
    files: list[dict[str, object]],
    audit_actions: tuple[str, ...],
    audit_resources: tuple[str, ...],
    count: int,
    mode: str,
) -> Iterator[list[object]]:
    for _index in range(count):
        timestamp = _event_timestamp(rng)
        document = rng.choice(documents)
        user = rng.choice(users)
        if mode == "collab":
            kind = rng.choices(
                ("comment", "session_join", "session_leave"),
                weights=(0.75, 0.125, 0.125),
                k=1,
            )[0]
            document_workspace = str(document["workspace"]["id"])
            workspace_members = [
                item for item in users if item["tenant_id"] == document["owner"]["tenant_id"]
            ]
            event_user = rng.choice(workspace_members)
            yield [
                _new_id(rng),
                kind,
                document["id"],
                event_user["id"],
                "" if kind == "comment" else _new_id(rng),
                _format_pg_timestamp(timestamp),
            ]
            if not document_workspace:
                raise ValueError("A collaboration document has no workspace")
            continue

        action = rng.choice(audit_actions)
        resource_type = rng.choice(audit_resources)
        resource_id = {
            "document": document["id"],
            "file": rng.choice(files)["id"],
            "user": user["id"],
            "folder": document["workspace"]["folder_id"],
            "permission": document["workspace"]["id"],
        }[resource_type]
        if mode == "audit":
            yield [
                _new_id(rng),
                user["id"],
                action,
                resource_type,
                resource_id,
                json.dumps({"source": "web", "result": "success"}, separators=(",", ":")),
                f"192.0.2.{rng.randint(1, 254)}",
                rng.choice(USER_AGENTS),
                _format_dotnet_timestamp(timestamp, rng),
            ]
            continue

        event_type = rng.choice(EVENT_TYPES)
        if event_type == "file.download":
            resource = rng.choice(files)
            resource_type = "file"
        elif event_type == "document.view":
            resource = document
            resource_type = "document"
        else:
            resource = document["workspace"]
            resource_type = "workspace"
        epoch_ns = int(timestamp.timestamp()) * 1_000_000_000 + timestamp.microsecond * 1000
        epoch_ns += rng.randrange(1000)
        yield [
            _new_id(rng),
            event_type,
            user["id"],
            resource["id"],
            resource_type,
            json.dumps({"source": "web"}, separators=(",", ":")),
            epoch_ns,
        ]


def generate(out_dir: Path) -> None:
    rng = random.Random(int(os.environ.get("UBW_SEED", "20261012")))
    enum_values = _validate_source_shapes()
    output = out_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    tenants: list[dict[str, object]] = []
    for tier, count in TIER_COUNTS:
        for _ in range(count):
            index = len(tenants)
            tenants.append(
                {
                    "id": _new_id(rng),
                    "name": _tenant_names()[index],
                    "tier": tier,
                    "tax_exempt": index % 9 == 0,
                    "status": "suspended" if index in {8, 31, 52} else "active",
                    "region": REGION_CODES[index % len(REGION_CODES)],
                }
            )
    _write_csv(
        output / "billing_tenants.csv",
        CSV_FILES["billing_tenants.csv"],
        (
            [
                tenant["id"],
                tenant["name"],
                "t" if tenant["tax_exempt"] else "f",
                tenant["status"],
            ]
            for tenant in tenants
        ),
    )
    _write_csv(
        output / "billing_tenant_regions.csv",
        ("tenant_id", "region_code"),
        ([tenant["id"], tenant["region"]] for tenant in tenants),
    )

    plans, plan_by_tier = _plan_catalog(rng)
    _write_csv(
        output / "billing_plans.csv",
        CSV_FILES["billing_plans.csv"],
        (
            [
                plan["id"],
                plan["code"],
                plan["tier"],
                plan["monthly_fee"],
                plan["included_units"],
                plan["overage_rate"],
                "t" if plan["active"] else "f",
            ]
            for plan in plans
        ),
    )
    _write_csv(
        output / "billing_subscriptions.csv",
        CSV_FILES["billing_subscriptions.csv"],
        _subscription_rows(rng, tenants, plan_by_tier),
    )
    _write_csv(
        output / "billing_usage_events.csv",
        CSV_FILES["billing_usage_events.csv"],
        _billing_usage_rows(rng, tenants),
    )

    periods: list[list[object]] = []
    periods_by_tenant: dict[str, dict[str, str]] = {}
    for tenant in tenants:
        tenant_periods: dict[str, str] = {}
        for period_start, period_end in (
            ("2026-08-01", "2026-08-31"),
            ("2026-09-01", "2026-09-30"),
        ):
            period_id = _new_id(rng)
            periods.append([period_id, tenant["id"], period_start, period_end])
            tenant_periods[period_start] = period_id
        periods_by_tenant[str(tenant["id"])] = tenant_periods
    _write_csv(
        output / "billing_rating_periods.csv",
        CSV_FILES["billing_rating_periods.csv"],
        periods,
    )
    invoice_rows, invoice_line_rows = _invoice_data(
        rng, tenants, plan_by_tier, periods_by_tenant, enum_values
    )
    _write_csv(
        output / "billing_invoices.csv", CSV_FILES["billing_invoices.csv"], invoice_rows
    )
    _write_csv(
        output / "billing_invoice_lines.csv",
        CSV_FILES["billing_invoice_lines.csv"],
        invoice_line_rows,
    )

    workspaces, _, tenant_workspaces = _build_workspaces(rng, tenants)
    users, memberships, members_by_workspace = _build_users_and_memberships(
        rng, tenants, tenant_workspaces, enum_values["auth_workspace_members.csv"]
    )
    _write_csv(output / "auth_users.csv", CSV_FILES["auth_users.csv"], _auth_user_rows(rng, users))
    _write_csv(
        output / "auth_workspace_members.csv",
        CSV_FILES["auth_workspace_members.csv"],
        memberships,
    )

    documents, document_rows, document_versions = _document_rows(
        rng, users, workspaces, members_by_workspace
    )
    _write_csv(output / "documents.csv", CSV_FILES["documents.csv"], document_rows)
    _write_csv(
        output / "document_versions.csv", CSV_FILES["document_versions.csv"], document_versions
    )
    files, file_rows, file_versions = _file_rows(rng, users, workspaces, members_by_workspace)
    _write_csv(output / "files.csv", CSV_FILES["files.csv"], file_rows)
    _write_csv(output / "file_versions.csv", CSV_FILES["file_versions.csv"], file_versions)

    event_inputs = {
        "collab_events.csv": (
            CSV_FILES["collab_events.csv"],
            50_000,
            "collab",
        ),
        "audit_events.csv": (
            CSV_FILES["audit_events.csv"],
            160_000,
            "audit",
        ),
        "analytics_events.csv": (
            CSV_FILES["analytics_events.csv"],
            120_000,
            "analytics",
        ),
    }
    for filename, (header, count, mode) in event_inputs.items():
        _write_csv(
            output / filename,
            header,
            _event_rows(
                rng,
                users,
                documents,
                files,
                enum_values["audit_actions"],
                enum_values["audit_resources"],
                count,
                mode,
            ),
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the SQL Server source extracts.")
    parser.add_argument("--out", type=Path, default=SOURCE / "build" / "extracts")
    args = parser.parse_args(argv)
    generate(args.out)
    print(f"Generated {len(CSV_FILES)} extracts in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
