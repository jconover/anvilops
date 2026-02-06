locals {
  default_user_data = <<-EOF
    <powershell>
    # Set hostname
    Rename-Computer -NewName "${var.server_name}" -Force

    # Enable WinRM for Ansible/AWX connectivity
    Set-Item -Path WSMan:\localhost\Service\AllowUnencrypted -Value $false
    Set-Item -Path WSMan:\localhost\Service\Auth\Basic -Value $true
    Set-Item -Path WSMan:\localhost\Service\Auth\CredSSP -Value $true

    # Configure WinRM HTTPS listener
    $cert = New-SelfSignedCertificate -DnsName $env:COMPUTERNAME -CertStoreLocation Cert:\LocalMachine\My
    New-Item -Path WSMan:\localhost\Listener -Transport HTTPS -Address * -CertificateThumbPrint $cert.Thumbprint -Force -ErrorAction SilentlyContinue

    # Open WinRM HTTPS in Windows Firewall
    New-NetFirewallRule -Name "WinRM-HTTPS" -DisplayName "WinRM over HTTPS" -Enabled True -Direction Inbound -Protocol TCP -LocalPort 5986 -Action Allow -ErrorAction SilentlyContinue

    # Ensure SSM agent is running
    $ssmService = Get-Service -Name AmazonSSMAgent -ErrorAction SilentlyContinue
    if ($ssmService) {
        Set-Service -Name AmazonSSMAgent -StartupType Automatic
        Start-Service -Name AmazonSSMAgent
    }

    # Enable PowerShell remoting
    Enable-PSRemoting -Force -SkipNetworkProfileCheck

    # Signal that user data has completed
    $logPath = "C:\AnvilOps\init.log"
    New-Item -Path "C:\AnvilOps" -ItemType Directory -Force
    "AnvilOps user data completed at $(Get-Date)" | Out-File -FilePath $logPath

    # Restart to apply hostname change
    Restart-Computer -Force
    </powershell>
  EOF

  effective_user_data = var.user_data != "" ? var.user_data : local.default_user_data

  required_tags = {
    Name        = var.server_name
    Environment = var.environment
    ManagedBy   = "AnvilOps"
    OSFamily    = "Windows"
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

  # Windows requires get_password_data to retrieve admin password
  get_password_data = var.key_name != "" ? true : false

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
