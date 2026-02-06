'use client';

import { useState, useMemo, useEffect, useCallback } from 'react';
import {
  FileText,
  Download,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Activity,
  TrendingUp,
  Users,
  Calendar,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { RoleGate } from '@/components/auth/role-gate';
import { AuditTable } from '@/components/audit/audit-table';
import {
  AuditFilters,
  DEFAULT_FILTERS,
  type AuditFilterState,
} from '@/components/audit/audit-filters';
import {
  useAuditLogs,
  useAuditSummary,
  type AuditQueryParams,
} from '@/lib/api/audit';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 25;

// ---------------------------------------------------------------------------
// Date helpers
// ---------------------------------------------------------------------------

function getDateRangeBounds(
  range: AuditFilterState['dateRange'],
  startDate: string,
  endDate: string,
): { start_date?: string; end_date?: string } {
  const now = new Date();
  switch (range) {
    case '24h': {
      const d = new Date(now);
      d.setHours(d.getHours() - 24);
      return { start_date: d.toISOString() };
    }
    case '7d': {
      const d = new Date(now);
      d.setDate(d.getDate() - 7);
      return { start_date: d.toISOString() };
    }
    case '30d': {
      const d = new Date(now);
      d.setDate(d.getDate() - 30);
      return { start_date: d.toISOString() };
    }
    case 'custom': {
      const result: { start_date?: string; end_date?: string } = {};
      if (startDate) result.start_date = new Date(startDate).toISOString();
      if (endDate) {
        const end = new Date(endDate);
        end.setHours(23, 59, 59, 999);
        result.end_date = end.toISOString();
      }
      return result;
    }
    case 'all':
    default:
      return {};
  }
}

// ---------------------------------------------------------------------------
// Access denied fallback
// ---------------------------------------------------------------------------

function AuditAccessDenied() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <ShieldAlert className="h-16 w-16 text-muted-foreground" />
      <h2 className="mt-4 text-xl font-semibold">Access Denied</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        You need administrator privileges to access the audit log.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AuditLogPage() {
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<AuditFilterState>(DEFAULT_FILTERS);
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Build API query params from filter state
  const queryParams: AuditQueryParams = useMemo(() => {
    const dateBounds = getDateRangeBounds(
      filters.dateRange,
      filters.startDate,
      filters.endDate,
    );
    const params: AuditQueryParams = {
      page,
      page_size: PAGE_SIZE,
      ...dateBounds,
    };
    if (filters.action) params.action = filters.action;
    if (filters.category) params.category = filters.category;
    if (filters.actorEmail) params.actor_email = filters.actorEmail;
    if (filters.status) params.status = filters.status;
    return params;
  }, [page, filters]);

  const {
    data: logsData,
    isLoading: logsLoading,
    isError: logsError,
    refetch: refetchLogs,
    dataUpdatedAt,
  } = useAuditLogs(queryParams, {
    refetchInterval: autoRefresh ? 10_000 : false,
  });

  const {
    data: summary,
    isLoading: summaryLoading,
  } = useAuditSummary();

  // Reset to page 1 when filters change
  const handleFiltersChange = useCallback((newFilters: AuditFilterState) => {
    setFilters(newFilters);
    setPage(1);
  }, []);

  // Pagination calculations
  const totalItems = logsData?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
  const startItem = totalItems > 0 ? (page - 1) * PAGE_SIZE + 1 : 0;
  const endItem = Math.min(page * PAGE_SIZE, totalItems);

  // Summary stats
  const todayStr = new Date().toISOString().slice(0, 10);
  const eventsToday = useMemo(() => {
    return (
      summary?.events_per_day.find((d) => d.date === todayStr)?.count ?? 0
    );
  }, [summary, todayStr]);

  const topAction = summary?.top_actions[0];
  const topActor = summary?.top_actors[0];

  return (
    <RoleGate permission="admin:access" fallback={<AuditAccessDenied />}>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-primary/10 p-2">
              <FileText className="h-6 w-6 text-primary" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Audit Log</h1>
              <p className="text-sm text-muted-foreground">
                Searchable record of all platform activity for compliance and
                troubleshooting
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Auto-refresh toggle */}
            <div className="flex items-center gap-2">
              <Switch
                id="auto-refresh"
                checked={autoRefresh}
                onCheckedChange={setAutoRefresh}
              />
              <Label htmlFor="auto-refresh" className="text-xs text-muted-foreground">
                Auto-refresh
              </Label>
            </div>

            {/* Last updated */}
            {dataUpdatedAt > 0 && (
              <span className="text-xs text-muted-foreground">
                Updated {new Date(dataUpdatedAt).toLocaleTimeString()}
              </span>
            )}

            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchLogs()}
              className="gap-2"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
            <Button variant="outline" size="sm" className="gap-2">
              <Download className="h-3.5 w-3.5" />
              Export
            </Button>
          </div>
        </div>

        {/* Summary Stats Row */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {summaryLoading ? (
            <>
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-[88px]" />
              ))}
            </>
          ) : (
            <>
              <Card>
                <CardContent className="flex items-center gap-4 p-4">
                  <div className="rounded-lg bg-blue-100 p-2.5 dark:bg-blue-900/30">
                    <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">
                      Total Events (30d)
                    </p>
                    <p className="text-2xl font-bold">
                      {summary?.total_events?.toLocaleString() ?? '--'}
                    </p>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 p-4">
                  <div className="rounded-lg bg-green-100 p-2.5 dark:bg-green-900/30">
                    <TrendingUp className="h-5 w-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">
                      Top Action
                    </p>
                    <p className="text-lg font-bold">
                      {topAction
                        ? topAction.action
                            .split('.')
                            .map(
                              (p) => p.charAt(0).toUpperCase() + p.slice(1),
                            )
                            .join(' ')
                        : '--'}
                    </p>
                    {topAction && (
                      <p className="text-xs text-muted-foreground">
                        {topAction.count.toLocaleString()} occurrences
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 p-4">
                  <div className="rounded-lg bg-purple-100 p-2.5 dark:bg-purple-900/30">
                    <Users className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">
                      Top Actor
                    </p>
                    <p className="max-w-[180px] truncate text-lg font-bold">
                      {topActor?.email ?? '--'}
                    </p>
                    {topActor && (
                      <p className="text-xs text-muted-foreground">
                        {topActor.count.toLocaleString()} events
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="flex items-center gap-4 p-4">
                  <div className="rounded-lg bg-amber-100 p-2.5 dark:bg-amber-900/30">
                    <Calendar className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-muted-foreground">
                      Events Today
                    </p>
                    <p className="text-2xl font-bold">
                      {eventsToday.toLocaleString()}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </>
          )}
        </div>

        {/* Filters */}
        <Card>
          <CardContent className="p-4">
            <AuditFilters
              filters={filters}
              onFiltersChange={handleFiltersChange}
            />
          </CardContent>
        </Card>

        {/* Error State */}
        {logsError && !logsLoading && (
          <Card>
            <CardContent className="flex flex-col items-center gap-4 py-12">
              <FileText className="h-12 w-12 text-muted-foreground" />
              <div className="text-center">
                <p className="font-medium">Unable to load audit logs</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  The audit API may be unavailable. Check your connection and try
                  again.
                </p>
              </div>
              <Button variant="outline" onClick={() => refetchLogs()}>
                Try Again
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Audit Table */}
        {!logsError && (
          <Card>
            <CardContent className="p-0">
              <AuditTable
                logs={logsData?.logs ?? []}
                isLoading={logsLoading}
              />
            </CardContent>
          </Card>
        )}

        {/* Pagination */}
        {totalItems > 0 && !logsError && (
          <div className="flex items-center justify-between px-2">
            <p className="text-sm text-muted-foreground">
              Showing {startItem}&ndash;{endItem} of{' '}
              {totalItems.toLocaleString()} entries
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Previous
              </Button>
              <span className="min-w-[80px] text-center text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          </div>
        )}
      </div>
    </RoleGate>
  );
}
