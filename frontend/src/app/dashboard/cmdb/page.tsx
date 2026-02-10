'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import {
  Database,
  CheckCircle2,
  XCircle,
  ExternalLink,
  RefreshCw,
  ShieldAlert,
  Server,
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
import { RoleGate } from '@/components/auth/role-gate';
import { PageHeader } from '@/components/shared/page-header';
import { CMDBDashboard } from '@/components/cmdb/cmdb-dashboard';
import { useServers } from '@/lib/api/hooks';
import { useCMDBStatus, useSyncServer } from '@/lib/api/cmdb';
import type { ServerResponse } from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Access denied fallback
// ---------------------------------------------------------------------------

function CMDBAccessDenied() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <ShieldAlert className="h-16 w-16 text-muted-foreground" />
      <h2 className="mt-4 text-xl font-semibold">Access Denied</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        You need administrator privileges to access CMDB integration.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual server CMDB row (fetches its own status)
// ---------------------------------------------------------------------------

interface ServerCMDBRowProps {
  server: ServerResponse;
}

function ServerCMDBRow({ server }: ServerCMDBRowProps) {
  const { data: cmdbStatus, isLoading } = useCMDBStatus(server.id);
  const syncMutation = useSyncServer();

  const handleSync = () => {
    syncMutation.mutate(server.id);
  };

  return (
    <TableRow>
      <TableCell>
        <Link
          href={`/dashboard/servers/${server.id}`}
          className="text-sm font-medium font-mono hover:underline text-primary"
        >
          {server.server_name}
        </Link>
      </TableCell>
      <TableCell className="text-sm text-muted-foreground">
        {server.environment}
      </TableCell>
      <TableCell>
        {isLoading ? (
          <Skeleton className="h-5 w-16" />
        ) : cmdbStatus?.synced ? (
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-4 w-4 text-green-600 dark:text-green-400" />
            <span className="text-sm text-green-700 dark:text-green-400">
              Synced
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <XCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
            <span className="text-sm text-red-700 dark:text-red-400">
              Not Synced
            </span>
          </div>
        )}
      </TableCell>
      <TableCell className="text-sm font-mono">
        {isLoading ? (
          <Skeleton className="h-5 w-24" />
        ) : (
          cmdbStatus?.ci_number ?? (
            <span className="text-muted-foreground">--</span>
          )
        )}
      </TableCell>
      <TableCell className="text-sm">
        {isLoading ? (
          <Skeleton className="h-5 w-32" />
        ) : cmdbStatus?.last_sync ? (
          new Date(cmdbStatus.last_sync).toLocaleString()
        ) : (
          <span className="text-muted-foreground">Never</span>
        )}
      </TableCell>
      <TableCell>
        {isLoading ? (
          <Skeleton className="h-5 w-20" />
        ) : cmdbStatus?.operational_status ? (
          <Badge variant="secondary">{cmdbStatus.operational_status}</Badge>
        ) : (
          <span className="text-sm text-muted-foreground">--</span>
        )}
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-2">
          {cmdbStatus?.servicenow_url && (
            <a
              href={cmdbStatus.servicenow_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
            >
              <ExternalLink className="h-3.5 w-3.5" />
            </a>
          )}
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1.5 text-xs"
            onClick={handleSync}
            disabled={syncMutation.isPending}
          >
            <RefreshCw
              className={`h-3 w-3 ${syncMutation.isPending ? 'animate-spin' : ''}`}
            />
            Sync
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

// ---------------------------------------------------------------------------
// Loading rows
// ---------------------------------------------------------------------------

function ServerTableSkeleton() {
  return (
    <>
      {Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i}>
          <TableCell>
            <Skeleton className="h-5 w-32" />
          </TableCell>
          <TableCell>
            <Skeleton className="h-5 w-20" />
          </TableCell>
          <TableCell>
            <Skeleton className="h-5 w-16" />
          </TableCell>
          <TableCell>
            <Skeleton className="h-5 w-24" />
          </TableCell>
          <TableCell>
            <Skeleton className="h-5 w-32" />
          </TableCell>
          <TableCell>
            <Skeleton className="h-5 w-20" />
          </TableCell>
          <TableCell>
            <Skeleton className="h-5 w-16" />
          </TableCell>
        </TableRow>
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CMDBPage() {
  const {
    data: serversData,
    isLoading: serversLoading,
    isError: serversError,
  } = useServers({ page_size: 100 });

  // Filter to only show servers that are ready or in a buildable state.
  const servers = useMemo(() => {
    if (!serversData?.servers) return [];
    return serversData.servers.filter(
      (s) => s.status !== 'decommissioned',
    );
  }, [serversData]);

  return (
    <RoleGate permission="admin:access" fallback={<CMDBAccessDenied />}>
      <div className="space-y-6">
        <PageHeader
          title="CMDB Integration"
          description="ServiceNow CMDB sync status and management"
        />

        {/* Dashboard stats and controls */}
        <CMDBDashboard />

        {/* Server sync status table */}
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4" />
              Server CMDB Status
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            {serversError ? (
              <div className="flex flex-col items-center gap-4 py-12">
                <Database className="h-12 w-12 text-muted-foreground" />
                <div className="text-center">
                  <p className="font-medium">Unable to load servers</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Failed to fetch server list. Check your connection and try
                    again.
                  </p>
                </div>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Server Name</TableHead>
                    <TableHead>Environment</TableHead>
                    <TableHead>CMDB Status</TableHead>
                    <TableHead>CI Number</TableHead>
                    <TableHead>Last Sync</TableHead>
                    <TableHead>Operational Status</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {serversLoading ? (
                    <ServerTableSkeleton />
                  ) : servers.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={7}
                        className="text-center py-8 text-muted-foreground"
                      >
                        No servers found. Provision a server to see its CMDB
                        status here.
                      </TableCell>
                    </TableRow>
                  ) : (
                    servers.map((server) => (
                      <ServerCMDBRow key={server.id} server={server} />
                    ))
                  )}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </RoleGate>
  );
}
