'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import {
  ChevronRight,
  Loader2,
  Minus,
  Pause,
  Play,
  Plus,
  Server,
} from 'lucide-react';

import type { ScalingGroup } from '@/lib/api/scaling';
import { ScaleDialog } from './scale-dialog';

// ---------------------------------------------------------------------------
// Status styling
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

const ENV_CONFIG: Record<string, string> = {
  dev: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
  staging:
    'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
  production: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ScalingCardProps {
  group: ScalingGroup;
  onScale: (id: string, desiredCount: number) => void;
  onPause: (id: string) => void;
  onResume: (id: string) => void;
  isScaling?: boolean;
  isPausing?: boolean;
  isResuming?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Summary card for a scaling group in the list view.
 *
 * Displays name, status, environment, an instance gauge bar, quick scale
 * buttons (+1 / -1), and a Pause/Resume toggle.
 */
export function ScalingCard({
  group,
  onScale,
  onPause,
  onResume,
  isScaling = false,
  isPausing = false,
  isResuming = false,
}: ScalingCardProps) {
  const [scaleDialogOpen, setScaleDialogOpen] = useState(false);

  const statusCfg = STATUS_CONFIG[group.status] ?? {
    label: group.status,
    className: 'bg-gray-100 text-gray-800',
  };
  const envClass =
    ENV_CONFIG[group.environment] ??
    'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300';

  const isPaused = group.status === 'paused';
  const isActive = group.status === 'active';
  const isBusy = isScaling || isPausing || isResuming;

  // Gauge: percentage of current count within the min-max range.
  const range = group.max_instances - group.min_instances || 1;
  const gaugePct = ((group.current_count - group.min_instances) / range) * 100;
  const clampedPct = Math.min(100, Math.max(0, gaugePct));

  const gaugeColor =
    group.current_count >= group.max_instances
      ? 'bg-red-500'
      : group.current_count !== group.desired_count
        ? 'bg-yellow-500'
        : 'bg-green-500';

  return (
    <>
      <Card className="group relative overflow-hidden transition-shadow hover:shadow-md">
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
          <div className="space-y-1.5 min-w-0">
            <CardTitle className="text-base font-semibold truncate">
              <Link
                href={`/dashboard/scaling/${group.id}`}
                className="hover:underline"
              >
                {group.name}
              </Link>
            </CardTitle>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge
                variant="outline"
                className={cn(
                  'border-0 font-medium text-xs',
                  statusCfg.className,
                  statusCfg.pulse && 'animate-pulse',
                )}
              >
                {statusCfg.label}
              </Badge>
              <Badge
                variant="outline"
                className={cn('border-0 font-medium text-xs', envClass)}
              >
                {group.environment}
              </Badge>
            </div>
          </div>
          <Link
            href={`/dashboard/scaling/${group.id}`}
            className="shrink-0 text-muted-foreground hover:text-foreground transition-colors"
          >
            <ChevronRight className="h-5 w-5" />
          </Link>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Instance counts */}
          <div className="flex items-center gap-2 text-sm">
            <Server className="h-4 w-4 text-muted-foreground" />
            <span className="font-semibold">{group.current_count}</span>
            <span className="text-muted-foreground">/</span>
            <span className="text-muted-foreground">{group.desired_count} desired</span>
            <span className="text-muted-foreground text-xs ml-auto">
              ({group.min_instances}&ndash;{group.max_instances})
            </span>
          </div>

          {/* Instance gauge bar */}
          <div className="space-y-1">
            <div className="h-2 w-full rounded-full bg-muted/50 overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-700 ease-in-out',
                  gaugeColor,
                )}
                style={{ width: `${clampedPct}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] text-muted-foreground">
              <span>{group.min_instances}</span>
              <span>{group.max_instances}</span>
            </div>
          </div>

          {/* Last scaled */}
          {group.last_scaled_at && (
            <p className="text-xs text-muted-foreground">
              Last scaled:{' '}
              {new Date(group.last_scaled_at).toLocaleDateString(undefined, {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              })}
            </p>
          )}

          {/* Quick actions */}
          <div className="flex items-center gap-2 pt-1">
            <TooltipProvider delayDuration={300}>
              {/* Quick scale -1 */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={
                      group.current_count <= group.min_instances ||
                      !isActive ||
                      isBusy
                    }
                    onClick={() =>
                      onScale(group.id, group.desired_count - 1)
                    }
                  >
                    {isScaling ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Minus className="h-3.5 w-3.5" />
                    )}
                    <span className="sr-only">Scale down by 1</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Scale down by 1</TooltipContent>
              </Tooltip>

              {/* Quick scale +1 */}
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8"
                    disabled={
                      group.current_count >= group.max_instances ||
                      !isActive ||
                      isBusy
                    }
                    onClick={() =>
                      onScale(group.id, group.desired_count + 1)
                    }
                  >
                    {isScaling ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Plus className="h-3.5 w-3.5" />
                    )}
                    <span className="sr-only">Scale up by 1</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Scale up by 1</TooltipContent>
              </Tooltip>

              {/* Scale to specific count */}
              <Button
                variant="outline"
                size="sm"
                className="h-8 text-xs"
                disabled={!isActive || isBusy}
                onClick={() => setScaleDialogOpen(true)}
              >
                Scale
              </Button>

              {/* Pause / Resume toggle */}
              <div className="ml-auto">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant={isPaused ? 'default' : 'outline'}
                      size="icon"
                      className="h-8 w-8"
                      disabled={isBusy || (!isActive && !isPaused)}
                      onClick={() =>
                        isPaused
                          ? onResume(group.id)
                          : onPause(group.id)
                      }
                    >
                      {isPausing || isResuming ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : isPaused ? (
                        <Play className="h-3.5 w-3.5" />
                      ) : (
                        <Pause className="h-3.5 w-3.5" />
                      )}
                      <span className="sr-only">
                        {isPaused ? 'Resume' : 'Pause'}
                      </span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    {isPaused ? 'Resume scaling' : 'Pause scaling'}
                  </TooltipContent>
                </Tooltip>
              </div>
            </TooltipProvider>
          </div>
        </CardContent>
      </Card>

      {/* Scale dialog */}
      <ScaleDialog
        open={scaleDialogOpen}
        onOpenChange={setScaleDialogOpen}
        groupName={group.name}
        currentCount={group.current_count}
        minInstances={group.min_instances}
        maxInstances={group.max_instances}
        onConfirm={(desired) => {
          onScale(group.id, desired);
          setScaleDialogOpen(false);
        }}
        isLoading={isScaling}
      />
    </>
  );
}
