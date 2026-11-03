output "instance_id" {
  description = "Pass to `make tp-demo-reset ORACLE=<id>`."
  value       = aws_instance.this.id
}

output "host" {
  value = aws_eip.this.public_ip
}

output "dsn" {
  description = "host:port/service for OW_TP_ORACLE_RO_DSN / OW_BILLING_RO_DSN."
  value       = "${aws_eip.this.public_ip}:1521/FREEPDB1"
}

output "ro_user" {
  value = var.ro_user
}
