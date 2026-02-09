'use client';

import { useState } from 'react';
import {
  CheckCircle2,
  XCircle,
  ExternalLink,
  RefreshCw,
  Database,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useCMDBStatus, useSyncServer } from '@/lib/api/cmdb';

// ---------------------------------------------------------------------------
// Operational status badge mapping
// ---------------------------------------------------------------------------

const STATUS_VARIANT: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  operational: 'default',
  'non-operational': 'destructive',
  repair: 'secondary',
  retired: 'outline',
};

function getStatusVariant(status: string | null): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (!status) return 'outline';
  return STATUS_VARIANT[status.toLowerCase()] ?? 'secondary';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface CMDBStatusCardProps {
  serverId: string;
}

export function CMDBStatusCard({ serverId }: CMDBStatusCardProps) {
  const { data: cmdbStatus, isLoading, isError } = useCMDBStatus(serverId);
  const syncMutation = useSyncServer();
  const [syncTriggered, setSyncTriggered] = useState(false);

  const handleSync = () => {
    setSyncTriggered(true);
    syncMutation.mutate(serverId, {
      onSettled: () => {
        // Keep the triggered state for a moment so the user sees feedback.
        setTimeout(() => setSyncTriggered(false), 2000);
      },
    });
  };

  // Loading state
  if (isLoading) {
    return (
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4" />
            ServiceNow CMDB
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-8 w-24" />
        </CardContent>
      </Card>
    );
  }

  // Error state
  if (isError || !cmdbStatus) {
    return (
      <Card>
        <CardHeader className="pb-4">
          <CardTitle className="flex items-center gap-2 text-base">
            <Database className="h-4 w-4" />
            ServiceNow CMDB
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-start gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium">Unable to load CMDB status</p>
              <p className="text-xs text-muted-foreground mt-1">
                The CMDB integration may be unavailable. Try syncing manually.
              </p>
            </div>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="mt-4 gap-2"
            onClick={handleSync}
            disabled={syncMutation.isPending}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`}
            />
            Sync Now
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-base">
          <Database className="h-4 w-4" />
          ServiceNow CMDB
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Sync status indicator */}
        <div className="flex items-center gap-2">
          {cmdbStatus.synced ? (
            <>
              <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />
              <span className="text-sm font-medium text-green-700 dark:text-green-400">
                Synced
              </span>
            </>
          ) : (
            <>
              <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              <span className="text-sm font-medium text-red-700 dark:text-red-400">
                Not Synced
              </span>
            </>
          )}
        </div>

        {/* CI Number with ServiceNow link */}
        {cmdbStatus.ci_number && (
          <div className="flex flex-col space-y-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              CI Number
            </span>
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono">{cmdbStatus.ci_number}</span>
              {cmdbStatus.servicenow_url && (
                <a
                  href={cmdbStatus.servicenow_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  Open in ServiceNow
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>
          </div>
        )}

        {/* Sys ID */}
        {cmdbStatus.sys_id && (
          <div className="flex flex-col space-y-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Sys ID
            </span>
            <span className="text-sm font-mono text-muted-foreground">
              {cmdbStatus.sys_id}
            </span>
          </div>
        )}

        {/* Last Sync */}
        <div className="flex flex-col space-y-1">
          <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Last Sync
          </span>
          <span className="text-sm">
            {cmdbStatus.last_sync
              ? new Date(cmdbStatus.last_sync).toLocaleString()
              : 'Never'}
          </span>
        </div>

        {/* Operational Status */}
        {cmdbStatus.operational_status && (
          <div className="flex flex-col space-y-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Operational Status
            </span>
            <div>
              <Badge variant={getStatusVariant(cmdbStatus.operational_status)}>
                {cmdbStatus.operational_status}
              </Badge>
            </div>
          </div>
        )}

        {/* Install Status */}
        {cmdbStatus.install_status && (
          <div className="flex flex-col space-y-1">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Install Status
            </span>
            <span className="text-sm">{cmdbStatus.install_status}</span>
          </div>
        )}

        {/* Sync Now button */}
        <div className="pt-2">
          <Button
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={handleSync}
            disabled={syncMutation.isPending}
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${syncMutation.isPending ? 'animate-spin' : ''}`}
            />
            {syncMutation.isPending
              ? 'Syncing...'
              : syncTriggered && syncMutation.isSuccess
                ? 'Synced!'
                : 'Sync Now'}
          </Button>
          {syncMutation.isError && (
            <p className="text-xs text-destructive mt-2">
              Sync failed. Please try again.
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
