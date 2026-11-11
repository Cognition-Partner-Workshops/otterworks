# ruff: noqa: E501  (HTML and Tableau XML templates)
"""Write the legacy Tableau workbooks that report off the SQL Server warehouse.

Each workbook re-implements one or more of the SSRS reports in source/reports/
as Tableau custom SQL against OtterWorksUBW. Column types come from SQL Server
itself, so the warehouse has to be up (make sfm-up) when this runs. The same
pass writes gate/bi/workbooks.yaml: the keys the report parity check aligns
rows on and the legacy procedures behind every workbook.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import uuid
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import pymssql
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
REPORTS = ROOT / "source" / "reports"
PROCS = ROOT / "source" / "procs"
SPEC = ROOT / "gate" / "bi" / "workbooks.yaml"

BUSINESS_DATE = "2026-09-15"
PARAM_DATE = "<[Parameters].[Business Date]>"
PARAM_TIER = "<[Parameters].[Plan Tier]>"

SERVER = "127.0.0.1"
PORT = "14333"
DATABASE = "OtterWorksUBW"
REPORT_USER = "sa"

TENANT = ["business_date", "tenant_id"]

# name, folder, datasources (caption, report, keys[, extra select columns]), sheets
# sheet: (name, datasource caption, mark, dimension, measure, aggregation)
WORKBOOKS = [
    (
        "Storage Overage",
        "Billing",
        [
            ("Overage Charges", "rpt_overage_charges", TENANT),
            ("Overage by Tier", "rpt_overage_by_tier", ["business_date", "plan_tier"]),
            ("Storage vs Included", "rpt_storage_vs_included", TENANT),
        ],
        [
            (
                "Overage Revenue by Tenant",
                "Overage Charges",
                "Bar",
                "tenant_name",
                "overage_cents",
                "sum",
            ),
            ("Overage GB by Plan Tier", "Overage by Tier", "Bar", "plan_tier", "overage_gb", "sum"),
            (
                "Storage vs Included",
                "Storage vs Included",
                "Text",
                ["tenant_name", "plan_tier"],
                ["bytes_used", "included_bytes", "overage_gb"],
                "sum",
            ),
        ],
    ),
    (
        "Invoice Lines",
        "Billing",
        [
            ("Invoice Lines", "rpt_invoice_lines", ["business_date", "invoice_id", "line_no"]),
        ],
        [
            ("Amount by Line Type", "Invoice Lines", "Bar", "line_type", "amount_cents", "sum"),
            (
                "Invoice Line Detail",
                "Invoice Lines",
                "Text",
                ["invoice_id", "line_no", "line_type"],
                ["amount_cents"],
                "sum",
            ),
        ],
    ),
    (
        "Invoice Totals by Tenant",
        "Billing",
        [
            ("Invoice Totals", "rpt_invoice_totals_by_tenant", TENANT),
        ],
        [
            (
                "Billed Amount by Tenant",
                "Invoice Totals",
                "Bar",
                "tenant_id",
                "amount_cents",
                "sum",
            ),
            (
                "Invoices per Tenant",
                "Invoice Totals",
                "Text",
                ["tenant_id"],
                ["invoice_count", "amount_cents"],
                "sum",
            ),
        ],
    ),
    (
        "Monthly Billing Summary",
        "Billing",
        [
            (
                "Billing Summary",
                "rpt_monthly_billing_summary",
                ["business_date", "line_type", "invoice_status"],
            ),
        ],
        [
            (
                "Amount by Invoice Status",
                "Billing Summary",
                "Bar",
                "invoice_status",
                "amount_cents",
                "sum",
            ),
            (
                "Lines by Type and Status",
                "Billing Summary",
                "Text",
                ["line_type", "invoice_status"],
                ["line_count", "amount_cents"],
                "sum",
            ),
        ],
    ),
    (
        "Tenant Usage Daily",
        "Usage",
        [
            ("Tenant Usage", "rpt_tenant_usage_daily", TENANT),
        ],
        [
            ("API Units by Tenant", "Tenant Usage", "Bar", "tenant_name", "api_units", "sum"),
            (
                "Usage Detail",
                "Tenant Usage",
                "Text",
                ["tenant_name", "region_code"],
                ["api_units", "compute_units", "active_users"],
                "sum",
            ),
        ],
    ),
    (
        "Top 20 Tenants by Storage",
        "Usage",
        [
            ("Top Tenants", "rpt_tenant_usage_top20", TENANT),
        ],
        [
            ("Bytes Used, Top 20", "Top Tenants", "Bar", "tenant_name", "bytes_used", "sum"),
            (
                "Top 20 Detail",
                "Top Tenants",
                "Text",
                ["tenant_name", "plan_tier"],
                ["bytes_used", "storage_peak_mb"],
                "sum",
            ),
        ],
    ),
    (
        "Usage by Region",
        "Usage",
        [
            ("Region Usage", "rpt_tenant_usage_by_region", ["business_date", "region_code"]),
        ],
        [
            ("API Units by Region", "Region Usage", "Bar", "region_code", "api_units", "sum"),
            ("Bytes Used by Region", "Region Usage", "Bar", "region_code", "bytes_used", "sum"),
            (
                "Region Detail",
                "Region Usage",
                "Text",
                ["region_code"],
                ["tenant_count", "compute_units"],
                "sum",
            ),
        ],
    ),
    (
        "Active Users",
        "Usage",
        [
            ("Active Users", "rpt_tenant_active_users", TENANT),
        ],
        [
            ("Active Users by Tenant", "Active Users", "Bar", "tenant_name", "active_users", "sum"),
            (
                "Active Users by Plan Tier",
                "Active Users",
                "Bar",
                "plan_tier",
                "active_users",
                "sum",
            ),
        ],
    ),
    (
        "API and Compute Units",
        "Usage",
        [
            ("API Units", "rpt_tenant_api_units", TENANT),
            ("Compute Units", "rpt_tenant_compute_units", TENANT),
        ],
        [
            ("API Units by Plan Tier", "API Units", "Bar", "plan_tier", "api_units", "sum"),
            (
                "Compute Units by Tenant",
                "Compute Units",
                "Bar",
                "tenant_name",
                "compute_units",
                "sum",
            ),
        ],
    ),
    (
        "Storage Peak",
        "Usage",
        [
            ("Storage Peak", "rpt_tenant_storage_peak", TENANT),
        ],
        [
            (
                "Peak Storage MB by Tenant",
                "Storage Peak",
                "Bar",
                "tenant_name",
                "storage_peak_mb",
                "sum",
            ),
            (
                "Peak Storage Detail",
                "Storage Peak",
                "Text",
                ["tenant_name", "plan_tier"],
                ["storage_peak_mb", "bytes_used"],
                "sum",
            ),
        ],
    ),
    (
        "Content Inventory",
        "Usage",
        [
            ("Content Counts", "rpt_tenant_content_counts", TENANT),
            (
                "Document Status",
                "rpt_document_status",
                ["business_date", "tenant_id", "workspace_id", "status_label"],
            ),
        ],
        [
            (
                "Documents by Tenant",
                "Content Counts",
                "Bar",
                "tenant_name",
                "document_count",
                "sum",
            ),
            (
                "Documents by Status",
                "Document Status",
                "Bar",
                "status_label",
                "document_count",
                "sum",
            ),
            ("Words by Status", "Document Status", "Bar", "status_label", "word_count", "sum"),
        ],
    ),
    (
        "Plan Mix",
        "Plans and Seats",
        [
            ("Plan Mix", "rpt_plan_mix", ["business_date", "plan_tier"]),
            ("Plan Tier Summary", "rpt_plan_tier_summary", ["business_date", "plan_tier"]),
        ],
        [
            ("Tenants by Plan Tier", "Plan Mix", "Bar", "plan_tier", "tenant_count", "sum"),
            ("Seats by Plan Tier", "Plan Mix", "Bar", "plan_tier", "seat_count", "sum"),
            (
                "Selected Tier",
                "Plan Tier Summary",
                "Text",
                ["plan_tier"],
                ["tenant_count", "seat_count", "tenants_over_limit", "avg_seats_per_tenant"],
                "sum",
            ),
        ],
    ),
    (
        "Seat Utilization",
        "Plans and Seats",
        [
            ("Seat Utilization", "rpt_seat_utilization", TENANT),
            ("Seat Counts", "rpt_seat_count_by_tenant", TENANT),
        ],
        [
            ("Utilization by Tenant", "Seat Utilization", "Bar", "tenant_id", "utilization", "sum"),
            ("Seats by Plan Tier", "Seat Counts", "Bar", "plan_tier", "seat_count", "sum"),
            ("Seat Limits by Plan Tier", "Seat Counts", "Bar", "plan_tier", "seat_limit", "sum"),
        ],
    ),
    (
        "Seat Headroom",
        "Plans and Seats",
        [
            ("Seat Headroom", "rpt_seat_limit_headroom", TENANT),
            ("Seats Over Limit", "rpt_seats_over_limit", TENANT),
        ],
        [
            ("Headroom by Tenant", "Seat Headroom", "Bar", "tenant_id", "seat_headroom", "sum"),
            (
                "Tenants Over Limit",
                "Seats Over Limit",
                "Text",
                ["tenant_id", "plan_tier"],
                ["seat_count", "seat_limit"],
                "sum",
            ),
        ],
    ),
    (
        "Storage Growth Trend",
        "Capacity",
        [
            (
                "Storage Growth",
                "rpt_storage_growth_trend",
                ["business_date", "tenant_id", "observation_date"],
            ),
        ],
        [
            (
                "Bytes Used over Time",
                "Storage Growth",
                "Line",
                "observation_date",
                "bytes_used",
                "sum",
            ),
            (
                "Peak Storage MB over Time",
                "Storage Growth",
                "Line",
                "observation_date",
                "peak_storage_mb",
                "sum",
            ),
        ],
    ),
    (
        "Retention Summary",
        "Retention",
        [
            (
                "Retention Summary",
                "rpt_retention_summary",
                ["business_date", "tenant_id", "resource_type", "retention_action"],
            ),
            (
                "Archived Content",
                "rpt_archived_content",
                ["business_date", "tenant_id", "resource_type", "retention_action"],
            ),
        ],
        [
            (
                "Items by Retention Action",
                "Retention Summary",
                "Bar",
                "retention_action",
                "item_count",
                "sum",
            ),
            (
                "Items by Resource Type",
                "Retention Summary",
                "Bar",
                "resource_type",
                "item_count",
                "sum",
            ),
            ("Archived Items", "Archived Content", "Bar", "resource_type", "item_count", "sum"),
        ],
    ),
    (
        "Retention Candidates",
        "Retention",
        [
            (
                "Retention Candidates",
                "rpt_retention_candidates",
                ["business_date", "tenant_id", "resource_type", "resource_id", "retention_action"],
            ),
            (
                "Purge Candidates",
                "rpt_trash_purge_candidates",
                ["business_date", "tenant_id", "resource_type", "resource_id", "retention_action"],
            ),
        ],
        [
            (
                "Candidates by Action",
                "Retention Candidates",
                "Bar",
                "retention_action",
                "resource_id",
                "cnt",
            ),
            (
                "Purge Candidates by Type",
                "Purge Candidates",
                "Bar",
                "resource_type",
                "resource_id",
                "cnt",
            ),
            (
                "Average Age by Action",
                "Retention Candidates",
                "Bar",
                "retention_action",
                "days_since_update",
                "avg",
            ),
        ],
    ),
    (
        "Audit Rollup",
        "Audit",
        [
            (
                "Audit Rollup",
                "rpt_audit_rollup",
                ["business_date", "tenant_id", "action", "resource_type"],
            ),
        ],
        [
            ("Events by Action", "Audit Rollup", "Bar", "action", "event_count", "sum"),
            (
                "Events by Resource Type",
                "Audit Rollup",
                "Bar",
                "resource_type",
                "event_count",
                "sum",
            ),
        ],
    ),
    (
        "Audit User Activity",
        "Audit",
        [
            (
                "User Activity",
                "rpt_audit_user_activity",
                ["business_date", "audit_id"],
                ["audit_id"],
            ),
        ],
        [
            ("Events by Action", "User Activity", "Bar", "action", "audit_id", "cnt"),
            ("Events by Resource Type", "User Activity", "Bar", "resource_type", "audit_id", "cnt"),
        ],
    ),
    (
        "Sensitive Actions",
        "Audit",
        [
            (
                "Sensitive Actions",
                "rpt_audit_sensitive_actions",
                ["business_date", "audit_id"],
                ["audit_id"],
            ),
        ],
        [
            ("Sensitive Actions by Type", "Sensitive Actions", "Bar", "action", "audit_id", "cnt"),
            (
                "Sensitive Actions by Tenant",
                "Sensitive Actions",
                "Bar",
                "tenant_id",
                "audit_id",
                "cnt",
            ),
        ],
    ),
]

TOLERANCES = {"rpt_seat_utilization": {"utilization": 0.000001}}

TYPE_MAP = {
    "int": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "tinyint": "integer",
    "bit": "integer",
    "decimal": "real",
    "numeric": "real",
    "float": "real",
    "real": "real",
    "money": "real",
    "date": "date",
    "datetime": "datetime",
    "datetime2": "datetime",
    "datetimeoffset": "datetime",
}


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def stable_id(*parts: str) -> str:
    return hashlib.sha1("/".join(parts).encode()).hexdigest()[:28]


def stable_uuid(*parts: str) -> str:
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "ubw-tableau/" + "/".join(parts))).upper() + "}"


def report_sql(report: str, extra: list[str]) -> str:
    text = (REPORTS / f"{report}.rdl").read_text()
    sql = html.unescape(re.search(r"<CommandText>(.*?)</CommandText>", text, re.S).group(1)).strip()
    if extra:
        sql = re.sub(r"^SELECT ", "SELECT " + ", ".join(extra) + ", ", sql, count=1)
    return sql.replace("@BusinessDate", PARAM_DATE).replace("@PlanTier", PARAM_TIER)


def describe(cursor, sql: str) -> list[tuple[str, str]]:
    probe = sql.replace(PARAM_DATE, f"'{BUSINESS_DATE}'").replace(PARAM_TIER, "'growth'")
    cursor.execute("EXEC sp_describe_first_result_set @tsql = %s", (probe,))
    columns = []
    for row in cursor.fetchall():
        name, system_type = row[2], row[5]
        base = system_type.split("(")[0].lower()
        columns.append((name, TYPE_MAP.get(base, "string")))
    return columns


def proc_tables(proc: Path) -> tuple[set[str], set[str]]:
    text = proc.read_text().lower()
    reads = set(re.findall(r"(?:from|join)\s+([a-z_]+\.[a-z_]+)", text))
    writes = set(re.findall(r"(?:into|update|merge(?:\s+into)?)\s+([a-z_]+\.[a-z_]+)", text))
    return reads - writes, writes


def lineage(tables: set[str]) -> list[str]:
    writers: dict[str, set[str]] = {}
    reads_of: dict[str, set[str]] = {}
    for proc in sorted(PROCS.glob("usp_*.sql")):
        unit = proc.stem.removeprefix("usp_")
        reads, writes = proc_tables(proc)
        reads_of[unit] = reads
        for table in writes:
            writers.setdefault(table, set()).add(unit)
    seen: set[str] = set()
    pending = set(tables)
    visited: set[str] = set()
    while pending:
        table = pending.pop()
        if table in visited:
            continue
        visited.add(table)
        for unit in writers.get(table, set()):
            if unit in {"log_run", "purge_expired"}:
                continue
            if unit not in seen:
                seen.add(unit)
                pending |= reads_of[unit]
    order = [
        line.split(":", 1)[1].strip()
        for line in (ROOT / "gate" / "manifest.yaml").read_text().splitlines()
        if line.strip().startswith("- unit:")
    ]
    return [unit for unit in order if unit in seen]


def column_xml(name: str, datatype: str) -> str:
    role, kind = (
        ("measure", "quantitative")
        if datatype in {"integer", "real"} and not name.endswith("_id") and name not in {"line_no"}
        else ("dimension", "nominal" if datatype == "string" else "ordinal")
    )
    if datatype in {"date", "datetime"}:
        role, kind = "dimension", "ordinal"
    return f"<column datatype='{datatype}' name='[{name}]' role='{role}' type='{kind}' />"


def instance(field: str, aggregation: str | None) -> tuple[str, str]:
    if aggregation is None:
        return (
            f"[none:{field}:nk]",
            f"<column-instance column='[{field}]' derivation='None' name='[none:{field}:nk]' pivot='key' type='nominal' />",
        )
    derivation = {"sum": "Sum", "cnt": "Count", "avg": "Avg"}[aggregation]
    name = f"[{aggregation}:{field}:qk]"
    return (
        name,
        f"<column-instance column='[{field}]' derivation='{derivation}' name='{name}' pivot='key' type='quantitative' />",
    )


def worksheet_xml(
    workbook: str, sheet, ds_names: dict[str, str], ds_columns: dict[str, list[tuple[str, str]]]
) -> str:
    name, ds_caption, mark, dimension, measure, aggregation = sheet
    ds = ds_names[ds_caption]
    types = dict(ds_columns[ds_caption])
    dims = dimension if isinstance(dimension, list) else [dimension]
    measures = measure if isinstance(measure, list) else [measure]
    deps = [column_xml(field, types[field]) for field in dict.fromkeys(dims + measures)]
    dim_refs, measure_refs = [], []
    for field in dims:
        ref, xml = instance(field, None)
        dim_refs.append(f"[{ds}].{ref}")
        deps.append(xml)
    for field in measures:
        ref, xml = instance(field, aggregation)
        measure_refs.append(f"[{ds}].{ref}")
        deps.append(xml)
    view_extra, encodings, filters = "", "", ""
    if mark == "Bar":
        rows, cols = dim_refs[0], measure_refs[0]
        view_extra = f"<sort class='computed' column={quoteattr(dim_refs[0])} direction='DESC' using={quoteattr(measure_refs[0])} />"
    elif mark == "Line":
        rows, cols = measure_refs[0], dim_refs[0]
    else:
        rows = "(" + " / ".join(dim_refs) + ")" if len(dim_refs) > 1 else dim_refs[0]
        cols = f"[{ds}].[:Measure Names]"
        members = "".join(
            f"<groupfilter function='member' level='[:Measure Names]' member={quoteattr(chr(34) + ref + chr(34))} />"
            for ref in measure_refs
        )
        filters = f"<filter class='categorical' column='[{ds}].[:Measure Names]'><groupfilter function='union' user:op='manual'>{members}</groupfilter></filter>"
        encodings = f"<encodings><text column='[{ds}].[Multiple Values]' /></encodings>"
    return (
        f"<worksheet name={quoteattr(name)}><table><view>"
        f"<datasources><datasource caption={quoteattr(ds_caption)} name='{ds}' /></datasources>"
        f"<datasource-dependencies datasource='{ds}'>{''.join(deps)}</datasource-dependencies>"
        f"{filters}{view_extra}<aggregation value='true' /></view><style />"
        f"<panes><pane selection-relaxation-option='selection-relaxation-allow'><view><breakdown value='auto' /></view>"
        f"<mark class='{mark}' />{encodings}</pane></panes>"
        f"<rows>{escape(rows)}</rows><cols>{escape(cols)}</cols></table>"
        f"<simple-id uuid='{stable_uuid(workbook, name)}' /></worksheet>"
    )


def datasource_xml(
    workbook: str, caption: str, ds: str, sql: str, columns: list[tuple[str, str]]
) -> str:
    conn = "sqlserver." + stable_id(workbook, caption, "conn")
    return (
        f"<datasource caption={quoteattr(caption)} inline='true' name='{ds}' version='18.1'>"
        f"<connection class='federated'><named-connections>"
        f"<named-connection caption='{SERVER}' name='{conn}'>"
        f"<connection authentication='sqlserver' class='sqlserver' dbname='{DATABASE}' odbc-native-protocol='' "
        f"one-time-sql='' port='{PORT}' server='{SERVER}' username='{REPORT_USER}' />"
        f"</named-connection></named-connections>"
        f"<relation connection='{conn}' name='Custom SQL Query' type='text'>{escape(sql)}</relation>"
        f"</connection><aliases enabled='yes' />"
        + "".join(column_xml(name, datatype) for name, datatype in columns)
        + "</datasource>"
    )


PARAMETERS = (
    "<datasource hasconnection='false' inline='true' name='Parameters' version='18.1'><aliases enabled='yes' />"
    f"<column caption='Business Date' datatype='date' name='[Business Date]' param-domain-type='any' role='measure' type='quantitative' value='#{BUSINESS_DATE}#'>"
    f"<calculation class='tableau' formula='#{BUSINESS_DATE}#' /></column>"
    "<column caption='Plan Tier' datatype='string' name='[Plan Tier]' param-domain-type='list' role='measure' type='nominal' value='&quot;growth&quot;'>"
    "<calculation class='tableau' formula='&quot;growth&quot;' /><members>"
    "<member value='&quot;starter&quot;' /><member value='&quot;growth&quot;' /><member value='&quot;scale&quot;' /></members></column>"
    "</datasource>"
)


def dashboard_xml(name: str, sheets: list[str]) -> str:
    height = 100000 // len(sheets)
    zones = "".join(
        f"<zone h='{height}' id='{index + 2}' name={quoteattr(sheet)} w='100000' x='0' y='{index * height}' />"
        for index, sheet in enumerate(sheets)
    )
    return (
        f"<dashboard name={quoteattr(name)}><style /><size maxheight='900' maxwidth='1200' minheight='900' minwidth='1200' />"
        f"<zones><zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>{zones}</zone></zones>"
        f"<simple-id uuid='{stable_uuid(name, 'dashboard')}' /></dashboard>"
    )


def main() -> None:
    connection = pymssql.connect(
        server=os.environ.get("UBW_SQL_HOST", SERVER),
        port=int(os.environ.get("UBW_SQL_PORT", PORT)),
        user=os.environ.get("UBW_SQL_USER", "sa"),
        password=os.environ["UBW_SQL_PASSWORD"],
        database=DATABASE,
    )
    cursor = connection.cursor()
    spec = {"business_dates": ["2026-09-15", "2026-09-30"], "workbooks": []}
    for name, folder, datasources, sheets in WORKBOOKS:
        ds_names, ds_columns, ds_xml, ds_spec, tables = {}, {}, [], [], set()
        for entry in datasources:
            caption, report, keys = entry[:3]
            extra = entry[3] if len(entry) > 3 else []
            sql = report_sql(report, extra)
            ds = "federated." + stable_id(name, caption)
            columns = describe(cursor, sql)
            ds_names[caption], ds_columns[caption] = ds, columns
            ds_xml.append(datasource_xml(name, caption, ds, sql, columns))
            tables |= set(re.findall(r"(?:FROM|JOIN)\s+([a-z_]+\.[a-z_]+)", sql))
            item = {"caption": caption, "report": report, "keys": list(keys)}
            if report in TOLERANCES:
                item["tolerance"] = TOLERANCES[report]
            ds_spec.append(item)
        worksheets = "".join(worksheet_xml(name, sheet, ds_names, ds_columns) for sheet in sheets)
        twb = (
            "<?xml version='1.0' encoding='utf-8' ?>\n"
            "<workbook original-version='18.1' source-build='2023.3.0 (20233.23.1017.0948)' source-platform='win' version='18.1' "
            "xmlns:user='http://www.tableausoftware.com/xml/user'>"
            "<preferences><preference name='ui.encoding.shelf.height' value='24' /></preferences>"
            f"<datasources>{PARAMETERS}{''.join(ds_xml)}</datasources>"
            f"<worksheets>{worksheets}</worksheets>"
            f"<dashboards>{dashboard_xml(name, [sheet[0] for sheet in sheets])}</dashboards>"
            "</workbook>\n"
        )
        filename = f"{name}.twb"
        (HERE / filename).write_text(twb.replace("><", ">\n<"))
        spec["workbooks"].append(
            {
                "name": name,
                "file": filename,
                "folder": folder,
                "legacy_tables": sorted(tables),
                "units": lineage(tables),
                "datasources": ds_spec,
            }
        )
        print(f"wrote {filename}")
    SPEC.write_text(
        "# Report-level parity contract for the Tableau estate. Written by source/tableau/generate.py.\n"
        "# Read-only for worker sessions, like gate/manifest.yaml.\n"
        + yaml.safe_dump(spec, sort_keys=False, width=120)
    )


if __name__ == "__main__":
    main()
