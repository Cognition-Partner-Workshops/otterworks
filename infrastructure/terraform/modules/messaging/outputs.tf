output "notification_queue_url" {
  description = "SQS queue URL for notification events"
  value       = aws_sqs_queue.notifications.url
}

output "notification_queue_arn" {
  description = "SQS queue ARN for notification events"
  value       = aws_sqs_queue.notifications.arn
}

output "analytics_queue_url" {
  description = "SQS queue URL for analytics events"
  value       = aws_sqs_queue.analytics_events.url
}

output "analytics_queue_arn" {
  description = "SQS queue ARN for analytics events"
  value       = aws_sqs_queue.analytics_events.arn
}

output "search_indexing_queue_url" {
  description = "SQS queue URL for search indexing"
  value       = aws_sqs_queue.search_indexing.url
}

output "search_indexing_queue_arn" {
  description = "SQS queue ARN for search indexing"
  value       = aws_sqs_queue.search_indexing.arn
}

output "events_topic_arn" {
  description = "SNS topic ARN for system events"
  value       = aws_sns_topic.events.arn
}

output "notification_dlq_arn" {
  description = "SQS dead-letter queue ARN for notification events"
  value       = aws_sqs_queue.notifications_dlq.arn
}

output "analytics_dlq_url" {
  description = "SQS dead-letter queue URL for analytics events"
  value       = aws_sqs_queue.analytics_events_dlq.url
}

output "analytics_dlq_arn" {
  description = "SQS dead-letter queue ARN for analytics events"
  value       = aws_sqs_queue.analytics_events_dlq.arn
}

output "search_indexing_dlq_url" {
  description = "SQS dead-letter queue URL for search indexing"
  value       = aws_sqs_queue.search_indexing_dlq.url
}

output "search_indexing_dlq_arn" {
  description = "SQS dead-letter queue ARN for search indexing"
  value       = aws_sqs_queue.search_indexing_dlq.arn
}

output "dlq_alarm_names" {
  description = "Map of source queue key to its DLQ depth alarm name"
  value       = { for k, a in aws_cloudwatch_metric_alarm.dlq_depth : k => a.alarm_name }
}

output "backlog_alarm_names" {
  description = "Map of source queue key to its oldest-message-age alarm name"
  value       = { for k, a in aws_cloudwatch_metric_alarm.oldest_message_age : k => a.alarm_name }
}
