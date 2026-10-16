resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = local.alarm_name
  alarm_description   = "Messages in ${local.dlq_name}: notification-service in ${var.tenant_namespace} failed to process them three times"
  namespace           = "AWS/SQS"
  metric_name         = "ApproximateNumberOfMessagesVisible"
  dimensions          = { QueueName = aws_sqs_queue.notifications_dlq.name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"

  lifecycle {
    ignore_changes = [actions_enabled]
  }
}

resource "aws_cloudwatch_dashboard" "cloud_worker" {
  dashboard_name = local.dashboard_name

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title   = "${local.queue_name} visible"
          region  = local.region
          view    = "timeSeries"
          stat    = "Sum"
          period  = 60
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", local.queue_name]]
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title   = "${local.dlq_name} visible"
          region  = local.region
          view    = "timeSeries"
          stat    = "Sum"
          period  = 60
          metrics = [["AWS/SQS", "ApproximateNumberOfMessagesVisible", "QueueName", local.dlq_name]]
          annotations = {
            horizontal = [{ label = "alarm", value = 1 }]
          }
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          title   = "${local.queue_name} age of oldest message"
          region  = local.region
          view    = "timeSeries"
          stat    = "Maximum"
          period  = 60
          metrics = [["AWS/SQS", "ApproximateAgeOfOldestMessage", "QueueName", local.queue_name]]
        }
      },
      {
        type   = "alarm"
        x      = 0
        y      = 6
        width  = 24
        height = 3
        properties = {
          title  = "Page"
          alarms = [aws_cloudwatch_metric_alarm.dlq_depth.arn]
        }
      },
    ]
  })
}
