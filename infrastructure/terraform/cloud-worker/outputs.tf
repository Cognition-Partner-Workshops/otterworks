output "sns_topic_arn" {
  value = aws_sns_topic.events.arn
}

output "sqs_queue_url" {
  value = aws_sqs_queue.notifications.url
}

output "sqs_queue_arn" {
  value = aws_sqs_queue.notifications.arn
}

output "sqs_dlq_url" {
  value = aws_sqs_queue.notifications_dlq.url
}

output "sqs_dlq_arn" {
  value = aws_sqs_queue.notifications_dlq.arn
}

output "dynamodb_table" {
  value = aws_dynamodb_table.notifications.name
}

output "dynamodb_preferences_table" {
  value = aws_dynamodb_table.notification_preferences.name
}

output "irsa_notification_service_role_arn" {
  value = aws_iam_role.notification_service.arn
}

output "irsa_file_service_role_arn" {
  value = aws_iam_role.file_service.arn
}

output "devin_observer_role_arn" {
  value = aws_iam_role.devin_observer.arn
}

output "devin_builder_role_arn" {
  value = aws_iam_role.devin_builder.arn
}

output "devin_reader_user_name" {
  value = aws_iam_user.devin_reader.name
}

output "alarm_name" {
  value = aws_cloudwatch_metric_alarm.dlq_depth.alarm_name
}

output "dashboard_url" {
  value = "https://${local.region}.console.aws.amazon.com/cloudwatch/home?region=${local.region}#dashboards:name=${aws_cloudwatch_dashboard.cloud_worker.dashboard_name}"
}

output "eventbridge_rule_name" {
  value = aws_cloudwatch_event_rule.dlq_alarm.name
}
