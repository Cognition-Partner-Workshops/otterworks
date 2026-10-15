# Offline checks that the sandbox only builds run-token resources from the
# production messaging module and never pages anyone.
# Run: terraform init -backend=false && terraform test

mock_provider "aws" {}

override_resource {
  target = module.messaging.aws_sns_topic.events
  values = {
    arn = "arn:aws:sns:us-east-1:111111111111:rs-20261006-ab-events-dev"
  }
}

override_resource {
  target = module.messaging.aws_sqs_queue.analytics_events
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-analytics-events-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/rs-20261006-ab-analytics-events-dev"
  }
}

override_resource {
  target = module.messaging.aws_sqs_queue.analytics_events_dlq
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-analytics-events-dlq-dev"
    url = "https://sqs.us-east-1.amazonaws.com/111111111111/rs-20261006-ab-analytics-events-dlq-dev"
  }
}

override_resource {
  target = module.messaging.aws_sqs_queue.search_indexing
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-search-indexing-dev"
  }
}

override_resource {
  target = module.messaging.aws_sqs_queue.search_indexing_dlq
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-search-indexing-dlq-dev"
  }
}

override_resource {
  target = module.messaging.aws_sqs_queue.notifications
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-notifications-dev"
  }
}

override_resource {
  target = module.messaging.aws_sqs_queue.notifications_dlq
  values = {
    arn = "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-notifications-dlq-dev"
  }
}

override_resource {
  target = aws_dynamodb_table.ledger
  values = {
    arn = "arn:aws:dynamodb:us-east-1:111111111111:table/rs-20261006-ab-analytics-ledger"
  }
}

variables {
  run_token = "rs-20261006-ab"
  expires   = "2026-10-07T20:00:00Z"
}

run "builds_the_repaired_module_under_token_names" {
  command = apply

  assert {
    condition     = output.ledger_table_name == "rs-20261006-ab-analytics-ledger"
    error_message = "Ledger table is named after the run token."
  }

  assert {
    condition     = alltrue([for n in concat(values(output.dlq_alarm_names), values(output.backlog_alarm_names)) : startswith(n, "rs-20261006-ab-")])
    error_message = "Every alarm is named after the run token."
  }

  assert {
    condition     = output.analytics_dlq_arn == "arn:aws:sqs:us-east-1:111111111111:rs-20261006-ab-analytics-events-dlq-dev"
    error_message = "The analytics DLQ comes from the messaging module."
  }

  assert {
    condition     = output.max_receive_count == 5
    error_message = "Sandbox uses the module's default maxReceiveCount."
  }
}

run "ledger_outage_is_off_by_default_and_scoped_to_the_ledger" {
  command = apply

  assert {
    condition     = jsondecode(aws_dynamodb_resource_policy.ledger_outage.policy).Statement[0].Condition.DateLessThan["aws:CurrentTime"] == "1970-01-01T00:00:00Z"
    error_message = "Without ledger_outage_until the deny window is in the past."
  }

  assert {
    condition     = jsondecode(aws_dynamodb_resource_policy.ledger_outage.policy).Statement[0].Effect == "Deny" && toset(jsondecode(aws_dynamodb_resource_policy.ledger_outage.policy).Statement[0].Action) == toset(["dynamodb:PutItem", "dynamodb:UpdateItem"])
    error_message = "The outage only denies ledger writes."
  }

  assert {
    condition     = aws_dynamodb_resource_policy.ledger_outage.resource_arn == aws_dynamodb_table.ledger.arn
    error_message = "The outage policy only attaches to the token's ledger."
  }
}

run "an_outage_window_reaches_the_policy" {
  command = plan

  variables {
    ledger_outage_until = "2026-10-06T22:30:00Z"
  }

  assert {
    condition     = jsondecode(aws_dynamodb_resource_policy.ledger_outage.policy).Statement[0].Condition.DateLessThan["aws:CurrentTime"] == "2026-10-06T22:30:00Z"
    error_message = "ledger_outage_until sets the deny window."
  }
}

run "accepts_live_proof_tokens" {
  command = plan

  variables {
    run_token = "lp-20261006-ab"
  }

  assert {
    condition     = aws_dynamodb_table.ledger.name == "lp-20261006-ab-analytics-ledger"
    error_message = "lp- tokens name their own ledger."
  }
}

run "rejects_tokens_outside_the_sandbox_namespace" {
  command = plan

  variables {
    run_token = "otterworks-dev"
  }

  expect_failures = [var.run_token]
}

run "rejects_a_non_rfc3339_outage" {
  command = plan

  variables {
    ledger_outage_until = "soon"
  }

  expect_failures = [var.ledger_outage_until]
}

run "rejects_a_non_rfc3339_expiry" {
  command = plan

  variables {
    expires = "tomorrow"
  }

  expect_failures = [var.expires]
}
