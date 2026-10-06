output "base_url" {
  description = "HTTP URL of the internet-facing ALB. lp-ec2-replay uses it as the target base URL."
  value       = "http://${aws_lb.this.dns_name}"
}

output "instance_id" {
  value = aws_instance.this.id
}

output "instance_type" {
  value = aws_instance.this.instance_type
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "app_log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "target_group_arn" {
  description = "Used by lp-ec2-up to wait for the health check."
  value       = aws_lb_target_group.app.arn
}

output "expires" {
  value = var.expires
}
