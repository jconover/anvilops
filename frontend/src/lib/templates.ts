import type { VolumeType } from '@/lib/api/types';

export interface ServerTemplate {
  id: string;
  name: string;
  description: string;
  icon: string;
  defaults: {
    os_type: string;
    instance_size: string;
    security_profile: string;
    puppet_role: string;
    domain_join: boolean;
    software_packages: string[];
    additional_storage: {
      mount_point?: string;
      drive_letter?: string;
      size_gb: number;
      volume_type: VolumeType;
    }[];
  };
}

export const SERVER_TEMPLATES: ServerTemplate[] = [
  {
    id: 'standard-web',
    name: 'Standard Web Server',
    description:
      'Linux-based web server with Nginx for internal applications. Pre-configured with standard hardening and monitoring agents.',
    icon: 'Globe',
    defaults: {
      os_type: 'amazon_linux_2023',
      instance_size: 'small',
      security_profile: 'web_facing',
      puppet_role: 'web_server',
      domain_join: false,
      software_packages: ['nginx'],
      additional_storage: [],
    },
  },
  {
    id: 'public-web',
    name: 'Public Web Server',
    description:
      'Internet-facing web server with Nginx, TLS via Certbot, and enhanced security hardening for public traffic.',
    icon: 'Earth',
    defaults: {
      os_type: 'amazon_linux_2023',
      instance_size: 'medium',
      security_profile: 'web_facing',
      puppet_role: 'web_server',
      domain_join: false,
      software_packages: ['nginx', 'certbot'],
      additional_storage: [],
    },
  },
  {
    id: 'sql-server',
    name: 'SQL Server',
    description:
      'Windows Server 2022 with dedicated data, log, and backup drives optimized for SQL Server workloads.',
    icon: 'Database',
    defaults: {
      os_type: 'windows_2022',
      instance_size: 'large',
      security_profile: 'database',
      puppet_role: 'db_server',
      domain_join: true,
      software_packages: [],
      additional_storage: [
        { drive_letter: 'D', size_gb: 100, volume_type: 'io2' },
        { drive_letter: 'E', size_gb: 50, volume_type: 'io2' },
        { drive_letter: 'F', size_gb: 100, volume_type: 'gp3' },
      ],
    },
  },
  {
    id: 'app-server-dotnet',
    name: 'App Server (.NET)',
    description:
      'Windows Server 2022 with the .NET SDK for hosting ASP.NET Core and .NET Framework applications.',
    icon: 'Box',
    defaults: {
      os_type: 'windows_2022',
      instance_size: 'medium',
      security_profile: 'internal_only',
      puppet_role: 'app_server',
      domain_join: true,
      software_packages: ['dotnet-sdk'],
      additional_storage: [],
    },
  },
  {
    id: 'app-server-java',
    name: 'App Server (Java)',
    description:
      'Linux server with Amazon Corretto 17 for running Java-based applications and microservices.',
    icon: 'Coffee',
    defaults: {
      os_type: 'amazon_linux_2023',
      instance_size: 'medium',
      security_profile: 'internal_only',
      puppet_role: 'app_server',
      domain_join: false,
      software_packages: ['java-17-amazon-corretto'],
      additional_storage: [],
    },
  },
  {
    id: 'dev-workstation',
    name: 'Dev Workstation',
    description:
      'Windows Server 2022 development environment with Git, VS Code, and Docker pre-installed.',
    icon: 'Monitor',
    defaults: {
      os_type: 'windows_2022',
      instance_size: 'medium',
      security_profile: 'internal_only',
      puppet_role: 'dev_workstation',
      domain_join: true,
      software_packages: ['git', 'vscode', 'docker'],
      additional_storage: [],
    },
  },
];
