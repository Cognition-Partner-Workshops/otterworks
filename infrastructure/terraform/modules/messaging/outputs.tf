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

output "audit_queue_url" {
  description = "SQS queue URL for audit events"
  value       = aws_sqs_queue.audit_events.url
}

output "audit_queue_arn" {
  description = "SQS queue ARN for audit events"
  value       = aws_sqs_queue.audit_events.arn
}

output "event_bus_name" {
  description = "EventBridge bus name for domain events"
  value       = aws_cloudwatch_event_bus.events.name
}

output "event_bus_arn" {
  description = "EventBridge bus ARN for domain events"
  value       = aws_cloudwatch_event_bus.events.arn
}

output "dead_letter_queue_arns" {
  description = "Dead-letter queue ARNs keyed by consumer"
  value = {
    notifications    = aws_sqs_queue.notifications_dlq.arn
    analytics_events = aws_sqs_queue.analytics_events_dlq.arn
    search_indexing  = aws_sqs_queue.search_indexing_dlq.arn
    audit_events     = aws_sqs_queue.audit_events_dlq.arn
  }
}
