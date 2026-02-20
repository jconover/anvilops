'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ConfirmationDialog } from '@/components/shared/confirmation-dialog';
import { ScalingVisualization } from '@/components/scaling/scaling-visualization';
import { ScaleDialog } from '@/components/scaling/scale-dialog';
import {
  useScalingGroup,
  useScaleGroup,
  usePauseGroup,
  useResumeGroup,
  useDeleteScalingGroup,
} from '@/lib/api/scaling';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  AlertCircle,
  ArrowLeft,
  Clock,
  Gauge,
  Loader2,
  Pause,
  Play,
  Server,
  Settings2,
  Trash2,
  TrendingUp,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  string,
  { label: string; className: string; pulse?: boolean }
> = {
  active: {
    label: 'Active',
    className:
      'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  },
  paused: {
    label: 'Paused',
    className:
      'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  },
  scaling_up: {
    label: 'Scaling Up',
    className:
      'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    pulse: true,
  },
  scaling_down: {
    label: 'Scaling Down',
    className:
      'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
    pulse: true,
  },
  provisioning: {
    label: 'Provisioning',
    className:
      'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
    pulse: true,
  },
  error: {
    label: 'Error',
    className: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  },
};

const MEMBER_STATUS: Record<string, { label: string; className: string }> = {
  active: {
    label: 'Active',
    className: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  },
  provisioning: {
    label: 'Provisioning',
    className: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
  },
  terminating: {
    label: 'Terminating',
    className: 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
  },
  failed: {
    label: 'Failed',
    className: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  },
};

const OS_DISPLAY: Record<string, string> = {
  windows_2022: 'Windows Server 2022',
  windows_2019: 'Windows Server 2019',
  amazon_linux_2023: 'Amazon Linux 2023',
  ubuntu_2204: 'Ubuntu 22.04 LTS',
  rhel_9: 'RHEL 9',
};

const SIZE_DISPLAY: Record<string, string> = {
  small: 'Small',
  medium: 'Medium',
  large: 'Large',
  xl: 'XL',
};

// ---------------------------------------------------------------------------
// Cosmetic scale history data
// ---------------------------------------------------------------------------

interface ScaleHistoryEntry {
  timestamp: string;
  action: string;
  from: number;
  to: number;
}

function generateScaleHistory(
  group: { created_at: string; current_count: number; desired_count: number; last_scaled_at: string | null },
): ScaleHistoryEntry[] {
  const history: ScaleHistoryEntry[] = [];
  history.push({
    timestamp: group.created_at,
    action: 'Group created',
    from: 0,
    to: group.desired_count,
  });
  if (group.last_scaled_at) {
    history.push({
      timestamp: group.last_scaled_at,
      action: 'Manual scale',
      from: group.current_count > group.desired_count
        ? group.current_count
        : Math.max(1, group.desired_count - 1),
      to: group.desired_count,
    });
  }
  return history;
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ScalingGroupDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [scaleDialogOpen, setScaleDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const {
    data: group,
    isLoading,
    isError,
    error: fetchError,
  } = useScalingGroup(id);

  const scaleMutation = useScaleGroup();
  const pauseMutation = usePauseGroup();
  const resumeMutation = useResumeGroup();
  const deleteMutation = useDeleteScalingGroup();

  const isPaused = group?.status === 'paused';
  const isActive = group?.status === 'active';
  const isBusy =
    scaleMutation.isPending ||
    pauseMutation.isPending ||
    resumeMutation.isPending;

  const handleScale = (desiredCount: number) => {
    scaleMutation.mutate(
      { id, desiredCount },
      {
        onSuccess: (updated) => {
          toast.success(
            `Scaling ${updated.name} to ${desiredCount} instances`,
          );
          setScaleDialogOpen(false);
        },
        onError: (err) => {
          toast.error('Failed to scale group', {
            description: err.message ?? 'An unexpected error occurred.',
          });
        },
      },
    );
  };

  const handlePauseResume = () => {
    if (isPaused) {
      resumeMutation.mutate(id, {
        onSuccess: (updated) =>
          toast.success(`Resumed scaling for ${updated.name}`),
        onError: (err) =>
          toast.error('Failed to resume', { description: err.message }),
      });
    } else {
      pauseMutation.mutate(id, {
        onSuccess: (updated) =>
          toast.success(`Paused scaling for ${updated.name}`),
        onError: (err) =>
          toast.error('Failed to pause', { description: err.message }),
      });
    }
  };

  const handleDelete = () => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success('Scaling group deleted');
        router.push('/dashboard/scaling');
      },
      onError: (err) => {
        toast.error('Failed to delete scaling group', {
          description: err.message ?? 'An unexpected error occurred.',
        });
      },
    });
  };

  const statusCfg = group
    ? STATUS_CONFIG[group.status] ?? {
        label: group.status,
        className: 'bg-gray-100 text-gray-800',
      }
    : null;

  const scaleHistory = group ? generateScaleHistory(group) : [];

  return (
    <div className="space-y-8">
      {/* Back button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push('/dashboard/scaling')}
        className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Scaling Groups
      </Button>

      {/* Error state */}
      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Failed to load scaling group
            </p>
            <p className="mt-0.5 text-xs text-red-700 dark:text-red-400">
              {fetchError instanceof Error
                ? fetchError.message
                : 'Scaling group not found or an unexpected error occurred.'}
            </p>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-6">
          <div className="space-y-2">
            <Skeleton className="h-9 w-[300px]" />
            <Skeleton className="h-5 w-[200px]" />
          </div>
          <Skeleton className="h-[200px] w-full rounded-lg" />
          <div className="grid gap-6 lg:grid-cols-2">
            <Skeleton className="h-[250px] rounded-lg" />
            <Skeleton className="h-[250px] rounded-lg" />
          </div>
        </div>
      )}

      {/* Loaded content */}
      {group && !isLoading && (
        <>
          {/* ---------- Header ---------- */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight">
                  {group.name}
                </h1>
                {statusCfg && (
                  <Badge
                    variant="outline"
                    className={cn(
                      'border-0 font-medium',
                      statusCfg.className,
                      statusCfg.pulse && 'animate-pulse',
                    )}
                  >
                    {statusCfg.label}
                  </Badge>
                )}
              </div>
              {group.description && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {group.description}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-3 mt-2 text-xs text-muted-foreground">
                <span>{group.environment}</span>
                <span className="text-muted-foreground/40">|</span>
                <span>{OS_DISPLAY[group.os_type] ?? group.os_type}</span>
                <span className="text-muted-foreground/40">|</span>
                <span>{SIZE_DISPLAY[group.instance_size] ?? group.instance_size}</span>
                <span className="text-muted-foreground/40">|</span>
                <span>{group.region}</span>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!isActive || isBusy}
                onClick={() => setScaleDialogOpen(true)}
              >
                <TrendingUp className="mr-2 h-4 w-4" />
                Scale
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={isBusy || (!isActive && !isPaused)}
                onClick={handlePauseResume}
              >
                {pauseMutation.isPending || resumeMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : isPaused ? (
                  <Play className="mr-2 h-4 w-4" />
                ) : (
                  <Pause className="mr-2 h-4 w-4" />
                )}
                {isPaused ? 'Resume' : 'Pause'}
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => setDeleteDialogOpen(true)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            </div>
          </div>

          {/* ---------- Scaling Visualization ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Gauge className="h-5 w-5" />
                Scaling Status
              </CardTitle>
              <CardDescription>
                Visual representation of the current scaling range and instance
                counts.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ScalingVisualization
                min={group.min_instances}
                max={group.max_instances}
                current={group.current_count}
                desired={group.desired_count}
              />
            </CardContent>
          </Card>

          {/* ---------- Two-column: Config + History ---------- */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Scaling Configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Settings2 className="h-5 w-5" />
                  Scaling Configuration
                </CardTitle>
                <CardDescription>
                  Thresholds and cooldown settings for automatic scaling.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="space-y-4">
                  <ConfigRow
                    label="Minimum instances"
                    value={String(group.min_instances)}
                  />
                  <ConfigRow
                    label="Maximum instances"
                    value={String(group.max_instances)}
                  />
                  <ConfigRow
                    label="Desired count"
                    value={String(group.desired_count)}
                  />
                  <ConfigRow
                    label="Scale up threshold"
                    value={`${group.scale_up_threshold}%`}
                  />
                  <ConfigRow
                    label="Scale down threshold"
                    value={`${group.scale_down_threshold}%`}
                  />
                  <ConfigRow
                    label="Cooldown period"
                    value={`${group.cooldown_seconds}s`}
                  />
                </dl>
              </CardContent>
            </Card>

            {/* Scale History Timeline (cosmetic) */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Clock className="h-5 w-5" />
                  Scale History
                </CardTitle>
                <CardDescription>
                  Timeline of recent scaling events for this group.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {scaleHistory.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    No scaling events recorded yet.
                  </p>
                ) : (
                  <div className="relative space-y-0">
                    {/* Timeline line */}
                    <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />
                    {scaleHistory.map((entry, idx) => (
                      <div key={idx} className="relative flex gap-3 pb-6 last:pb-0">
                        <div className="relative z-10 mt-1.5 h-3.5 w-3.5 rounded-full border-2 border-primary bg-background shrink-0" />
                        <div className="min-w-0 space-y-0.5">
                          <p className="text-sm font-medium">{entry.action}</p>
                          <p className="text-xs text-muted-foreground">
                            {entry.from} &rarr; {entry.to} instances
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {new Date(entry.timestamp).toLocaleDateString(
                              undefined,
                              {
                                month: 'short',
                                day: 'numeric',
                                year: 'numeric',
                                hour: '2-digit',
                                minute: '2-digit',
                              },
                            )}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* ---------- Members Table ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Server className="h-5 w-5" />
                Group Members
              </CardTitle>
              <CardDescription>
                Servers currently managed by this scaling group.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {group.members.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <Server className="h-8 w-8 text-muted-foreground/50 mb-2" />
                  <p className="text-sm text-muted-foreground">
                    No members in this scaling group yet.
                  </p>
                </div>
              ) : (
                <div className="rounded-md border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-12">#</TableHead>
                        <TableHead>Server Name</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Private IP</TableHead>
                        <TableHead>Server Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {group.members.map((member) => {
                        const mStatus =
                          MEMBER_STATUS[member.status] ?? {
                            label: member.status,
                            className: 'bg-gray-100 text-gray-700',
                          };
                        return (
                          <TableRow key={member.id}>
                            <TableCell className="text-muted-foreground">
                              {member.member_index}
                            </TableCell>
                            <TableCell className="font-medium">
                              {member.server_name ?? (
                                <span className="text-muted-foreground italic">
                                  Pending
                                </span>
                              )}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant="outline"
                                className={cn(
                                  'border-0 text-xs font-medium',
                                  mStatus.className,
                                )}
                              >
                                {mStatus.label}
                              </Badge>
                            </TableCell>
                            <TableCell className="font-mono text-sm">
                              {member.private_ip ?? (
                                <span className="text-muted-foreground italic">
                                  --
                                </span>
                              )}
                            </TableCell>
                            <TableCell>
                              {member.server_status ?? (
                                <span className="text-muted-foreground italic">
                                  --
                                </span>
                              )}
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {/* ---------- Dialogs ---------- */}
      {group && (
        <>
          <ScaleDialog
            open={scaleDialogOpen}
            onOpenChange={setScaleDialogOpen}
            groupName={group.name}
            currentCount={group.current_count}
            minInstances={group.min_instances}
            maxInstances={group.max_instances}
            onConfirm={handleScale}
            isLoading={scaleMutation.isPending}
          />
          <ConfirmationDialog
            open={deleteDialogOpen}
            onOpenChange={setDeleteDialogOpen}
            title="Delete Scaling Group"
            description={`Are you sure you want to delete "${group.name}"? This will terminate all ${group.current_count} member servers and cannot be undone.`}
            confirmLabel="Delete Group"
            variant="destructive"
            onConfirm={handleDelete}
            isLoading={deleteMutation.isPending}
          />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function ConfigRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}
