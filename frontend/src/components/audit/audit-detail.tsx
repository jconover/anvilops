'use client';

import Link from 'next/link';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ExternalLink,
  User,
  Globe,
  Clock,
  Tag,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import type { AuditLog } from '@/lib/api/audit';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatFullTimestamp(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZoneName: 'short',
  });
}

function StatusIndicator({ status }: { status: string }) {
  switch (status) {
    case 'success':
      return (
        <div className="flex items-center gap-1.5 text-green-600 dark:text-green-400">
          <CheckCircle2 className="h-4 w-4" />
          <span className="text-sm font-medium">Success</span>
        </div>
      );
    case 'failure':
      return (
        <div className="flex items-center gap-1.5 text-red-600 dark:text-red-400">
          <XCircle className="h-4 w-4" />
          <span className="text-sm font-medium">Failure</span>
        </div>
      );
    case 'error':
      return (
        <div className="flex items-center gap-1.5 text-yellow-600 dark:text-yellow-400">
          <AlertTriangle className="h-4 w-4" />
          <span className="text-sm font-medium">Error</span>
        </div>
      );
    default:
      return (
        <span className="text-sm text-muted-foreground">{status}</span>
      );
  }
}

function buildResourceLink(
  resourceType: string | null,
  resourceId: string | null,
): string | null {
  if (!resourceType || !resourceId) return null;
  switch (resourceType) {
    case 'server':
      return `/dashboard/servers/${resourceId}`;
    case 'request':
      return `/dashboard/requests/${resourceId}`;
    default:
      return null;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface AuditDetailProps {
  log: AuditLog;
}

export function AuditDetail({ log }: AuditDetailProps) {
  const resourceLink = buildResourceLink(log.resource_type, log.resource_id);

  return (
    <div className="space-y-4 rounded-lg border bg-muted/30 p-4">
      {/* Top row: status + timestamps */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Status */}
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Status
          </p>
          <StatusIndicator status={log.status} />
        </div>

        {/* Timestamp */}
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Timestamp
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <Clock className="h-3.5 w-3.5 text-muted-foreground" />
            {formatFullTimestamp(log.timestamp)}
          </div>
        </div>

        {/* Actor */}
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Actor
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <User className="h-3.5 w-3.5 text-muted-foreground" />
            <span>{log.actor_email ?? 'System'}</span>
            {log.actor_role && (
              <Badge variant="outline" className="ml-1 text-[10px]">
                {log.actor_role}
              </Badge>
            )}
          </div>
        </div>

        {/* IP Address */}
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            IP Address
          </p>
          <div className="flex items-center gap-1.5 text-sm">
            <Globe className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono text-xs">
              {log.ip_address ?? 'N/A'}
            </span>
          </div>
        </div>
      </div>

      <Separator />

      {/* Action + Resource */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Action */}
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Action
          </p>
          <div className="flex items-center gap-2 text-sm">
            <Badge variant="secondary" className="font-mono text-xs">
              {log.action}
            </Badge>
            <span className="text-muted-foreground">in</span>
            <Badge variant="outline" className="text-xs">
              {log.category}
            </Badge>
          </div>
        </div>

        {/* Resource */}
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Resource
          </p>
          {log.resource_type ? (
            <div className="flex items-center gap-2 text-sm">
              <Tag className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="capitalize">{log.resource_type}</span>
              {log.resource_name && (
                <span className="font-mono text-xs text-muted-foreground">
                  ({log.resource_name})
                </span>
              )}
              {resourceLink && (
                <Link
                  href={resourceLink}
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  View
                  <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">N/A</span>
          )}
        </div>
      </div>

      {/* Error message */}
      {log.error_message && (
        <>
          <Separator />
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-red-500">
              Error Message
            </p>
            <p className="rounded-md bg-red-50 p-3 font-mono text-xs text-red-700 dark:bg-red-950/30 dark:text-red-400">
              {log.error_message}
            </p>
          </div>
        </>
      )}

      {/* Details JSON */}
      {log.details && Object.keys(log.details).length > 0 && (
        <>
          <Separator />
          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Details
            </p>
            <pre className="max-h-80 overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-50 dark:bg-slate-900">
              <code>{JSON.stringify(log.details, null, 2)}</code>
            </pre>
          </div>
        </>
      )}

      {/* Audit trail metadata */}
      <Separator />
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
        <span>
          <strong>Log ID:</strong>{' '}
          <span className="font-mono">{log.id}</span>
        </span>
        <span>
          <strong>Created:</strong> {formatFullTimestamp(log.created_at)}
        </span>
        {log.resource_id && (
          <span>
            <strong>Resource ID:</strong>{' '}
            <span className="font-mono">{log.resource_id}</span>
          </span>
        )}
      </div>
    </div>
  );
}
