'use client';

import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Bell,
  ShieldAlert,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import type { DriftSummary } from '@/lib/api/drift';

// ---------------------------------------------------------------------------
// Severity color map
// ---------------------------------------------------------------------------

const SEVERITY_COLORS: Record<string, { bg: string; text: string; bar: string }> = {
  critical: {
    bg: 'bg-red-50 dark:bg-red-950/40',
    text: 'text-red-700 dark:text-red-400',
    bar: 'bg-red-500',
  },
  high: {
    bg: 'bg-orange-50 dark:bg-orange-950/40',
    text: 'text-orange-700 dark:text-orange-400',
    bar: 'bg-orange-500',
  },
  medium: {
    bg: 'bg-yellow-50 dark:bg-yellow-950/40',
    text: 'text-yellow-700 dark:text-yellow-400',
    bar: 'bg-yellow-500',
  },
  low: {
    bg: 'bg-slate-50 dark:bg-slate-900/40',
    text: 'text-slate-600 dark:text-slate-400',
    bar: 'bg-slate-400',
  },
};

const CATEGORY_COLORS: Record<string, string> = {
  security: 'bg-red-500',
  configuration: 'bg-blue-500',
  package: 'bg-purple-500',
  service: 'bg-emerald-500',
  file: 'bg-amber-500',
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DriftSummaryCardsProps {
  summary: DriftSummary;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DriftSummaryCards({ summary }: DriftSummaryCardsProps) {
  const totalCategory = Object.values(summary.by_category).reduce(
    (sum, val) => sum + val,
    0,
  );

  return (
    <div className="space-y-4">
      {/* Primary metrics row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
        {/* Total Events */}
        <Card className="relative overflow-hidden">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Total Events
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums">
                  {summary.total_events.toLocaleString()}
                </p>
              </div>
              <div className="flex flex-col items-center gap-1">
                <Activity className="h-5 w-5 text-muted-foreground" />
                <TrendIndicator direction={summary.trend_direction} />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Critical */}
        <Card className={`relative overflow-hidden border-red-200 dark:border-red-900/50 ${summary.by_severity.critical > 0 ? 'ring-1 ring-red-300 dark:ring-red-800' : ''}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-red-600 dark:text-red-400">
                  Critical
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-red-700 dark:text-red-400">
                  {summary.by_severity.critical}
                </p>
              </div>
              <ShieldAlert className="h-5 w-5 text-red-500" />
            </div>
            {summary.by_severity.critical > 0 && (
              <div className="absolute inset-x-0 bottom-0 h-1 bg-red-500" />
            )}
          </CardContent>
        </Card>

        {/* High */}
        <Card className="relative overflow-hidden border-orange-200 dark:border-orange-900/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-orange-600 dark:text-orange-400">
                  High
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-orange-700 dark:text-orange-400">
                  {summary.by_severity.high}
                </p>
              </div>
              <AlertTriangle className="h-5 w-5 text-orange-500" />
            </div>
            {summary.by_severity.high > 0 && (
              <div className="absolute inset-x-0 bottom-0 h-1 bg-orange-500" />
            )}
          </CardContent>
        </Card>

        {/* Medium */}
        <Card className="relative overflow-hidden border-yellow-200 dark:border-yellow-900/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-yellow-600 dark:text-yellow-400">
                  Medium
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums text-yellow-700 dark:text-yellow-400">
                  {summary.by_severity.medium}
                </p>
              </div>
              <div className="rounded-full bg-yellow-100 p-1 dark:bg-yellow-900/40">
                <div className="h-3 w-3 rounded-full bg-yellow-500" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Low */}
        <Card className="relative overflow-hidden">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Low
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums">
                  {summary.by_severity.low}
                </p>
              </div>
              <div className="rounded-full bg-slate-100 p-1 dark:bg-slate-800">
                <div className="h-3 w-3 rounded-full bg-slate-400" />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Active Alerts */}
        <Card className={`relative overflow-hidden ${summary.active_alerts > 0 ? 'border-red-200 dark:border-red-900/50' : ''}`}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  Active Alerts
                </p>
                <p className="mt-1 text-2xl font-bold tabular-nums">
                  {summary.active_alerts}
                </p>
              </div>
              <div className="relative">
                <Bell className={`h-5 w-5 ${summary.active_alerts > 0 ? 'text-red-500' : 'text-muted-foreground'}`} />
                {summary.active_alerts > 0 && (
                  <span className="absolute -right-1 -top-1 flex h-3 w-3">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
                    <span className="relative inline-flex h-3 w-3 rounded-full bg-red-500" />
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Category breakdown bar */}
      <Card>
        <CardContent className="p-4">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Events by Category
          </p>
          {totalCategory > 0 ? (
            <div className="space-y-2">
              {/* Stacked bar */}
              <div className="flex h-3 overflow-hidden rounded-full bg-muted">
                {Object.entries(summary.by_category).map(([category, count]) => {
                  if (count === 0) return null;
                  const width = (count / totalCategory) * 100;
                  return (
                    <div
                      key={category}
                      className={`${CATEGORY_COLORS[category] || 'bg-gray-400'} transition-all duration-300`}
                      style={{ width: `${width}%` }}
                      title={`${category}: ${count}`}
                    />
                  );
                })}
              </div>
              {/* Legend */}
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {Object.entries(summary.by_category).map(([category, count]) => (
                  <div key={category} className="flex items-center gap-1.5">
                    <div
                      className={`h-2.5 w-2.5 rounded-full ${CATEGORY_COLORS[category] || 'bg-gray-400'}`}
                    />
                    <span className="text-xs text-muted-foreground">
                      <span className="capitalize">{category}</span>
                      <span className="ml-1 font-medium text-foreground">{count}</span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">No drift events detected</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Trend indicator sub-component
// ---------------------------------------------------------------------------

function TrendIndicator({ direction }: { direction: 'up' | 'down' | 'stable' }) {
  switch (direction) {
    case 'up':
      return (
        <div className="flex items-center gap-0.5 text-red-600 dark:text-red-400">
          <ArrowUp className="h-3.5 w-3.5" />
          <span className="text-[10px] font-semibold uppercase">Up</span>
        </div>
      );
    case 'down':
      return (
        <div className="flex items-center gap-0.5 text-green-600 dark:text-green-400">
          <ArrowDown className="h-3.5 w-3.5" />
          <span className="text-[10px] font-semibold uppercase">Down</span>
        </div>
      );
    case 'stable':
      return (
        <div className="flex items-center gap-0.5 text-muted-foreground">
          <ArrowRight className="h-3.5 w-3.5" />
          <span className="text-[10px] font-semibold uppercase">Stable</span>
        </div>
      );
  }
}
