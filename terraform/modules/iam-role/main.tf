locals {
  merged_tags = merge(
    {
      Name        = var.name
      Environment = var.environment
      ManagedBy   = "AnvilOps"
    },
    var.tags
  )
}

data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "this" {
  name               = var.name
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json
  tags               = local.merged_tags
}

resource "aws_iam_instance_profile" "this" {
  name = var.name
  role = aws_iam_role.this.name
  tags = local.merged_tags
}

# Attach SSM managed policy (required for all AnvilOps servers)
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Attach CloudWatch agent policy for monitoring
resource "aws_iam_role_policy_attachment" "cloudwatch" {
  role       = aws_iam_role.this.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# Attach any custom policies
resource "aws_iam_role_policy_attachment" "custom" {
  for_each = toset(var.custom_policy_arns)

  role       = aws_iam_role.this.name
  policy_arn = each.value
}
