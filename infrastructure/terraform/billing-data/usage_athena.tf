# Usage summary on Athena: a Glue table over s3://<bucket>/usage/ (the export's
# headerless gzip CSV), an Athena workgroup writing its results to
# s3://<bucket>/athena-results/, and the usage_summary named queries that
# reproduce billing.fn_usage_summary. manifests/usage/ sits outside the table
# location, so it is never read as data.

locals {
  glue_database     = "${local.db_name}_billing"
  usage_table       = "usage_events"
  athena_workgroup  = "${local.name}-billing"
  usage_location    = "s3://${aws_s3_bucket.usage.id}/usage/"
  athena_results    = "s3://${aws_s3_bucket.usage.id}/athena-results/"
  usage_period_from = "2020-01"
}

resource "aws_glue_catalog_database" "billing" {
  name        = local.glue_database
  description = "Billing usage exported from ${local.db_name} (run ${var.run_token})"
}

# Partition projection on period (yyyy-MM, one per month), so no crawler and no
# MSCK REPAIR: a new month is queryable as soon as the export writes it, and a
# projected month without an object reads as zero rows.
resource "aws_glue_catalog_table" "usage_events" {
  name          = local.usage_table
  database_name = aws_glue_catalog_database.billing.name
  description   = "billing.usage_events as exported nightly by ${local.usage_export}"
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    EXTERNAL                          = "TRUE"
    classification                    = "csv"
    compressionType                   = "gzip"
    "skip.header.line.count"          = "0"
    "projection.enabled"              = "true"
    "projection.period.type"          = "date"
    "projection.period.format"        = "yyyy-MM"
    "projection.period.range"         = "${local.usage_period_from},NOW"
    "projection.period.interval"      = "1"
    "projection.period.interval.unit" = "MONTHS"
    "storage.location.template"       = "${local.usage_location}period=$${period}/"
    run_token                         = var.run_token
    Expires                           = var.expires
  }

  partition_keys {
    name    = "period"
    type    = "string"
    comment = "UTC month of occurred_at, yyyy-mm"
  }

  storage_descriptor {
    location      = local.usage_location
    input_format  = "org.apache.hadoop.mapred.TextInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat"

    ser_de_info {
      name                  = "usage-csv"
      serialization_library = "org.apache.hadoop.hive.serde2.lazy.LazySimpleSerDe"
      parameters = {
        "field.delim"          = ","
        "serialization.format" = ","
      }
    }

    columns {
      name    = "event_id"
      type    = "string"
      comment = "billing.usage_events.id"
    }
    columns {
      name = "tenant_id"
      type = "string"
    }
    columns {
      name    = "kind"
      type    = "string"
      comment = "api, storage, compute"
    }
    columns {
      name = "units"
      type = "int"
    }
    columns {
      name    = "occurred_at"
      type    = "timestamp"
      comment = "UTC"
    }
    columns {
      name    = "usage_date"
      type    = "date"
      comment = "occurred_at::date, UTC"
    }
  }
}

resource "aws_athena_workgroup" "billing" {
  name          = local.athena_workgroup
  description   = "Usage summary queries over ${local.glue_database}.${local.usage_table}"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 1073741824

    engine_version {
      selected_engine_version = "Athena engine version 3"
    }

    result_configuration {
      output_location       = local.athena_results
      expected_bucket_owner = data.aws_caller_identity.current.account_id

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

# Same semantics as billing.fn_usage_summary(p_tenant_id, p_period_start, p_period_end):
#   WHERE tenant_id = p_tenant_id AND occurred_at::date BETWEEN start AND end
#   GROUP BY kind, count(*), COALESCE(sum(units), 0), ORDER BY kind
# Execution parameters are positional and each ? is used once, so the period
# bounds are passed twice: once for the partition filter, once for the date filter.
#   ExecutionParameters: ['<tenant uuid>', '<start yyyy-mm-dd>', '<end yyyy-mm-dd>', '<start>', '<end>']
resource "aws_athena_named_query" "usage_summary" {
  name        = "usage_summary"
  workgroup   = aws_athena_workgroup.billing.id
  database    = aws_glue_catalog_database.billing.name
  description = "billing.fn_usage_summary on Athena. Params: tenant_id, period_start, period_end, period_start, period_end (dates yyyy-mm-dd)."
  query       = <<-SQL
    SELECT u.kind, count(*) AS event_count, coalesce(sum(u.units), 0) AS units
    FROM ${local.glue_database}.${local.usage_table} u
    WHERE u.tenant_id = ?
      AND CAST(u.occurred_at AS date) BETWEEN CAST(? AS date) AND CAST(? AS date)
      AND u.period BETWEEN date_format(CAST(? AS date), '%Y-%m') AND date_format(CAST(? AS date), '%Y-%m')
    GROUP BY u.kind
    ORDER BY u.kind
  SQL
}

# All tenants at once, for the legacy comparison: fn_usage_summary per tenant_id.
#   ExecutionParameters: ['<start yyyy-mm-dd>', '<end yyyy-mm-dd>', '<start>', '<end>']
resource "aws_athena_named_query" "usage_summary_all_tenants" {
  name        = "usage_summary_all_tenants"
  workgroup   = aws_athena_workgroup.billing.id
  database    = aws_glue_catalog_database.billing.name
  description = "billing.fn_usage_summary for every tenant. Params: period_start, period_end, period_start, period_end (dates yyyy-mm-dd)."
  query       = <<-SQL
    SELECT u.tenant_id, u.kind, count(*) AS event_count, coalesce(sum(u.units), 0) AS units
    FROM ${local.glue_database}.${local.usage_table} u
    WHERE CAST(u.occurred_at AS date) BETWEEN CAST(? AS date) AND CAST(? AS date)
      AND u.period BETWEEN date_format(CAST(? AS date), '%Y-%m') AND date_format(CAST(? AS date), '%Y-%m')
    GROUP BY u.tenant_id, u.kind
    ORDER BY u.tenant_id, u.kind
  SQL
}
