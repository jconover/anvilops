# frozen_string_literal: true

# Custom Facter fact: anvilops_metadata
#
# Reports AnvilOps server metadata for Puppet Enterprise dashboards and
# PuppetDB queries. This fact reads a metadata JSON file that is written
# by the Ansible post-provisioning playbook during Day 1 setup.
#
# The metadata file contains:
#   - server_name: The AnvilOps server name (e.g., PROD-WEB-a3f8)
#   - environment: The deployment environment (dev, staging, production)
#   - role: The server role (web_server, db_server, app_server, etc.)
#   - template: The template used to provision (e.g., standard_web_server)
#   - request_id: The AnvilOps request UUID
#   - provisioned_at: ISO 8601 timestamp of provisioning
#   - provisioned_by: User who initiated the build
#   - aws_account_id: The AWS account ID
#   - aws_region: The AWS region
#   - vpc_id: The VPC ID
#
# File locations:
#   - Linux: /etc/anvilops/metadata.json
#   - Windows: C:/ProgramData/AnvilOps/metadata.json
#
# If the metadata file does not exist (e.g., during initial provisioning
# before Ansible has run), the fact returns a minimal hash with only
# the managed_by and puppet_managed keys.

Facter.add(:anvilops_metadata) do
  confine kernel: ['Linux', 'windows']

  setcode do
    metadata = {}

    # Determine metadata file location based on OS
    os_family = Facter.value(:os)['family'] rescue nil

    metadata_file = case os_family
                    when 'windows'
                      'C:/ProgramData/AnvilOps/metadata.json'
                    else
                      '/etc/anvilops/metadata.json'
                    end

    # Read and parse the metadata file if it exists
    begin
      if File.exist?(metadata_file)
        require 'json'
        raw_content = File.read(metadata_file)
        parsed = JSON.parse(raw_content)

        # Only accept known keys to prevent metadata injection
        allowed_keys = %w[
          server_name
          environment
          role
          template
          request_id
          provisioned_at
          provisioned_by
          aws_account_id
          aws_region
          vpc_id
          subnet_id
          instance_type
          ami_id
          cost_center
          team
          project
          decommission_date
        ]

        parsed.each do |key, value|
          metadata[key] = value.to_s if allowed_keys.include?(key)
        end
      end
    rescue JSON::ParserError => e
      metadata['metadata_parse_error'] = e.message[0..200]
    rescue StandardError => e
      metadata['metadata_read_error'] = e.message[0..200]
    end

    # Read compliance configuration if available
    begin
      compliance_file = case os_family
                        when 'windows'
                          'C:/ProgramData/AnvilOps/compliance_config.json'
                        else
                          '/etc/anvilops/compliance_config.json'
                        end

      if File.exist?(compliance_file)
        require 'json'
        compliance_config = JSON.parse(File.read(compliance_file))
        metadata['cis_level'] = compliance_config['cis_level'].to_s if compliance_config['cis_level']
        metadata['stig_enabled'] = compliance_config['stig_enabled'].to_s if compliance_config.key?('stig_enabled')
        metadata['compliance_report_only'] = compliance_config['report_only'].to_s if compliance_config.key?('report_only')
      end
    rescue StandardError
      # Silently ignore compliance config errors
    end

    # Always set these keys to identify AnvilOps-managed nodes
    metadata['managed_by'] = 'AnvilOps'
    metadata['puppet_managed'] = true
    metadata['fact_version'] = '1.0.0'

    metadata
  end
end
