resource "aws_instance" "this" {
  ami                         = local.selected_ami
  instance_type               = var.instance_type
  subnet_id                   = var.subnet_ids[0]
  iam_instance_profile        = aws_iam_instance_profile.this.name
  vpc_security_group_ids      = [aws_security_group.instance.id]
  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/files/user_data.sh.tftpl", {
    region            = data.aws_region.current.name
    service_name      = var.service_name
    artifact_bucket   = aws_s3_bucket.artifacts.id
    artifact_name     = local.artifact_name
    artifact_md5      = filemd5(var.artifact_path)
    artifact_path     = "/opt/${var.service_name}/${local.artifact_name}"
    app_port          = var.app_port
    app_log_path      = local.app_log_path
    log_group_name    = aws_cloudwatch_log_group.app.name
    packages          = join(" ", var.packages)
    environment_lines = local.environment_lines
    bootstrap_script  = var.bootstrap_script
    start_command     = var.start_command
  })

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
  }

  tags = merge(local.tags, { Name = "${var.run_token}-${var.service_name}" })
}
