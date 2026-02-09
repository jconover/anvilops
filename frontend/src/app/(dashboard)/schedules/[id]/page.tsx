'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { ConfirmationDialog } from '@/components/shared/confirmation-dialog';
import { ExecutionHistory } from '@/components/schedules/execution-history';
import { describeCron } from '@/components/schedules/cron-builder';
import { cn } from '@/lib/utils';
import {
  useSchedule,
  useScheduleExecutions,
  usePauseSchedule,
  useResumeSchedule,
  useRunNow,
  useDeleteSchedule,
} from '@/lib/api/schedules';
import {
  AlertCircle,
  ArrowLeft,
  Calendar,
  Clock,
  Edit,
  Globe,
  Hash,
  Pause,
  Play,
  Repeat,
  Server,
  Settings,
  Trash2,
  Zap,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Status badge config
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  string,
  { label: string; className: string }
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
  completed: {
    label: 'Completed',
    className:
      'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
  },
  expired: {
    label: 'Expired',
    className:
      'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  });
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const absDiffMs = Math.abs(diffMs);

  if (absDiffMs < 60_000) return 'just now';

  const minutes = Math.floor(absDiffMs / 60_000);
  const hours = Math.floor(absDiffMs / 3_600_000);
  const days = Math.floor(absDiffMs / 86_400_000);

  if (diffMs > 0) {
    if (days > 0) return `in ${days}d ${hours % 24}h`;
    if (hours > 0) return `in ${hours}h ${minutes % 60}m`;
    return `in ${minutes}m`;
  }

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  return `${minutes}m ago`;
}

const CONFIG_LABELS: Record<string, string> = {
  environment: 'Environment',
  os_type: 'Operating System',
  instance_size: 'Instance Size',
  region: 'Region',
  puppet_role: 'Puppet Role',
  template_id: 'Template',
};

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ScheduleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  const {
    data: schedule,
    isLoading: scheduleLoading,
    isError: scheduleError,
    error: scheduleErr,
  } = useSchedule(id);

  const {
    data: executionsData,
    isLoading: executionsLoading,
  } = useScheduleExecutions(id);

  const pauseMutation = usePauseSchedule();
  const resumeMutation = useResumeSchedule();
  const runNowMutation = useRunNow();
  const deleteMutation = useDeleteSchedule();

  const executions = executionsData?.executions ?? [];

  // ------------------------------------------------------------------
  // Action handlers
  // ------------------------------------------------------------------

  const handlePause = () => {
    pauseMutation.mutate(id, {
      onSuccess: () => toast.success('Schedule paused'),
      onError: (err) =>
        toast.error('Failed to pause schedule', { description: err.message }),
    });
  };

  const handleResume = () => {
    resumeMutation.mutate(id, {
      onSuccess: () => toast.success('Schedule resumed'),
      onError: (err) =>
        toast.error('Failed to resume schedule', { description: err.message }),
    });
  };

  const handleRunNow = () => {
    runNowMutation.mutate(id, {
      onSuccess: () =>
        toast.success('Execution triggered', {
          description: 'The schedule is running now.',
        }),
      onError: (err) =>
        toast.error('Failed to trigger execution', {
          description: err.message,
        }),
    });
  };

  const handleDelete = () => {
    deleteMutation.mutate(id, {
      onSuccess: () => {
        toast.success('Schedule deleted');
        router.push('/dashboard/schedules');
      },
      onError: (err) =>
        toast.error('Failed to delete schedule', { description: err.message }),
    });
  };

  const canPause = schedule?.status === 'active';
  const canResume = schedule?.status === 'paused';
  const canRunNow =
    schedule?.status === 'active' || schedule?.status === 'paused';

  const statusStyle = schedule
    ? STATUS_CONFIG[schedule.status] || {
        label: schedule.status,
        className: 'bg-gray-100 text-gray-800',
      }
    : null;

  const cronDescription =
    schedule?.schedule_type === 'recurring' && schedule.cron_expression
      ? describeCron(schedule.cron_expression)
      : null;

  return (
    <div className="space-y-8">
      {/* Back button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push('/dashboard/schedules')}
        className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Schedules
      </Button>

      {/* Error state */}
      {scheduleError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Failed to load schedule
            </p>
            <p className="mt-0.5 text-xs text-red-700 dark:text-red-400">
              {scheduleErr instanceof Error
                ? scheduleErr.message
                : 'Schedule not found or an unexpected error occurred.'}
            </p>
          </div>
        </div>
      )}

      {/* Loading state */}
      {scheduleLoading && (
        <div className="space-y-6">
          <div className="space-y-2">
            <Skeleton className="h-9 w-[300px]" />
            <Skeleton className="h-5 w-[200px]" />
          </div>
          <Skeleton className="h-[200px] w-full rounded-lg" />
          <Skeleton className="h-[300px] w-full rounded-lg" />
        </div>
      )}

      {/* Schedule loaded */}
      {schedule && !scheduleLoading && (
        <>
          {/* ---------- Header ---------- */}
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight">
                  {schedule.name}
                </h1>
                {statusStyle && (
                  <Badge
                    variant="outline"
                    className={cn(
                      'border-0 font-medium text-sm',
                      statusStyle.className,
                    )}
                  >
                    {statusStyle.label}
                  </Badge>
                )}
              </div>
              {schedule.description && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {schedule.description}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-sm text-muted-foreground">
                <span className="inline-flex items-center gap-1.5">
                  {schedule.schedule_type === 'recurring' ? (
                    <Repeat className="h-3.5 w-3.5" />
                  ) : (
                    <Calendar className="h-3.5 w-3.5" />
                  )}
                  {schedule.schedule_type === 'recurring'
                    ? 'Recurring'
                    : 'One-Time'}
                </span>
                {schedule.next_run_at && (
                  <span
                    className="inline-flex items-center gap-1.5"
                    title={formatDateTime(schedule.next_run_at)}
                  >
                    <Clock className="h-3.5 w-3.5" />
                    Next: {formatRelativeTime(schedule.next_run_at)}
                  </span>
                )}
                <span className="inline-flex items-center gap-1.5">
                  <Zap className="h-3.5 w-3.5" />
                  {schedule.run_count} run
                  {schedule.run_count !== 1 ? 's' : ''}
                  {schedule.max_runs != null &&
                    ` / ${schedule.max_runs} max`}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex flex-wrap items-center gap-2">
              {canPause && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handlePause}
                  disabled={pauseMutation.isPending}
                >
                  <Pause className="mr-2 h-4 w-4" />
                  Pause
                </Button>
              )}
              {canResume && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResume}
                  disabled={resumeMutation.isPending}
                >
                  <Play className="mr-2 h-4 w-4" />
                  Resume
                </Button>
              )}
              {canRunNow && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleRunNow}
                  disabled={runNowMutation.isPending}
                >
                  <Zap className="mr-2 h-4 w-4" />
                  Run Now
                </Button>
              )}
              <Button variant="outline" size="sm" asChild>
                <Link href={`/dashboard/schedules/${id}/edit`}>
                  <Edit className="mr-2 h-4 w-4" />
                  Edit
                </Link>
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

          {/* ---------- Configuration card ---------- */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Schedule configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Settings className="h-5 w-5" />
                  Schedule Configuration
                </CardTitle>
                <CardDescription>
                  Timing and frequency settings
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="space-y-4">
                  {/* Type */}
                  <div className="flex items-start gap-3">
                    {schedule.schedule_type === 'recurring' ? (
                      <Repeat className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    ) : (
                      <Calendar className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    )}
                    <div>
                      <dt className="text-xs font-medium text-muted-foreground">
                        Type
                      </dt>
                      <dd className="mt-0.5 text-sm">
                        {schedule.schedule_type === 'recurring'
                          ? 'Recurring'
                          : 'One-Time'}
                      </dd>
                    </div>
                  </div>

                  {/* Cron expression */}
                  {schedule.cron_expression && (
                    <div className="flex items-start gap-3">
                      <Clock className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      <div>
                        <dt className="text-xs font-medium text-muted-foreground">
                          Cron Expression
                        </dt>
                        <dd className="mt-0.5 text-sm font-mono">
                          {schedule.cron_expression}
                        </dd>
                        {cronDescription && (
                          <dd className="mt-1 text-xs text-muted-foreground">
                            {cronDescription}
                          </dd>
                        )}
                      </div>
                    </div>
                  )}

                  {/* One-time date */}
                  {schedule.scheduled_at && (
                    <div className="flex items-start gap-3">
                      <Calendar className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      <div>
                        <dt className="text-xs font-medium text-muted-foreground">
                          Scheduled At
                        </dt>
                        <dd className="mt-0.5 text-sm">
                          {formatDateTime(schedule.scheduled_at)}
                        </dd>
                      </div>
                    </div>
                  )}

                  {/* Timezone */}
                  <div className="flex items-start gap-3">
                    <Globe className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                    <div>
                      <dt className="text-xs font-medium text-muted-foreground">
                        Timezone
                      </dt>
                      <dd className="mt-0.5 text-sm">{schedule.timezone}</dd>
                    </div>
                  </div>

                  {/* Max runs */}
                  {schedule.max_runs != null && (
                    <div className="flex items-start gap-3">
                      <Hash className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      <div>
                        <dt className="text-xs font-medium text-muted-foreground">
                          Maximum Runs
                        </dt>
                        <dd className="mt-0.5 text-sm">
                          {schedule.run_count} / {schedule.max_runs}
                        </dd>
                      </div>
                    </div>
                  )}

                  {/* Next run */}
                  {schedule.next_run_at && (
                    <div className="flex items-start gap-3">
                      <Clock className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      <div>
                        <dt className="text-xs font-medium text-muted-foreground">
                          Next Run
                        </dt>
                        <dd className="mt-0.5 text-sm">
                          {formatDateTime(schedule.next_run_at)}
                          <span className="ml-2 text-xs text-muted-foreground">
                            ({formatRelativeTime(schedule.next_run_at)})
                          </span>
                        </dd>
                      </div>
                    </div>
                  )}

                  {/* Last run */}
                  {schedule.last_run_at && (
                    <div className="flex items-start gap-3">
                      <Clock className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      <div>
                        <dt className="text-xs font-medium text-muted-foreground">
                          Last Run
                        </dt>
                        <dd className="mt-0.5 text-sm">
                          {formatDateTime(schedule.last_run_at)}
                          <span className="ml-2 text-xs text-muted-foreground">
                            ({formatRelativeTime(schedule.last_run_at)})
                          </span>
                        </dd>
                      </div>
                    </div>
                  )}
                </dl>
              </CardContent>
            </Card>

            {/* Server configuration */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <Server className="h-5 w-5" />
                  Server Configuration
                </CardTitle>
                <CardDescription>
                  Server parameters for scheduled builds
                </CardDescription>
              </CardHeader>
              <CardContent>
                {schedule.server_config &&
                Object.keys(schedule.server_config).length > 0 ? (
                  <dl className="space-y-4">
                    {Object.entries(schedule.server_config).map(
                      ([key, value]) => {
                        if (value == null || value === '') return null;
                        const label = CONFIG_LABELS[key] || key;
                        return (
                          <div key={key} className="flex items-start gap-3">
                            <Server className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                            <div>
                              <dt className="text-xs font-medium text-muted-foreground">
                                {label}
                              </dt>
                              <dd className="mt-0.5 text-sm">
                                {String(value)}
                              </dd>
                            </div>
                          </div>
                        );
                      },
                    )}
                  </dl>
                ) : (
                  <p className="text-sm text-muted-foreground italic">
                    No server configuration defined.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>

          {/* ---------- Execution history ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Execution History</CardTitle>
              <CardDescription>
                Past and upcoming execution records for this schedule
              </CardDescription>
            </CardHeader>
            <CardContent>
              <ExecutionHistory
                executions={executions}
                isLoading={executionsLoading}
              />
            </CardContent>
          </Card>
        </>
      )}

      {/* Delete confirmation */}
      <ConfirmationDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Delete Schedule"
        description="Are you sure you want to delete this schedule? This action cannot be undone. Future scheduled executions will be cancelled."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDelete}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
