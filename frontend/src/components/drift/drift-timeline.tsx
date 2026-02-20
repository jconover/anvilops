'use client';

import { useState } from 'react';
import {
  ArrowRight,
  Clock,
  FileWarning,
  RotateCcw,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useDriftTimeline, type DriftTimelineEvent } from '@/lib/api/drift';

// ---------------------------------------------------------------------------
// Severity dot colors
// ---------------------------------------------------------------------------

const SEVERITY_DOT: Record<string, { ring: string; fill: string }> = {
  critical: {
    ring: 'ring-red-200 dark:ring-red-800',
    fill: 'bg-red-500',
  },
  high: {
    ring: 'ring-orange-200 dark:ring-orange-800',
    fill: 'bg-orange-500',
  },
  medium: {
    ring: 'ring-yellow-200 dark:ring-yellow-800',
    fill: 'bg-yellow-500',
  },
  low: {
    ring: 'ring-slate-200 dark:ring-slate-700',
    fill: 'bg-slate-400',
  },
};

function getSeverityDot(severity: string) {
  return SEVERITY_DOT[severity.toLowerCase()] || SEVERITY_DOT.low;
}

// ---------------------------------------------------------------------------
// Time range options
// ---------------------------------------------------------------------------

const TIME_RANGES = [
  { label: '24h', hours: 24 },
  { label: '48h', hours: 48 },
  { label: '7d', hours: 168 },
  { label: '30d', hours: 720 },
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatDate(ts: string): string {
  return new Date(ts).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

function truncateValue(value: string | null, maxLength: number = 60): string {
  if (!value) return '(none)';
  if (value.length <= maxLength) return value;
  return value.slice(0, maxLength) + '...';
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DriftTimelineProps {
  serverId: string | undefined;
  /** Optional label for the server (e.g. certname) */
  serverLabel?: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DriftTimeline({ serverId, serverLabel }: DriftTimelineProps) {
  const [hours, setHours] = useState<number>(24);
  const { data, isLoading, isError } = useDriftTimeline(serverId, hours);

  // Group events by date
  function groupByDate(
    events: DriftTimelineEvent[],
  ): Map<string, DriftTimelineEvent[]> {
    const groups = new Map<string, DriftTimelineEvent[]>();
    for (const event of events) {
      const dateKey = formatDate(event.detected_at);
      const existing = groups.get(dateKey) || [];
      existing.push(event);
      groups.set(dateKey, existing);
    }
    return groups;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base">
            <Clock className="h-4 w-4" />
            Drift Timeline
            {serverLabel && (
              <span className="text-sm font-normal text-muted-foreground">
                - {serverLabel}
              </span>
            )}
          </CardTitle>
          <div className="flex items-center gap-1">
            {TIME_RANGES.map((range) => (
              <Button
                key={range.hours}
                variant={hours === range.hours ? 'default' : 'outline'}
                size="sm"
                onClick={() => setHours(range.hours)}
                className="h-7 px-2.5 text-xs"
              >
                {range.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Loading state */}
        {isLoading && (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="flex gap-3">
                <Skeleton className="h-4 w-4 shrink-0 rounded-full" />
                <div className="flex-1 space-y-1">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Error state */}
        {isError && !isLoading && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
            <FileWarning className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Failed to load drift timeline for this server.
            </p>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && !isError && data && data.events.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
            <ShieldCheck className="h-8 w-8 text-green-500" />
            <p className="text-sm font-medium text-green-700 dark:text-green-400">
              No drift events in the last{' '}
              {hours >= 168
                ? `${Math.round(hours / 24)} days`
                : `${hours} hours`}
            </p>
            <p className="text-xs text-muted-foreground">
              This server is maintaining its desired state.
            </p>
          </div>
        )}

        {/* Timeline */}
        {!isLoading && !isError && data && data.events.length > 0 && (
          <div>
            <p className="mb-4 flex items-center gap-2 text-xs text-muted-foreground">
              <Shield className="h-3.5 w-3.5" />
              {data.total} event{data.total !== 1 ? 's' : ''} detected in the
              last{' '}
              {hours >= 168
                ? `${Math.round(hours / 24)} days`
                : `${hours} hours`}
            </p>

            {/* Grouped by date */}
            {Array.from(groupByDate(data.events)).map(
              ([dateLabel, events]) => (
                <div key={dateLabel} className="mb-6 last:mb-0">
                  {/* Date header */}
                  <div className="mb-3 flex items-center gap-2">
                    <div className="h-px flex-1 bg-border" />
                    <span className="text-xs font-medium text-muted-foreground">
                      {dateLabel}
                    </span>
                    <div className="h-px flex-1 bg-border" />
                  </div>

                  {/* Vertical timeline */}
                  <div className="relative ml-3 border-l-2 border-muted pl-6">
                    {events.map((event, idx) => {
                      const dot = getSeverityDot(event.severity);
                      return (
                        <div
                          key={event.id}
                          className={`relative pb-5 last:pb-0`}
                        >
                          {/* Timeline dot */}
                          <div
                            className={`absolute -left-[31px] top-0.5 flex h-4 w-4 items-center justify-center rounded-full ring-2 ${dot.ring} bg-background`}
                          >
                            <div
                              className={`h-2.5 w-2.5 rounded-full ${dot.fill}`}
                            />
                          </div>

                          {/* Event content */}
                          <div className="rounded-lg border bg-card p-3 transition-colors hover:bg-muted/30">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="text-sm font-medium">
                                    {event.resource_type}[{event.resource_title}]
                                  </span>
                                  <Badge
                                    variant={
                                      event.severity === 'critical'
                                        ? 'destructive'
                                        : event.severity === 'high'
                                          ? 'warning'
                                          : 'secondary'
                                    }
                                    className="text-[10px]"
                                  >
                                    {event.severity}
                                  </Badge>
                                  {event.is_corrective && (
                                    <Badge variant="info" className="gap-1 text-[10px]">
                                      <RotateCcw className="h-2.5 w-2.5" />
                                      Auto-fixed
                                    </Badge>
                                  )}
                                  {event.is_resolved && (
                                    <Badge variant="success" className="text-[10px]">
                                      Resolved
                                    </Badge>
                                  )}
                                </div>
                                <p className="mt-1 text-xs text-muted-foreground">
                                  Property:{' '}
                                  <span className="font-mono">
                                    {event.property_name}
                                  </span>
                                  {event.drift_category && (
                                    <>
                                      {' '}
                                      <span className="capitalize text-muted-foreground">
                                        ({event.drift_category})
                                      </span>
                                    </>
                                  )}
                                  {event.cis_control_id && (
                                    <>
                                      {' '}
                                      <span className="font-mono text-muted-foreground">
                                        [CIS {event.cis_control_id}]
                                      </span>
                                    </>
                                  )}
                                </p>

                                {/* Value diff */}
                                <div className="mt-2 flex items-center gap-2 text-xs">
                                  <code className="max-w-[200px] truncate rounded bg-red-50 px-1.5 py-0.5 text-red-700 dark:bg-red-950/40 dark:text-red-300">
                                    {truncateValue(event.old_value)}
                                  </code>
                                  <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                                  <code className="max-w-[200px] truncate rounded bg-green-50 px-1.5 py-0.5 text-green-700 dark:bg-green-950/40 dark:text-green-300">
                                    {truncateValue(event.new_value)}
                                  </code>
                                </div>
                              </div>
                              <span className="shrink-0 text-xs text-muted-foreground">
                                {formatTimestamp(event.detected_at)}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ),
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
