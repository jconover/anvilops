'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  Globe,
  HardDrive,
  Monitor,
  Server,
  ShieldAlert,
  User,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { ApprovalActions } from '@/components/approvals/approval-actions';
import type { ServerResponse } from '@/lib/api/types';

interface ApprovalCardProps {
  server: ServerResponse;
}

/** Human-readable OS labels. */
const OS_LABELS: Record<string, string> = {
  windows_2022: 'Windows Server 2022',
  windows_2019: 'Windows Server 2019',
  amazon_linux_2023: 'Amazon Linux 2023',
  ubuntu_2204: 'Ubuntu 22.04 LTS',
  rhel_9: 'RHEL 9',
};

/** Human-readable instance size labels. */
const SIZE_LABELS: Record<string, string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large',
  xl: 'Extra Large',
};

/**
 * Returns the list of reasons this server requires approval.
 * Business rules: production environment and/or xl instance size.
 */
function getApprovalReasons(
  server: ServerResponse,
): { label: string; severity: 'production' | 'xl' }[] {
  const reasons: { label: string; severity: 'production' | 'xl' }[] = [];
  if (server.environment === 'production') {
    reasons.push({
      label: 'Production environment request',
      severity: 'production',
    });
  }
  if (server.instance_size === 'xl') {
    reasons.push({
      label: 'Extra-large instance size',
      severity: 'xl',
    });
  }
  return reasons;
}

/** Formats an ISO timestamp into a relative human-readable string. */
function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(iso).toLocaleDateString();
}

/** Badge variant for the environment. */
function envBadgeVariant(env: string) {
  switch (env) {
    case 'production':
      return 'destructive' as const;
    case 'staging':
      return 'warning' as const;
    default:
      return 'secondary' as const;
  }
}

export function ApprovalCard({ server }: ApprovalCardProps) {
  const [expanded, setExpanded] = useState(false);
  const reasons = getApprovalReasons(server);

  return (
    <Card className="transition-shadow hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-4">
          {/* Left: server name + badges */}
          <div className="flex flex-col gap-2 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Server className="h-5 w-5 text-muted-foreground shrink-0" />
              <span className="font-semibold text-base truncate">
                {server.server_name}
              </span>
              <Badge variant={envBadgeVariant(server.environment)}>
                {server.environment}
              </Badge>
              <Badge variant="info">{server.status}</Badge>
            </div>

            {/* Requester placeholder */}
            <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <User className="h-3.5 w-3.5" />
              <span>Requested by user</span>
              <span className="mx-1">--</span>
              <Clock className="h-3.5 w-3.5" />
              <span>{formatRelativeTime(server.created_at)}</span>
            </div>
          </div>

          {/* Right: actions */}
          <div className="shrink-0">
            <ApprovalActions
              serverId={server.id}
              serverName={server.server_name}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="pb-3">
        {/* Approval reason banners */}
        <div className="flex flex-col gap-2 mb-4">
          {reasons.map((reason) => (
            <div
              key={reason.label}
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium ${
                reason.severity === 'production'
                  ? 'bg-red-50 text-red-800 border border-red-200 dark:bg-red-950/30 dark:text-red-300 dark:border-red-800'
                  : 'bg-yellow-50 text-yellow-800 border border-yellow-200 dark:bg-yellow-950/30 dark:text-yellow-300 dark:border-yellow-800'
              }`}
            >
              {reason.severity === 'production' ? (
                <ShieldAlert className="h-4 w-4 shrink-0" />
              ) : (
                <AlertTriangle className="h-4 w-4 shrink-0" />
              )}
              {reason.label}
            </div>
          ))}
        </div>

        {/* Summary row */}
        <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <div className="flex items-center gap-1.5">
            <Monitor className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">OS:</span>
            <span className="font-medium">
              {OS_LABELS[server.os_type] ?? server.os_type}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <HardDrive className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Size:</span>
            <span className="font-medium">
              {SIZE_LABELS[server.instance_size] ?? server.instance_size}
            </span>
          </div>
          <div className="flex items-center gap-1.5">
            <Globe className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Region:</span>
            <span className="font-medium">{server.region}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <span className="text-muted-foreground">Created:</span>
            <span className="font-medium">
              {new Date(server.created_at).toLocaleDateString()}
            </span>
          </div>
        </div>
      </CardContent>

      {/* Expandable details */}
      <CardFooter className="flex flex-col items-stretch gap-0 pt-0">
        <div className="flex items-center justify-between">
          <Link
            href={`/servers/${server.id}`}
            className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
          >
            View Details
            <ExternalLink className="h-3.5 w-3.5" />
          </Link>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="text-muted-foreground"
          >
            {expanded ? (
              <>
                Hide Details
                <ChevronUp className="ml-1 h-4 w-4" />
              </>
            ) : (
              <>
                Show Details
                <ChevronDown className="ml-1 h-4 w-4" />
              </>
            )}
          </Button>
        </div>

        {expanded && (
          <div className="mt-3">
            <Separator className="mb-3" />
            <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <DetailRow label="Server ID" value={server.id} />
              <DetailRow label="Server Name" value={server.server_name} />
              <DetailRow label="Environment" value={server.environment} />
              <DetailRow
                label="OS Type"
                value={OS_LABELS[server.os_type] ?? server.os_type}
              />
              <DetailRow
                label="Instance Size"
                value={SIZE_LABELS[server.instance_size] ?? server.instance_size}
              />
              <DetailRow label="Region" value={server.region} />
              <DetailRow label="Status" value={server.status} />
              <DetailRow
                label="Status Message"
                value={server.status_message ?? 'None'}
              />
              <DetailRow
                label="AWS Instance ID"
                value={server.aws_instance_id ?? 'Not provisioned'}
              />
              <DetailRow
                label="Private IP"
                value={server.private_ip ?? 'Not assigned'}
              />
              <DetailRow
                label="Public IP"
                value={server.public_ip ?? 'Not assigned'}
              />
              <DetailRow
                label="DNS Name"
                value={server.dns_name ?? 'Not assigned'}
              />
              <DetailRow
                label="Created"
                value={new Date(server.created_at).toLocaleString()}
              />
              <DetailRow
                label="Updated"
                value={new Date(server.updated_at).toLocaleString()}
              />
            </div>
          </div>
        )}
      </CardFooter>
    </Card>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-muted-foreground whitespace-nowrap">{label}:</span>
      <span className="font-medium break-all">{value}</span>
    </div>
  );
}
