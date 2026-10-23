data "aws_iam_policy_document" "instance_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.${data.aws_partition.current.dns_suffix}"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.run_token}-instance"
  description        = "Instance role for ${var.service_name} rehost run ${var.run_token}"
  assume_role_policy = data.aws_iam_policy_document.instance_assume.json
  tags               = merge(local.tags, { Name = "${var.run_token}-instance" })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/CloudWatchAgentServerPolicy"
}

data "aws_iam_policy_document" "read_artifacts" {
  statement {
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }

  statement {
    effect    = "Allow"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.artifacts.arn]
  }
}

resource "aws_iam_role_policy" "read_artifacts" {
  name   = "${var.run_token}-read-artifacts"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.read_artifacts.json
}

resource "aws_iam_instance_profile" "this" {
  name = "${var.run_token}-instance"
  role = aws_iam_role.instance.name
  tags = local.tags
}
