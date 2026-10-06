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

run "rejects_tokens_outside_the_sandbox_namespace" {
  command = plan

  variables {
    run_token = "lp-20261006-ab"
  }

  expect_failures = [var.run_token]
}

run "rejects_a_non_rfc3339_expiry" {
  command = plan

  variables {
    expires = "tomorrow"
  }

  expect_failures = [var.expires]
}
