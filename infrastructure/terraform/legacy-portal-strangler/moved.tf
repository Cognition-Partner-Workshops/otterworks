# Addresses before the root served more than the announcements module (run lp-ann-20261006-a1).
moved {
  from = aws_lambda_function.announcements
  to   = aws_lambda_function.this
}

moved {
  from = aws_apigatewayv2_integration.announcements
  to   = aws_apigatewayv2_integration.lambda
}

moved {
  from = aws_apigatewayv2_route.announcements
  to   = aws_apigatewayv2_route.module
}

moved {
  from = aws_cloudwatch_event_bus.this
  to   = aws_cloudwatch_event_bus.this[0]
}

moved {
  from = aws_cloudwatch_event_rule.announcement_published
  to   = aws_cloudwatch_event_rule.announcement_published[0]
}

moved {
  from = aws_sqs_queue.notifications_dlq
  to   = aws_sqs_queue.notifications_dlq[0]
}

moved {
  from = aws_sqs_queue.notifications
  to   = aws_sqs_queue.notifications[0]
}

moved {
  from = aws_sqs_queue_policy.notifications
  to   = aws_sqs_queue_policy.notifications[0]
}

moved {
  from = aws_sqs_queue_policy.notifications_dlq
  to   = aws_sqs_queue_policy.notifications_dlq[0]
}

moved {
  from = aws_cloudwatch_event_target.notifications
  to   = aws_cloudwatch_event_target.notifications[0]
}

moved {
  from = aws_cloudwatch_log_group.events
  to   = aws_cloudwatch_log_group.events[0]
}

moved {
  from = aws_cloudwatch_log_resource_policy.events
  to   = aws_cloudwatch_log_resource_policy.events[0]
}

moved {
  from = aws_cloudwatch_event_target.audit_log
  to   = aws_cloudwatch_event_target.audit_log[0]
}
