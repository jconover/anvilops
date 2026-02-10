# =============================================================================
# AnvilOps Puppet Enterprise Module
# =============================================================================
# Dedicated EC2 instance running Puppet Enterprise for Day 2+ compliance
# enforcement. Includes EBS data volume, Secrets Manager, CloudWatch agent,
# and optional Route 53 DNS record.
# =============================================================================

locals {
  user_data_vars = {
    hostname             = "puppet.${var.domain_name}"
    domain_name          = var.domain_name
    console_password_arn = aws_secretsmanager_secret.puppet_console_password.arn
    puppet_code_repo_url = var.puppet_code_repo_url
    autosign_domain      = var.domain_name
    pe_version           = var.puppet_enterprise_version
    device_name          = "/dev/xvdf"
    mount_point          = "/opt/puppetlabs"
    aws_region           = data.aws_region.current.name
    environment          = var.environment
  }
}

data "aws_region" "current" {}

data "aws_subnet" "puppet_subnet" {
  id = var.private_subnet_ids[0]
}

# -----------------------------------------------------------------------------
# AMI Lookup — Latest Amazon Linux 2023 (used when puppet_ami_id is empty)
# -----------------------------------------------------------------------------

data "aws_ami" "amazon_linux_2023" {
  count       = var.puppet_ami_id == "" ? 1 : 0
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }
}

locals {
  puppet_ami_id = var.puppet_ami_id != "" ? var.puppet_ami_id : data.aws_ami.amazon_linux_2023[0].id
}

# -----------------------------------------------------------------------------
# Secrets Manager — PE Console Admin Password
# -----------------------------------------------------------------------------

resource "random_password" "puppet_console_admin" {
  length           = 24
  special          = true
  override_special = "!@#$%^&*()-_=+[]{}:?"
}

resource "aws_secretsmanager_secret" "puppet_console_password" {
  name_prefix             = "${var.project_name}-${var.environment}-puppet-console-"
  description             = "Puppet Enterprise console admin password for ${var.environment}"
  recovery_window_in_days = 7

  tags = merge(var.tags, { Name = "${var.project_name}-${var.environment}-puppet-console-password" })
}

resource "aws_secretsmanager_secret_version" "puppet_console_password" {
  secret_id = aws_secretsmanager_secret.puppet_console_password.id
  secret_string = jsonencode({
    username    = "admin"
    password    = random_password.puppet_console_admin.result
    console_url = "https://puppet.${var.domain_name}"
  })
}

# -----------------------------------------------------------------------------
# EBS Volume — /opt/puppetlabs
# -----------------------------------------------------------------------------

resource "aws_ebs_volume" "puppet_data" {
  availability_zone = data.aws_subnet.puppet_subnet.availability_zone
  size              = var.puppet_data_volume_size
  type              = "gp3"
  encrypted         = true
  iops              = 3000
  throughput        = 125

  tags = merge(var.tags, {
    Name      = "puppet-${var.environment}-data"
    MountPath = "/opt/puppetlabs"
  })
}

resource "aws_volume_attachment" "puppet_data" {
  device_name  = "/dev/xvdf"
  volume_id    = aws_ebs_volume.puppet_data.id
  instance_id  = aws_instance.puppet_enterprise.id
  force_detach = false
}

# -----------------------------------------------------------------------------
# EC2 Instance — Puppet Enterprise Server
# -----------------------------------------------------------------------------

resource "aws_instance" "puppet_enterprise" {
  ami                    = local.puppet_ami_id
  instance_type          = var.puppet_instance_type
  subnet_id              = var.private_subnet_ids[0]
  vpc_security_group_ids = [var.puppet_security_group_id]
  iam_instance_profile   = var.puppet_instance_profile_name
  key_name               = var.ssh_key_name != "" ? var.ssh_key_name : null

  user_data                   = base64encode(templatefile("${path.module}/templates/user_data.sh.tftpl", local.user_data_vars))
  user_data_replace_on_change = false

  root_block_device {
    volume_size           = var.puppet_root_volume_size
    volume_type           = "gp3"
    encrypted             = true
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true

    tags = merge(var.tags, { Name = "puppet-${var.environment}-root" })
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
    instance_metadata_tags      = "enabled"
  }

  tags = merge(var.tags, {
    Name        = "puppet-${var.environment}"
    Component   = "PuppetEnterprise"
    Role        = "ConfigurationManagement"
  })

  lifecycle {
    ignore_changes = [ami, user_data]
  }

  depends_on = [aws_ebs_volume.puppet_data]
}

# -----------------------------------------------------------------------------
# Route 53 DNS Record (Private Zone)
# -----------------------------------------------------------------------------

resource "aws_route53_record" "puppet_private" {
  count = var.private_hosted_zone_id != "" ? 1 : 0

  zone_id = var.private_hosted_zone_id
  name    = "puppet.${var.domain_name}"
  type    = "A"
  ttl     = 300
  records = [aws_instance.puppet_enterprise.private_ip]
}

# -----------------------------------------------------------------------------
# CloudWatch Log Groups
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "puppet_server" {
  name              = "/aws/ec2/puppet/${var.environment}/puppet-server"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Name = "puppet-${var.environment}-server-logs" })
}

resource "aws_cloudwatch_log_group" "puppet_console" {
  name              = "/aws/ec2/puppet/${var.environment}/puppet-console"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Name = "puppet-${var.environment}-console-logs" })
}

resource "aws_cloudwatch_log_group" "puppetdb" {
  name              = "/aws/ec2/puppet/${var.environment}/puppetdb"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Name = "puppet-${var.environment}-puppetdb-logs" })
}

resource "aws_cloudwatch_log_group" "puppet_system" {
  name              = "/aws/ec2/puppet/${var.environment}/system"
  retention_in_days = var.log_retention_days
  tags              = merge(var.tags, { Name = "puppet-${var.environment}-system-logs" })
}

# -----------------------------------------------------------------------------
# SSM Parameter — CloudWatch Agent Configuration
# -----------------------------------------------------------------------------

resource "aws_ssm_parameter" "cloudwatch_agent_config" {
  name        = "/anvilops/${var.environment}/puppet/cloudwatch-agent-config"
  description = "CloudWatch Agent configuration for Puppet Enterprise server"
  type        = "String"
  value = jsonencode({
    agent = {
      metrics_collection_interval = 60
      run_as_user                 = "cwagent"
    }
    logs = {
      logs_collected = {
        files = {
          collect_list = [
            {
              file_path        = "/var/log/puppetlabs/puppetserver/puppetserver.log"
              log_group_name   = aws_cloudwatch_log_group.puppet_server.name
              log_stream_name  = "{instance_id}/puppetserver.log"
              timezone         = "UTC"
            },
            {
              file_path        = "/var/log/puppetlabs/console-services/console-services.log"
              log_group_name   = aws_cloudwatch_log_group.puppet_console.name
              log_stream_name  = "{instance_id}/console-services.log"
              timezone         = "UTC"
            },
            {
              file_path        = "/var/log/puppetlabs/puppetdb/puppetdb.log"
              log_group_name   = aws_cloudwatch_log_group.puppetdb.name
              log_stream_name  = "{instance_id}/puppetdb.log"
              timezone         = "UTC"
            },
            {
              file_path       = "/var/log/messages"
              log_group_name  = aws_cloudwatch_log_group.puppet_system.name
              log_stream_name = "{instance_id}/messages"
              timezone        = "UTC"
            }
          ]
        }
      }
    }
    metrics = {
      namespace = "AnvilOps/PuppetEnterprise"
      metrics_collected = {
        cpu = {
          measurement                 = ["cpu_usage_idle", "cpu_usage_iowait"]
          metrics_collection_interval = 60
          totalcpu                    = true
        }
        disk = {
          measurement                 = ["used_percent"]
          metrics_collection_interval = 60
          resources                   = ["*"]
        }
        mem = {
          measurement                 = ["mem_used_percent"]
          metrics_collection_interval = 60
        }
      }
    }
  })

  tags = merge(var.tags, { Name = "puppet-${var.environment}-cloudwatch-config" })
}
