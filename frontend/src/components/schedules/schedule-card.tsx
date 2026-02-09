'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { cn } from '@/lib/utils';
import {
  Calendar,
  Clock,
  MoreVertical,
  Pause,
  Play,
  Repeat,
  Trash2,
  Zap,
} from 'lucide-react';
import { describeCron } from '@/components/schedules/cron-builder';
import type { BuildSchedule } from '@/lib/api/schedules';

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

const TYPE_CONFIG: Record<
  string,
  { label: string; icon: React.ElementType }
> = {
  one_time: { label: 'One-Time', icon: Calendar },
  recurring: { label: 'Recurring', icon: Repeat },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
    // Future
    if (days > 0) return `in ${days}d ${hours % 24}h`;
    if (hours > 0) return `in ${hours}h ${minutes % 60}m`;
    return `in ${minutes}m`;
  }

  // Past
  if (days > 0) return `${days}d ago`;
  if (hours > 0) return `${hours}h ago`;
  return `${minutes}m ago`;
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface ScheduleCardProps {
  schedule: BuildSchedule;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onRunNow?: (id: string) => void;
  onDelete?: (id: string) => void;
}

export function ScheduleCard({
  schedule,
  onPause,
  onResume,
  onRunNow,
  onDelete,
}: ScheduleCardProps) {
  const statusStyle = STATUS_CONFIG[schedule.status] || {
    label: schedule.status,
    className: 'bg-gray-100 text-gray-800',
  };

  const typeInfo = TYPE_CONFIG[schedule.schedule_type] || {
    label: schedule.schedule_type,
    icon: Calendar,
  };

  const TypeIcon = typeInfo.icon;

  const cronDescription = useMemo(() => {
    if (schedule.schedule_type === 'recurring' && schedule.cron_expression) {
      return describeCron(schedule.cron_expression);
    }
    return null;
  }, [schedule.schedule_type, schedule.cron_expression]);

  const canPause = schedule.status === 'active';
  const canResume = schedule.status === 'paused';
  const canRunNow = schedule.status === 'active' || schedule.status === 'paused';

  return (
    <Card className="group transition-colors hover:border-foreground/20">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <Link
              href={`/dashboard/schedules/${schedule.id}`}
              className="group/link"
            >
              <CardTitle className="text-base font-semibold truncate group-hover/link:text-primary transition-colors">
                {schedule.name}
              </CardTitle>
            </Link>
            {schedule.description && (
              <p className="mt-1 text-sm text-muted-foreground line-clamp-1">
                {schedule.description}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Badge
              variant="outline"
              className={cn('border-0 font-medium text-xs', statusStyle.className)}
            >
              {statusStyle.label}
            </Badge>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreVertical className="h-4 w-4" />
                  <span className="sr-only">Actions</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem asChild>
                  <Link href={`/dashboard/schedules/${schedule.id}`}>
                    View Details
                  </Link>
                </DropdownMenuItem>
                {canPause && onPause && (
                  <DropdownMenuItem onClick={() => onPause(schedule.id)}>
                    <Pause className="mr-2 h-4 w-4" />
                    Pause
                  </DropdownMenuItem>
                )}
                {canResume && onResume && (
                  <DropdownMenuItem onClick={() => onResume(schedule.id)}>
                    <Play className="mr-2 h-4 w-4" />
                    Resume
                  </DropdownMenuItem>
                )}
                {canRunNow && onRunNow && (
                  <DropdownMenuItem onClick={() => onRunNow(schedule.id)}>
                    <Zap className="mr-2 h-4 w-4" />
                    Run Now
                  </DropdownMenuItem>
                )}
                <DropdownMenuSeparator />
                {onDelete && (
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={() => onDelete(schedule.id)}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          {/* Type */}
          <div className="flex items-center gap-2 text-muted-foreground">
            <TypeIcon className="h-4 w-4 flex-shrink-0" />
            <span>{typeInfo.label}</span>
          </div>

          {/* Run count */}
          <div className="flex items-center gap-2 text-muted-foreground">
            <Zap className="h-4 w-4 flex-shrink-0" />
            <span>
              {schedule.run_count} run{schedule.run_count !== 1 ? 's' : ''}
              {schedule.max_runs != null && ` / ${schedule.max_runs} max`}
            </span>
          </div>

          {/* Next run */}
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4 flex-shrink-0" />
            <div className="min-w-0">
              <span className="block text-xs font-medium text-muted-foreground/70">
                Next run
              </span>
              {schedule.next_run_at ? (
                <span
                  className="block truncate"
                  title={formatDateTime(schedule.next_run_at)}
                >
                  {formatRelativeTime(schedule.next_run_at)}
                </span>
              ) : (
                <span className="italic">None scheduled</span>
              )}
            </div>
          </div>

          {/* Last run */}
          <div className="flex items-center gap-2 text-muted-foreground">
            <Clock className="h-4 w-4 flex-shrink-0" />
            <div className="min-w-0">
              <span className="block text-xs font-medium text-muted-foreground/70">
                Last run
              </span>
              {schedule.last_run_at ? (
                <span
                  className="block truncate"
                  title={formatDateTime(schedule.last_run_at)}
                >
                  {formatRelativeTime(schedule.last_run_at)}
                </span>
              ) : (
                <span className="italic">Never</span>
              )}
            </div>
          </div>
        </div>

        {/* Cron description for recurring schedules */}
        {cronDescription && (
          <div className="mt-3 flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            <Repeat className="h-3.5 w-3.5 flex-shrink-0" />
            <span>{cronDescription}</span>
            <code className="ml-auto font-mono text-[10px] opacity-70">
              {schedule.cron_expression}
            </code>
          </div>
        )}

        {/* One-time scheduled date */}
        {schedule.schedule_type === 'one_time' && schedule.scheduled_at && (
          <div className="mt-3 flex items-center gap-2 rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
            <Calendar className="h-3.5 w-3.5 flex-shrink-0" />
            <span>Scheduled for {formatDateTime(schedule.scheduled_at)}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
