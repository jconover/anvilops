locals {
  default_user_data = <<-EOF
    #!/bin/bash
    set -euo pipefail

    # Set hostname
    hostnamectl set-hostname "${var.server_name}"

    # Update the system
    if command -v yum &>/dev/null; then
      yum update -y
    elif command -v apt-get &>/dev/null; then
      apt-get update -y && apt-get upgrade -y
    fi

    # Ensure SSM agent is installed and running
    if command -v yum &>/dev/null; then
      yum install -y amazon-ssm-agent
    elif command -v apt-get &>/dev/null; then
      snap install amazon-ssm-agent --classic 2>/dev/null || true
    fi
    systemctl enable amazon-ssm-agent
    systemctl start amazon-ssm-agent

    # Signal that user data has completed
    echo "AnvilOps user data completed at $(date)" > /var/log/anvilops-init.log
  EOF

  effective_user_data = var.user_data != "" ? var.user_data : local.default_user_data

  required_tags = {
    Name        = var.server_name
    Environment = var.environment
    ManagedBy   = "AnvilOps"
    OSFamily    = "Linux"
  }

  merged_tags = merge(local.required_tags, var.tags)
}

resource "aws_instance" "this" {
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = var.vpc_security_group_ids
  iam_instance_profile   = var.iam_instance_profile
  key_name               = var.key_name != "" ? var.key_name : null

  user_data                   = base64encode(local.effective_user_data)
  user_data_replace_on_change = false

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    encrypted             = true
    delete_on_termination = true

    tags = merge(local.merged_tags, {
      Name = "${var.server_name}-root"
    })
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 enforced
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "enabled"
  }

  tags = local.merged_tags

  lifecycle {
    ignore_changes = [
      ami, # Prevent replacement on AMI updates
    ]
  }
}
