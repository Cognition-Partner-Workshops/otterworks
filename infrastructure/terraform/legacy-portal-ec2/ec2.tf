# The "before" state: one plain EC2 host running the monolith and its own
# PostgreSQL. No autoscaling group, no managed database, no alarms, and no SSH
# key pair; access is SSM only.

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb"
  description = "Internet-facing ALB for the legacy-portal EC2 run"
  vpc_id      = data.aws_vpc.this.id
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from anywhere"
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_all" {
  security_group_id = aws_security_group.alb.id
  description       = "All egress"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "instance" {
  name        = "${local.name}-instance"
  description = "Monolith host; only the run ALB may reach the app port"
  vpc_id      = data.aws_vpc.this.id
}

resource "aws_vpc_security_group_ingress_rule" "instance_app_from_alb" {
  security_group_id            = aws_security_group.instance.id
  description                  = "App port from the ALB only"
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = var.app_port
  to_port                      = var.app_port
  ip_protocol                  = "tcp"
}

# Egress stays open: the host needs yum/dnf, SSM, CloudWatch and S3.
resource "aws_vpc_security_group_egress_rule" "instance_all" {
  security_group_id = aws_security_group.instance.id
  description       = "All egress"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_instance" "this" {
  ami                    = data.aws_ssm_parameter.al2023_ami.value
  instance_type          = var.instance_type
  subnet_id              = data.aws_subnets.public.ids[0]
  iam_instance_profile   = aws_iam_instance_profile.this.name
  vpc_security_group_ids = [aws_security_group.instance.id]

  user_data = templatefile("${path.module}/files/user_data.sh", {
    region          = var.region
    artifact_bucket = aws_s3_bucket.artifacts.id
    jar_key         = aws_s3_object.jar.key
    jar_md5         = filemd5("${path.module}/${var.jar_path}")
    app_port        = var.app_port
    log_group_name  = aws_cloudwatch_log_group.app.name
  })

  # A fresh host runs the bootstrap again; an in-place user_data update would
  # only change metadata without re-running cloud-init.
  user_data_replace_on_change = true

  metadata_options {
    http_tokens = "required"
  }

  root_block_device {
    volume_size = 16
    volume_type = "gp3"
  }

  tags = { Name = local.name }
}
