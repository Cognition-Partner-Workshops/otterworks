# ------------------------------------------------------------------------------
# Cost guardrail
#
# The platform ran at ~$1,320/month for months before anyone looked, and roughly
# two thirds of that was buying nothing: an idle OpenSearch collection, load
# balancers with no backends, and an EKS extended-support penalty. None of it
# was visible until someone read the bill.
#
# A budget does not stop spend, but it converts "discovered eventually" into
# "alerted the same week". Thresholds are set against the design target in
# demo-platform/docs/cost-and-scale.md (~$570/month), not against what the
# account happens to cost today, so drift back toward the old shape alerts.
#
# The budget filters on the Project tag, so the tag has to be activated for
# cost allocation or the budget reads $0 forever. Activation is not
# retroactive and takes up to a day to reach Cost Explorer.
# ------------------------------------------------------------------------------

resource "aws_ce_cost_allocation_tag" "project" {
  tag_key = "Project"
  status  = "Active"
}

resource "aws_budgets_budget" "monthly" {
  count = var.budget_alert_emails != null && length(var.budget_alert_emails) > 0 ? 1 : 0

  name         = "otterworks-${var.environment}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$otterworks"]
  }

  # Actual spend past 80% -- something is running that probably should not be.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.budget_alert_emails
  }

  # Forecast past 100% catches a resource left running on day 3 of the month,
  # which is the failure mode that produced the original bill.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = var.budget_alert_emails
  }
}
