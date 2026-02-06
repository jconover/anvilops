'use client';

import { useState } from 'react';
import {
  ArrowRight,
  Clock,
  RotateCcw,
  ShieldCheck,
  FileWarning,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useNodeDrift } from '@/lib/api/hooks';

interface DriftReportProps {
  serverId: string | undefined;
  certname: string;
}

const TIME_RANGES = [
  { label: '24h', hours: 24 },
  { label: '48h', hours: 48 },
  { label: '7d', hours: 168 },
  { label: '30d', hours: 720 },
] as const;

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function truncateValue(value: string, maxLength: number = 60): string {
  if (value.length <= maxLength) return value;
  return value.slice(0, maxLength) + '...';
}

export function DriftReport({ serverId, certname }: DriftReportProps) {
  const [hours, setHours] = useState<number>(24);
  const { data, isLoading, isError } = useNodeDrift(serverId, hours);

  return (
    <Card className="border-0 shadow-none">
      <CardHeader className="px-0 pt-0">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            Drift Report: {certname}
          </CardTitle>
          <div className="flex items-center gap-1">
            {TIME_RANGES.map((range) => (
              <Button
                key={range.hours}
                variant={hours === range.hours ? 'default' : 'outline'}
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  setHours(range.hours);
                }}
                className="h-7 px-2.5 text-xs"
              >
                {range.label}
              </Button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {isError && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
            <FileWarning className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Failed to load drift data for this node.
            </p>
          </div>
        )}

        {!isLoading && !isError && data && data.drift_events.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
            <ShieldCheck className="h-8 w-8 text-green-500" />
            <p className="text-sm font-medium text-green-700 dark:text-green-400">
              No drift events in the last{' '}
              {hours >= 168
                ? `${Math.round(hours / 24)} days`
                : `${hours} hours`}
            </p>
            <p className="text-xs text-muted-foreground">
              This node is maintaining its desired state.
            </p>
          </div>
        )}

        {!isLoading && !isError && data && data.drift_events.length > 0 && (
          <div className="space-y-2">
            <div className="mb-3 flex items-center gap-2 text-xs text-muted-foreground">
              <Clock className="h-3.5 w-3.5" />
              <span>
                {data.total_events} event{data.total_events !== 1 ? 's' : ''} in
                the last{' '}
                {hours >= 168
                  ? `${Math.round(hours / 24)} days`
                  : `${hours} hours`}
              </span>
            </div>
            {data.drift_events.map((event, index) => (
              <div
                key={`${event.resource_type}-${event.resource_title}-${event.timestamp}-${index}`}
                className="rounded-lg border bg-card p-3"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {event.resource_type}[{event.resource_title}]
                      </span>
                      {event.corrective_change && (
                        <Badge variant="info" className="gap-1">
                          <RotateCcw className="h-3 w-3" />
                          Auto-corrected
                        </Badge>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Property: <span className="font-mono">{event.property}</span>
                    </p>
                    <div className="mt-2 flex items-center gap-2 text-xs">
                      <code className="rounded bg-red-50 px-1.5 py-0.5 text-red-700 dark:bg-red-950 dark:text-red-300">
                        {truncateValue(event.old_value)}
                      </code>
                      <ArrowRight className="h-3 w-3 shrink-0 text-muted-foreground" />
                      <code className="rounded bg-green-50 px-1.5 py-0.5 text-green-700 dark:bg-green-950 dark:text-green-300">
                        {truncateValue(event.new_value)}
                      </code>
                    </div>
                  </div>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatTimestamp(event.timestamp)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
