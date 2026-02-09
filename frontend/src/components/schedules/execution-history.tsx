'use client';

import Link from 'next/link';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  MinusCircle,
  ExternalLink,
} from 'lucide-react';
import type { ScheduleExecution, ExecutionStatus } from '@/lib/api/schedules';

// ---------------------------------------------------------------------------
// Status config
// ---------------------------------------------------------------------------

const EXECUTION_STATUS_CONFIG: Record<
  ExecutionStatus,
  {
    label: string;
    className: string;
    icon: React.ElementType;
  }
> = {
  completed: {
    label: 'Completed',
    className:
      'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    icon: CheckCircle2,
  },
  running: {
    label: 'Running',
    className:
      'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    icon: Loader2,
  },
  failed: {
    label: 'Failed',
    className:
      'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    icon: AlertCircle,
  },
  pending: {
    label: 'Pending',
    className:
      'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    icon: Clock,
  },
  skipped: {
    label: 'Skipped',
    className:
      'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
    icon: MinusCircle,
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
  });
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();

  if (diffMs < 60_000) return 'just now';

  const minutes = Math.floor(diffMs / 60_000);
  const hours = Math.floor(diffMs / 3_600_000);
  const days = Math.floor(diffMs / 86_400_000);

  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  return `${minutes}m ago`;
}

function computeDuration(
  started: string | null,
  completed: string | null,
): string | null {
  if (!started || !completed) return null;

  const ms =
    new Date(completed).getTime() - new Date(started).getTime();

  if (ms < 0) return null;
  if (ms < 1000) return '<1s';

  const seconds = Math.floor(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);

  if (hours > 0) {
    return `${hours}h ${minutes % 60}m`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds % 60}s`;
  }
  return `${seconds}s`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ExecutionHistoryProps {
  executions: ScheduleExecution[];
  isLoading?: boolean;
  className?: string;
}

export function ExecutionHistory({
  executions,
  isLoading,
  className,
}: ExecutionHistoryProps) {
  if (isLoading) {
    return (
      <div className={cn('space-y-2', className)}>
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full rounded-md" />
        ))}
      </div>
    );
  }

  if (executions.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center rounded-lg border border-dashed p-8 text-center',
          className,
        )}
      >
        <Clock className="mb-3 h-10 w-10 text-muted-foreground/50" />
        <p className="text-sm font-medium text-muted-foreground">
          No executions yet
        </p>
        <p className="mt-1 text-xs text-muted-foreground/70">
          Executions will appear here once the schedule runs.
        </p>
      </div>
    );
  }

  return (
    <div className={cn('rounded-md border', className)}>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Scheduled For</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Server</TableHead>
            <TableHead>Duration</TableHead>
            <TableHead>Error</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {executions.map((execution) => {
            const statusConfig =
              EXECUTION_STATUS_CONFIG[execution.status] ||
              EXECUTION_STATUS_CONFIG.pending;
            const StatusIcon = statusConfig.icon;
            const duration = computeDuration(
              execution.started_at,
              execution.completed_at,
            );

            return (
              <TableRow key={execution.id}>
                {/* Scheduled for */}
                <TableCell>
                  <div>
                    <span
                      className="text-sm"
                      title={formatDateTime(execution.scheduled_for)}
                    >
                      {formatRelativeTime(execution.scheduled_for)}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {formatDateTime(execution.scheduled_for)}
                    </span>
                  </div>
                </TableCell>

                {/* Status */}
                <TableCell>
                  <Badge
                    variant="outline"
                    className={cn(
                      'border-0 font-medium gap-1',
                      statusConfig.className,
                    )}
                  >
                    <StatusIcon
                      className={cn(
                        'h-3 w-3',
                        execution.status === 'running' && 'animate-spin',
                      )}
                    />
                    {statusConfig.label}
                  </Badge>
                </TableCell>

                {/* Server link */}
                <TableCell>
                  {execution.server_request_id ? (
                    <Link
                      href={`/dashboard/requests/${execution.server_request_id}`}
                      className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                    >
                      <span className="font-mono text-xs">
                        {execution.server_request_id.slice(0, 8)}
                      </span>
                      <ExternalLink className="h-3 w-3" />
                    </Link>
                  ) : (
                    <span className="text-sm text-muted-foreground italic">
                      --
                    </span>
                  )}
                </TableCell>

                {/* Duration */}
                <TableCell>
                  {duration ? (
                    <span className="text-sm font-mono">{duration}</span>
                  ) : (
                    <span className="text-sm text-muted-foreground italic">
                      --
                    </span>
                  )}
                </TableCell>

                {/* Error */}
                <TableCell>
                  {execution.error_message ? (
                    <span
                      className="text-sm text-red-600 dark:text-red-400 line-clamp-1"
                      title={execution.error_message}
                    >
                      {execution.error_message}
                    </span>
                  ) : (
                    <span className="text-sm text-muted-foreground italic">
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
  );
}
