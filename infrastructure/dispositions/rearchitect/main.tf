locals {
  name = var.run_token

  tags = merge(var.extra_tags, {
    run_token            = var.run_token
    RunToken             = var.run_token
    Expires              = var.expires
    ManagedBy            = "terraform"
    disposition          = "rearchitect"
    service              = var.service_name
    disposition_evidence = var.disposition_evidence
  })

  function_names = { for context, _ in var.contexts : context => "${local.name}-${context}" }
  default_route_context = coalesce(
    var.default_route_context,
    sort(keys(var.contexts))[0]
  )
  publishing_contexts = {
    for context, settings in var.contexts : context => settings
    if settings.publishes_events
  }
  account           = var.account_id != null ? var.account_id : data.aws_caller_identity.current[0].account_id
  arn_scope         = "arn:${data.aws_partition.current.partition}"
  bus_name          = "${var.service_name}-${local.name}"
  probe_name        = "${local.name}-probe"
  probe_enabled     = length(var.probe_steps) > 0
  page_enabled      = var.devin_webhook_url != "" && nonsensitive(var.devin_webhook_secret != "")
  page_rule_name    = "${local.name}-page-devin"
  alarm_5xx_name    = "${local.name}-api-5xx-rate"
  alarm_errors_name = "${local.name}-lambda-errors"
  alarm_page_name   = "${local.name}-page"
}

data "aws_partition" "current" {}

data "aws_region" "current" {}

data "aws_caller_identity" "current" {
  count = var.account_id == null ? 1 : 0
}
