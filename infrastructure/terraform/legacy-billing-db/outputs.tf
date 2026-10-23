output "db_instance_identifier" {
  value = aws_db_instance.this.identifier
}

output "address" {
  value = aws_db_instance.this.address
}

output "port" {
  value = aws_db_instance.this.port
}

output "db_name" {
  value = aws_db_instance.this.db_name
}

output "master_username" {
  value = aws_db_instance.this.username
}

output "master_user_secret_arn" {
  value = aws_db_instance.this.master_user_secret[0].secret_arn
}

output "client_security_group_id" {
  value = aws_security_group.client.id
}

output "db_security_group_id" {
  value = aws_security_group.db.id
}

output "kms_key_arn" {
  value = aws_kms_key.this.arn
}

output "parameter_group_name" {
  value = aws_db_parameter_group.this.name
}
