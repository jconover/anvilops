'use client';

import { useState } from 'react';
import {
  Database,
  Server,
  CheckCircle2,
  Clock,
  RefreshCw,
  TrendingUp,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useCMDBStats, useFullSync } from '@/lib/api/cmdb';

// ---------------------------------------------------------------------------
// Cosmetic sync history data
// ---------------------------------------------------------------------------

interface SyncHistoryEntry {
  id: string;
  timestamp: string;
  type: 'full' | 'incremental' | 'manual';
  synced_count: number;
  failed_count: number;
  duration_seconds: number;
  status: 'success' | 'partial' | 'failed';
}

const MOCK_SYNC_HISTORY: SyncHistoryEntry[] = [
  {
    id: '1',
    timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    type: 'full',
    synced_count: 47,
    failed_count: 0,
    duration_seconds: 34,
    status: 'success',
  },
  {
    id: '2',
    timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString(),
    type: 'incremental',
    synced_count: 3,
    failed_count: 0,
    duration_seconds: 4,
    status: 'success',
  },
  {
    id: '3',
    timestamp: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(),
    type: 'full',
    synced_count: 45,
    failed_count: 2,
    duration_seconds: 41,
    status: 'partial',
  },
  {
    id: '4',
    timestamp: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
    type: 'manual',
    synced_count: 1,
    failed_count: 0,
    duration_seconds: 2,
    status: 'success',
  },
  {
    id: '5',
    timestamp: new Date(Date.now() - 72 * 60 * 60 * 1000).toISOString(),
    type: 'full',
    synced_count: 44,
    failed_count: 0,
    duration_seconds: 29,
    status: 'success',
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SYNC_TYPE_LABELS: Record<SyncHistoryEntry['type'], string> = {
  full: 'Full Reconciliation',
  incremental: 'Incremental',
  manual: 'Manual',
};

function getSyncStatusBadge(status: SyncHistoryEntry['status']) {
  switch (status) {
    case 'success':
      return <Badge variant="default">Success</Badge>;
    case 'partial':
      return <Badge variant="secondary">Partial</Badge>;
    case 'failed':
      return <Badge variant="destructive">Failed</Badge>;
    default:
      return <Badge variant="outline">{status}</Badge>;
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}m ${secs}s`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CMDBDashboard() {
  const { data: stats, isLoading: statsLoading, isError: statsError } = useCMDBStats();
  const fullSyncMutation = useFullSync();
  const [syncTriggered, setSyncTriggered] = useState(false);

  const handleFullSync = () => {
    setSyncTriggered(true);
    fullSyncMutation.mutate(undefined, {
      onSettled: () => {
        setTimeout(() => setSyncTriggered(false), 3000);
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {statsLoading ? (
          <>
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-[88px]" />
            ))}
          </>
        ) : statsError ? (
          <Card className="col-span-full">
            <CardContent className="flex items-center gap-3 p-4">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <p className="text-sm">
                Unable to load CMDB statistics. The integration may be
                unavailable.
              </p>
            </CardContent>
          </Card>
        ) : (
          <>
            {/* Total Synced */}
            <Card>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="rounded-lg bg-green-100 p-2.5 dark:bg-green-900/30">
                  <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    Total Synced
                  </p>
                  <p className="text-2xl font-bold">
                    {stats?.total_synced?.toLocaleString() ?? '--'}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Total Servers */}
            <Card>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="rounded-lg bg-blue-100 p-2.5 dark:bg-blue-900/30">
                  <Server className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    Total Servers
                  </p>
                  <p className="text-2xl font-bold">
                    {stats?.total_servers?.toLocaleString() ?? '--'}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Sync Rate */}
            <Card>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="rounded-lg bg-purple-100 p-2.5 dark:bg-purple-900/30">
                  <TrendingUp className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    Sync Rate
                  </p>
                  <p className="text-2xl font-bold">
                    {stats?.sync_rate != null
                      ? `${Math.round(stats.sync_rate)}%`
                      : '--'}
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Pending Syncs */}
            <Card>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="rounded-lg bg-amber-100 p-2.5 dark:bg-amber-900/30">
                  <Clock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    Pending Syncs
                  </p>
                  <p className="text-2xl font-bold">
                    {stats?.pending_syncs?.toLocaleString() ?? '--'}
                  </p>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>

      {/* Last full sync + action row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="text-sm text-muted-foreground">
          {stats?.last_full_sync ? (
            <>
              Last full sync:{' '}
              <span className="font-medium text-foreground">
                {new Date(stats.last_full_sync).toLocaleString()}
              </span>
            </>
          ) : (
            'No full sync has been run yet.'
          )}
        </div>
        <Button
          className="gap-2"
          onClick={handleFullSync}
          disabled={fullSyncMutation.isPending}
        >
          <RefreshCw
            className={`h-4 w-4 ${fullSyncMutation.isPending ? 'animate-spin' : ''}`}
          />
          {fullSyncMutation.isPending
            ? 'Running Full Sync...'
            : syncTriggered && fullSyncMutation.isSuccess
              ? 'Sync Complete!'
              : 'Run Full Sync'}
        </Button>
      </div>

      {fullSyncMutation.isError && (
        <div className="flex items-center gap-2 rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Full sync failed. Please check your ServiceNow integration settings
          and try again.
        </div>
      )}

      {fullSyncMutation.isSuccess && syncTriggered && (
        <div className="flex items-center gap-2 rounded-md bg-green-50 px-4 py-3 text-sm text-green-700 dark:bg-green-900/20 dark:text-green-400">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          Full reconciliation completed successfully.
        </div>
      )}

      {/* Sync History Table */}
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4" />
            Sync History
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Synced</TableHead>
                <TableHead className="text-right">Failed</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {MOCK_SYNC_HISTORY.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="text-sm">
                    {new Date(entry.timestamp).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-sm">
                    {SYNC_TYPE_LABELS[entry.type]}
                  </TableCell>
                  <TableCell className="text-right text-sm font-mono">
                    {entry.synced_count}
                  </TableCell>
                  <TableCell className="text-right text-sm font-mono">
                    {entry.failed_count > 0 ? (
                      <span className="text-destructive">
                        {entry.failed_count}
                      </span>
                    ) : (
                      entry.failed_count
                    )}
                  </TableCell>
                  <TableCell className="text-right text-sm font-mono">
                    {formatDuration(entry.duration_seconds)}
                  </TableCell>
                  <TableCell>{getSyncStatusBadge(entry.status)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
