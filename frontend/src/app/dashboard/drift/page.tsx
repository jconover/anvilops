'use client';

import { useState, useEffect } from 'react';
import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  Download,
  Radar,
  RefreshCw,
  Server,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useDriftSummary,
  useDriftEvents,
  useDriftAlerts,
  useAcknowledgeAlert,
  useDriftTrends,
} from '@/lib/api/drift';
import type { DriftEventsParams } from '@/lib/api/drift';
import { DriftSummaryCards } from '@/components/drift/drift-summary-cards';
import { DriftTrendChart } from '@/components/drift/drift-trend-chart';
import { DriftAlertsPanel } from '@/components/drift/drift-alerts-panel';
import { DriftEventsTable } from '@/components/drift/drift-events-table';

// ---------------------------------------------------------------------------
// Trend direction icon helper
// ---------------------------------------------------------------------------

function TrendDirectionIcon({ direction }: { direction: 'up' | 'down' | 'stable' }) {
  switch (direction) {
    case 'up':
      return <ArrowUp className="h-5 w-5 text-red-500" />;
    case 'down':
      return <ArrowDown className="h-5 w-5 text-green-500" />;
    case 'stable':
      return <ArrowRight className="h-5 w-5 text-muted-foreground" />;
  }
}

// ---------------------------------------------------------------------------
// Main dashboard page
// ---------------------------------------------------------------------------

export default function DriftDetectionPage() {
  const [eventsParams, setEventsParams] = useState<DriftEventsParams>({
    page: 1,
    page_size: 20,
  });

  // Data hooks
  const {
    data: summary,
    isLoading: summaryLoading,
    isError: summaryError,
    refetch: refetchSummary,
    dataUpdatedAt: summaryUpdatedAt,
  } = useDriftSummary();

  const {
    data: eventsData,
    isLoading: eventsLoading,
    refetch: refetchEvents,
  } = useDriftEvents(eventsParams);

  const {
    data: alerts,
    isLoading: alertsLoading,
    refetch: refetchAlerts,
  } = useDriftAlerts();

  const {
    data: trends,
    isLoading: trendsLoading,
    refetch: refetchTrends,
  } = useDriftTrends();

  const acknowledgeAlert = useAcknowledgeAlert();

  // Auto-refresh all data every 60 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetchSummary();
      refetchEvents();
      refetchAlerts();
      refetchTrends();
    }, 60_000);
    return () => clearInterval(interval);
  }, [refetchSummary, refetchEvents, refetchAlerts, refetchTrends]);

  function handleRefreshAll() {
    refetchSummary();
    refetchEvents();
    refetchAlerts();
    refetchTrends();
  }

  function handleAcknowledge(alertId: string) {
    acknowledgeAlert.mutate(alertId);
  }

  function handleDownloadReport() {
    const report = {
      generated_at: new Date().toISOString(),
      summary,
      alerts: alerts || [],
      trends: trends || null,
    };
    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `drift-report-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  const isFullyLoading = summaryLoading && alertsLoading && trendsLoading;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2">
            <Radar className="h-6 w-6 text-primary" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">
                Drift Detection
              </h1>
              {summary && (
                <TrendDirectionIcon direction={summary.trend_direction} />
              )}
            </div>
            <p className="text-sm text-muted-foreground">
              Real-time infrastructure drift monitoring and alerting
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {summaryUpdatedAt > 0 && (
            <span className="text-xs text-muted-foreground">
              Updated {new Date(summaryUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          {/* Live indicator */}
          <div className="flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-green-500" />
            </span>
            <span className="text-[11px] font-medium text-muted-foreground">
              Live
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefreshAll}
            className="gap-2"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={handleDownloadReport}
            disabled={!summary}
            className="gap-2"
          >
            <Download className="h-3.5 w-3.5" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Loading State */}
      {isFullyLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <Skeleton className="h-8" />
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Skeleton className="h-64 lg:col-span-2" />
            <Skeleton className="h-64" />
          </div>
          <Skeleton className="h-96" />
        </div>
      )}

      {/* Error State */}
      {summaryError && !summaryLoading && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <Radar className="h-12 w-12 text-muted-foreground" />
            <div className="text-center">
              <p className="font-medium">Unable to load drift detection data</p>
              <p className="mt-1 text-sm text-muted-foreground">
                The drift detection API may be unavailable. Check your
                connection and try again.
              </p>
            </div>
            <Button variant="outline" onClick={handleRefreshAll}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Data Loaded */}
      {summary && !summaryLoading && (
        <>
          {/* Summary Cards */}
          <DriftSummaryCards summary={summary} />

          {/* Trend Chart + Alerts panel */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              {trendsLoading ? (
                <Skeleton className="h-72" />
              ) : trends ? (
                <DriftTrendChart data={trends.events_per_day} />
              ) : null}
            </div>
            <div className="lg:col-span-1">
              {alertsLoading ? (
                <Skeleton className="h-72" />
              ) : (
                <DriftAlertsPanel
                  alerts={alerts || []}
                  onAcknowledge={handleAcknowledge}
                  isAcknowledging={acknowledgeAlert.isPending}
                />
              )}
            </div>
          </div>

          {/* Top drifting resources and servers */}
          {trends && (
            <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
              {/* Top Resources */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Activity className="h-4 w-4" />
                    Top Drifting Resources
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {trends.top_resources.length === 0 ? (
                    <p className="py-4 text-center text-sm text-muted-foreground">
                      No resource drift data available
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {trends.top_resources.slice(0, 8).map((resource, idx) => {
                        const maxCount = trends.top_resources[0]?.count || 1;
                        const width = (resource.count / maxCount) * 100;
                        return (
                          <div key={resource.resource} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="truncate font-mono font-medium">
                                {resource.resource}
                              </span>
                              <span className="shrink-0 tabular-nums text-muted-foreground">
                                {resource.count}
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-primary/70 transition-all duration-500"
                                style={{ width: `${width}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Top Servers */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Server className="h-4 w-4" />
                    Top Drifting Servers
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {trends.top_servers.length === 0 ? (
                    <p className="py-4 text-center text-sm text-muted-foreground">
                      No server drift data available
                    </p>
                  ) : (
                    <div className="space-y-3">
                      {trends.top_servers.slice(0, 8).map((server, idx) => {
                        const maxCount = trends.top_servers[0]?.count || 1;
                        const width = (server.count / maxCount) * 100;
                        return (
                          <div key={server.server_name} className="space-y-1">
                            <div className="flex items-center justify-between text-xs">
                              <span className="truncate font-medium">
                                {server.server_name}
                              </span>
                              <span className="shrink-0 tabular-nums text-muted-foreground">
                                {server.count}
                              </span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-muted">
                              <div
                                className="h-full rounded-full bg-orange-500/70 transition-all duration-500"
                                style={{ width: `${width}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          )}

          {/* Events Table */}
          <DriftEventsTable
            events={eventsData?.events || []}
            total={eventsData?.total || 0}
            isLoading={eventsLoading}
            params={eventsParams}
            onParamsChange={setEventsParams}
          />
        </>
      )}
    </div>
  );
}
