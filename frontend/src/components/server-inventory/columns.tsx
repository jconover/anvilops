'use client';

import { Badge } from '@/components/ui/badge';
import type { ServerResponse, ServerStatus, OsType } from '@/lib/api/types';
import { formatDistanceToNow } from 'date-fns';

// ---------------------------------------------------------------------------
// Column definition type
// ---------------------------------------------------------------------------

export interface ColumnDef {
  id: string;
  header: string;
  accessorFn: (row: ServerResponse) => string | number | null;
  sortable: boolean;
  visibleByDefault: boolean;
  cell: (row: ServerResponse) => React.ReactNode;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const OS_FRIENDLY_NAMES: Record<string, string> = {
  windows_2022: 'Windows Server 2022',
  windows_2019: 'Windows Server 2019',
  amazon_linux_2023: 'Amazon Linux 2023',
  ubuntu_2204: 'Ubuntu 22.04 LTS',
  rhel_9: 'RHEL 9',
};

export function getOsFriendlyName(osType: string): string {
  return OS_FRIENDLY_NAMES[osType] ?? osType;
}

const INSTANCE_SIZE_LABELS: Record<string, string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large',
  xl: 'XL',
};

export function getInstanceSizeLabel(size: string): string {
  return INSTANCE_SIZE_LABELS[size] ?? size;
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'destructive' | 'outline' | 'success' | 'warning' | 'info'> = {
  pending: 'warning',
  approved: 'info',
  provisioning: 'info',
  configuring: 'info',
  validating: 'info',
  ready: 'success',
  failed: 'destructive',
  cancelled: 'secondary',
  decommissioning: 'warning',
  decommissioned: 'secondary',
};

const STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  approved: 'Approved',
  provisioning: 'Provisioning',
  configuring: 'Configuring',
  validating: 'Validating',
  ready: 'Ready',
  failed: 'Failed',
  cancelled: 'Cancelled',
  decommissioning: 'Decommissioning',
  decommissioned: 'Decommissioned',
};

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_VARIANT[status] ?? 'outline';
  const label = STATUS_LABELS[status] ?? status;
  return <Badge variant={variant}>{label}</Badge>;
}

// ---------------------------------------------------------------------------
// Environment badge
// ---------------------------------------------------------------------------

const ENV_VARIANT: Record<string, 'info' | 'warning' | 'destructive'> = {
  dev: 'info',
  staging: 'warning',
  production: 'destructive',
};

const ENV_LABELS: Record<string, string> = {
  dev: 'Dev',
  staging: 'Staging',
  production: 'Production',
};

export function EnvironmentBadge({ environment }: { environment: string }) {
  const variant = ENV_VARIANT[environment] ?? 'outline';
  const label = ENV_LABELS[environment] ?? environment;
  return <Badge variant={variant}>{label}</Badge>;
}

// ---------------------------------------------------------------------------
// Date formatter
// ---------------------------------------------------------------------------

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return dateStr;
  }
}

// ---------------------------------------------------------------------------
// Column definitions
// ---------------------------------------------------------------------------

export const columns: ColumnDef[] = [
  {
    id: 'server_name',
    header: 'Server Name',
    accessorFn: (row) => row.server_name,
    sortable: true,
    visibleByDefault: true,
    cell: (row) => (
      <span className="font-medium font-mono text-sm">{row.server_name}</span>
    ),
  },
  {
    id: 'environment',
    header: 'Environment',
    accessorFn: (row) => row.environment,
    sortable: true,
    visibleByDefault: true,
    cell: (row) => <EnvironmentBadge environment={row.environment} />,
  },
  {
    id: 'os_type',
    header: 'OS',
    accessorFn: (row) => row.os_type,
    sortable: true,
    visibleByDefault: true,
    cell: (row) => (
      <span className="text-sm">{getOsFriendlyName(row.os_type)}</span>
    ),
  },
  {
    id: 'instance_size',
    header: 'Instance Size',
    accessorFn: (row) => row.instance_size,
    sortable: true,
    visibleByDefault: true,
    cell: (row) => (
      <span className="text-sm">{getInstanceSizeLabel(row.instance_size)}</span>
    ),
  },
  {
    id: 'status',
    header: 'Status',
    accessorFn: (row) => row.status,
    sortable: true,
    visibleByDefault: true,
    cell: (row) => <StatusBadge status={row.status} />,
  },
  {
    id: 'region',
    header: 'Region',
    accessorFn: (row) => row.region,
    sortable: true,
    visibleByDefault: false,
    cell: (row) => <span className="text-sm">{row.region}</span>,
  },
  {
    id: 'private_ip',
    header: 'Private IP',
    accessorFn: (row) => row.private_ip,
    sortable: false,
    visibleByDefault: true,
    cell: (row) => (
      <span className="font-mono text-sm text-muted-foreground">
        {row.private_ip ?? '--'}
      </span>
    ),
  },
  {
    id: 'public_ip',
    header: 'Public IP',
    accessorFn: (row) => row.public_ip,
    sortable: false,
    visibleByDefault: false,
    cell: (row) => (
      <span className="font-mono text-sm text-muted-foreground">
        {row.public_ip ?? '--'}
      </span>
    ),
  },
  {
    id: 'dns_name',
    header: 'DNS Name',
    accessorFn: (row) => row.dns_name,
    sortable: false,
    visibleByDefault: false,
    cell: (row) => (
      <span className="font-mono text-sm text-muted-foreground">
        {row.dns_name ?? '--'}
      </span>
    ),
  },
  {
    id: 'aws_instance_id',
    header: 'Instance ID',
    accessorFn: (row) => row.aws_instance_id,
    sortable: false,
    visibleByDefault: false,
    cell: (row) => (
      <span className="font-mono text-xs text-muted-foreground">
        {row.aws_instance_id ?? '--'}
      </span>
    ),
  },
  {
    id: 'created_at',
    header: 'Created',
    accessorFn: (row) => row.created_at,
    sortable: true,
    visibleByDefault: true,
    cell: (row) => (
      <span className="text-sm text-muted-foreground">
        {formatDate(row.created_at)}
      </span>
    ),
  },
];

/** Returns the IDs of columns that should be visible by default. */
export function getDefaultVisibleColumns(): string[] {
  return columns.filter((col) => col.visibleByDefault).map((col) => col.id);
}
