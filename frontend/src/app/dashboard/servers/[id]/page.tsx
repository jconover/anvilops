'use client';

import { useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  useServer,
  useServerBuildSteps,
  usePuppetStatus,
} from '@/lib/api/hooks';
import { useAuth } from '@/lib/auth/context';
import {
  StatusBadge,
  EnvironmentBadge,
  getOsFriendlyName,
  getInstanceSizeLabel,
} from '@/components/server-inventory/columns';
import { DecommissionDialog } from '@/components/server-inventory/decommission-dialog';
import { DecommissionTracker } from '@/components/server-inventory/decommission-tracker';
import type { BuildStep, BuildStepStatus } from '@/lib/api/types';
import { CMDBStatusCard } from '@/components/cmdb/cmdb-status-card';
import {
  ArrowLeft,
  Trash2,
  GitBranch,
  Server,
  Globe,
  Shield,
  Clock,
  CheckCircle2,
  Circle,
  XCircle,
  Loader2,
  AlertTriangle,
  Ban,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Build steps timeline
// ---------------------------------------------------------------------------

const STEP_STATUS_CONFIG: Record<
  BuildStepStatus,
  { icon: React.ReactNode; color: string }
> = {
  completed: {
    icon: <CheckCircle2 className="h-5 w-5" />,
    color: 'text-green-600 dark:text-green-400',
  },
  in_progress: {
    icon: <Loader2 className="h-5 w-5 animate-spin" />,
    color: 'text-blue-600 dark:text-blue-400',
  },
  pending: {
    icon: <Circle className="h-5 w-5" />,
    color: 'text-muted-foreground',
  },
  failed: {
    icon: <XCircle className="h-5 w-5" />,
    color: 'text-red-600 dark:text-red-400',
  },
};

function BuildTimeline({ steps }: { steps: BuildStep[] }) {
  const sorted = [...steps].sort((a, b) => a.step_order - b.step_order);

  return (
    <div className="space-y-1">
      {sorted.map((step, index) => {
        const config = STEP_STATUS_CONFIG[step.status] ?? STEP_STATUS_CONFIG.pending;
        const isLast = index === sorted.length - 1;

        return (
          <div key={step.id} className="flex gap-3">
            {/* Timeline line + icon */}
            <div className="flex flex-col items-center">
              <div className={config.color}>{config.icon}</div>
              {!isLast && (
                <div className="w-px flex-1 bg-border min-h-[24px]" />
              )}
            </div>
            {/* Step content */}
            <div className="pb-4">
              <p className="text-sm font-medium leading-tight">
                {step.step_name}
              </p>
              {step.started_at && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {step.completed_at
                    ? `Completed ${new Date(step.completed_at).toLocaleString()}`
                    : `Started ${new Date(step.started_at).toLocaleString()}`}
                </p>
              )}
              {step.error_message && (
                <p className="text-xs text-destructive mt-1">
                  {step.error_message}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Info row helper
// ---------------------------------------------------------------------------

function InfoRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col space-y-1">
      <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        {label}
      </span>
      <span
        className={`text-sm ${
          mono ? 'font-mono' : ''
        } ${!value ? 'text-muted-foreground' : ''}`}
      >
        {value ?? '--'}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-6 w-16" />
        <Skeleton className="h-6 w-20" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <Skeleton className="h-5 w-32" />
          </CardHeader>
          <CardContent className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ServerDetailPage() {
  const params = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const [showDecommissionDialog, setShowDecommissionDialog] = useState(false);

  const serverId = params.id;
  const { data: server, isLoading: serverLoading } = useServer(serverId);
  const { data: buildSteps } = useServerBuildSteps(serverId);
  const { data: puppetStatus } = usePuppetStatus(serverId);

  const canDecommission = hasPermission('servers:delete');
  const isDecommissioning = server?.status === 'decommissioning';
  const isDecommissioned = server?.status === 'decommissioned';
  const canShowDecommission =
    canDecommission &&
    (server?.status === 'ready' || server?.status === 'failed');

  // Loading
  if (serverLoading || !server) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/dashboard/servers">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Inventory
          </Link>
        </Button>
        <DetailSkeleton />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back link */}
      <Button variant="ghost" size="sm" asChild>
        <Link href="/dashboard/servers">
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Inventory
        </Link>
      </Button>

      {/* Decommissioned banner */}
      {isDecommissioned && (
        <Alert variant="destructive">
          <Ban className="h-4 w-4" />
          <AlertTitle>Server Decommissioned</AlertTitle>
          <AlertDescription>
            This server has been permanently decommissioned. All associated
            resources (EC2 instance, EBS volumes, DNS records, security groups)
            have been destroyed. The Puppet node has been purged and the AWX host
            has been removed.
          </AlertDescription>
        </Alert>
      )}

      {/* Decommissioning banner */}
      {isDecommissioning && (
        <Alert variant="warning">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Decommission In Progress</AlertTitle>
          <AlertDescription>
            This server is currently being decommissioned. The reverse pipeline
            is running to clean up all associated resources. Track the progress
            below.
          </AlertDescription>
        </Alert>
      )}

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3 flex-wrap">
          <h1 className="text-2xl font-bold tracking-tight font-mono">
            {server.server_name}
          </h1>
          <StatusBadge status={server.status} />
          <EnvironmentBadge environment={server.environment} />
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" asChild>
            <Link href={`/dashboard/requests/${server.id}`}>
              <GitBranch className="mr-2 h-4 w-4" />
              View Build
            </Link>
          </Button>
          {canShowDecommission && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setShowDecommissionDialog(true)}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Decommission
            </Button>
          )}
        </div>
      </div>

      {server.status_message && (
        <div className="rounded-md bg-muted px-4 py-3 text-sm">
          {server.status_message}
        </div>
      )}

      {/* Decommission progress tracker */}
      {isDecommissioning && (
        <Card className="border-amber-200 dark:border-amber-800">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base text-amber-700 dark:text-amber-400">
              <Trash2 className="h-4 w-4" />
              Decommission Pipeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            <DecommissionTracker buildSteps={buildSteps} />
          </CardContent>
        </Card>
      )}

      {/* Info grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Server details */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4" />
              Server Information
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-6">
              <InfoRow
                label="Operating System"
                value={getOsFriendlyName(server.os_type)}
              />
              <InfoRow
                label="Instance Size"
                value={getInstanceSizeLabel(server.instance_size)}
              />
              <InfoRow label="Region" value={server.region} />
              <InfoRow
                label="AWS Instance ID"
                value={server.aws_instance_id}
                mono
              />
              <InfoRow label="Private IP" value={server.private_ip} mono />
              <InfoRow label="Public IP" value={server.public_ip} mono />
              <InfoRow label="DNS Name" value={server.dns_name} mono />
            </div>

            <Separator className="my-6" />

            {/* Timestamps */}
            <div className="grid grid-cols-2 gap-6">
              <InfoRow
                label="Created"
                value={
                  server.created_at
                    ? new Date(server.created_at).toLocaleString()
                    : null
                }
              />
              <InfoRow
                label="Last Updated"
                value={
                  server.updated_at
                    ? new Date(server.updated_at).toLocaleString()
                    : null
                }
              />
            </div>
          </CardContent>
        </Card>

        {/* Build pipeline timeline */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Clock className="h-4 w-4" />
              Build Pipeline
            </CardTitle>
          </CardHeader>
          <CardContent>
            {buildSteps && buildSteps.length > 0 ? (
              <BuildTimeline steps={buildSteps} />
            ) : (
              <p className="text-sm text-muted-foreground">
                No build steps available yet.
              </p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Puppet / Compliance section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Shield className="h-4 w-4" />
              Puppet Compliance
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              <InfoRow
                label="Certname"
                value={
                  server.puppet_certname ??
                  puppetStatus?.certname ??
                  null
                }
                mono
              />
              <InfoRow
                label="Node Group"
                value={server.puppet_node_group_id}
              />
              <InfoRow
                label="Last Report Status"
                value={
                  server.puppet_last_report_status ??
                  puppetStatus?.latest_report_status ??
                  null
                }
              />
              <InfoRow
                label="Enrolled At"
                value={
                  server.puppet_enrolled_at
                    ? new Date(server.puppet_enrolled_at).toLocaleString()
                    : null
                }
              />
              {puppetStatus && (
                <>
                  <InfoRow
                    label="Report Environment"
                    value={puppetStatus.report_environment}
                  />
                  <InfoRow
                    label="Last Report"
                    value={
                      puppetStatus.report_timestamp
                        ? new Date(
                            puppetStatus.report_timestamp,
                          ).toLocaleString()
                        : null
                    }
                  />
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Network / Connectivity */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Globe className="h-4 w-4" />
              Network
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-6">
              <InfoRow label="Private IP" value={server.private_ip} mono />
              <InfoRow label="Public IP" value={server.public_ip} mono />
              <InfoRow label="DNS Name" value={server.dns_name} mono />
              <InfoRow label="Region" value={server.region} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ServiceNow CMDB */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CMDBStatusCard serverId={server.id} />
      </div>

      {/* AWX info (if available) */}
      {(server.awx_host_id || (server.awx_job_ids && server.awx_job_ids.length > 0)) && (
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="text-base">AWX Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-6">
              <InfoRow
                label="AWX Host ID"
                value={server.awx_host_id?.toString() ?? null}
              />
              <InfoRow
                label="AWX Job IDs"
                value={
                  server.awx_job_ids && server.awx_job_ids.length > 0
                    ? server.awx_job_ids.join(', ')
                    : null
                }
                mono
              />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Decommission confirmation dialog */}
      <DecommissionDialog
        server={server}
        open={showDecommissionDialog}
        onOpenChange={setShowDecommissionDialog}
      />
    </div>
  );
}
