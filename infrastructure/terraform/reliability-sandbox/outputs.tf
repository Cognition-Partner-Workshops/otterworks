output "run_token" {
  value = var.run_token
}

output "expires" {
  value = var.expires
}

output "region" {
  value = var.aws_region
}

output "events_topic_arn" {
  value = module.messaging.events_topic_arn
}

output "analytics_queue_url" {
  value = module.messaging.analytics_queue_url
}

output "analytics_queue_arn" {
  value = module.messaging.analytics_queue_arn
}

output "analytics_dlq_url" {
  value = module.messaging.analytics_dlq_url
}

output "analytics_dlq_arn" {
  value = module.messaging.analytics_dlq_arn
}

output "search_indexing_queue_url" {
  value = module.messaging.search_indexing_queue_url
}

output "search_indexing_dlq_url" {
  value = module.messaging.search_indexing_dlq_url
}

output "notification_queue_url" {
  value = module.messaging.notification_queue_url
}

output "dlq_alarm_names" {
  value = module.messaging.dlq_alarm_names
}

output "backlog_alarm_names" {
  value = module.messaging.backlog_alarm_names
}

output "ledger_table_name" {
  value = aws_dynamodb_table.ledger.name
}

output "max_receive_count" {
  value = var.max_receive_count
}
