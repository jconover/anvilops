'use client';

import { useState, useMemo, useCallback } from 'react';
import Link from 'next/link';
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  FileText,
  ExternalLink,
} from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { AuditDetail } from '@/components/audit/audit-detail';
import type { AuditLog } from '@/lib/api/audit';

// ---------------------------------------------------------------------------
// Action label + color mapping
// ---------------------------------------------------------------------------

interface ActionMeta {
  label: string;
  variant: 'info' | 'success' | 'destructive' | 'warning' | 'secondary' | 'default';
}

const ACTION_MAP: Record<string, ActionMeta> = {
  'server.created': { label: 'Server Created', variant: 'info' },
  'server.approved': { label: 'Server Approved', variant: 'success' },
  'server.rejected': { label: 'Server Rejected', variant: 'destructive' },
  'server.provisioning': { label: 'Provisioning Started', variant: 'info' },
  'server.provisioned': { label: 'Provisioning Complete', variant: 'success' },
  'server.configuring': { label: 'Configuration Started', variant: 'info' },
  'server.configured': { label: 'Configuration Complete', variant: 'success' },
  'server.ready': { label: 'Server Ready', variant: 'success' },
  'server.build_failed': { label: 'Build Failed', variant: 'destructive' },
  'server.decommissioned': { label: 'Server Decommissioned', variant: 'warning' },
  'server.deleted': { label: 'Server Deleted', variant: 'destructive' },
  'auth.login': { label: 'User Login', variant: 'secondary' },
  'auth.logout': { label: 'User Logout', variant: 'secondary' },
  'auth.login_failed': { label: 'Login Failed', variant: 'destructive' },
  'template.created': { label: 'Template Created', variant: 'info' },
  'template.updated': { label: 'Template Updated', variant: 'info' },
  'template.deleted': { label: 'Template Deleted', variant: 'warning' },
  'system.config_changed': { label: 'Config Changed', variant: 'warning' },
  'system.maintenance': { label: 'Maintenance', variant: 'secondary' },
};

function getActionMeta(action: string): ActionMeta {
  return (
    ACTION_MAP[action] ?? {
      label: action
        .split('.')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' '),
      variant: 'default' as const,
    }
  );
}

// ---------------------------------------------------------------------------
// Category badge colors
// ---------------------------------------------------------------------------

function getCategoryVariant(
  category: string,
): 'info' | 'success' | 'warning' | 'secondary' | 'default' {
  switch (category) {
    case 'server':
      return 'info';
    case 'auth':
      return 'secondary';
    case 'template':
      return 'success';
    case 'system':
      return 'warning';
    default:
      return 'default';
  }
}

// ---------------------------------------------------------------------------
// Status icon
// ---------------------------------------------------------------------------

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case 'success':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'failure':
      return <XCircle className="h-4 w-4 text-red-500" />;
    case 'error':
      return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    default:
      return <span className="text-xs text-muted-foreground">{status}</span>;
  }
}

// ---------------------------------------------------------------------------
// Timestamp formatter
// ---------------------------------------------------------------------------

function formatShortTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  }) +
    ', ' +
    date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
    });
}

// ---------------------------------------------------------------------------
// Resource link builder
// ---------------------------------------------------------------------------

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
// Sorting
// ---------------------------------------------------------------------------

type SortField = 'timestamp' | 'action' | 'category' | 'actor_email' | 'status';
type SortDir = 'asc' | 'desc';

function SortIndicator({
  field,
  currentField,
  currentDir,
}: {
  field: SortField;
  currentField: SortField;
  currentDir: SortDir;
}) {
  if (field !== currentField) {
    return <ArrowUpDown className="ml-1 inline h-3 w-3 text-muted-foreground/40" />;
  }
  return currentDir === 'asc' ? (
    <ArrowUp className="ml-1 inline h-3 w-3" />
  ) : (
    <ArrowDown className="ml-1 inline h-3 w-3" />
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface AuditTableProps {
  logs: AuditLog[];
  isLoading?: boolean;
}

export function AuditTable({ logs, isLoading }: AuditTableProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sortField, setSortField] = useState<SortField>('timestamp');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const toggleExpand = useCallback((id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  }, []);

  const handleSort = useCallback(
    (field: SortField) => {
      if (sortField === field) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortDir('desc');
      }
    },
    [sortField],
  );

  const sortedLogs = useMemo(() => {
    const sorted = [...logs];
    sorted.sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'timestamp':
          cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          break;
        case 'action':
          cmp = a.action.localeCompare(b.action);
          break;
        case 'category':
          cmp = a.category.localeCompare(b.category);
          break;
        case 'actor_email':
          cmp = (a.actor_email ?? '').localeCompare(b.actor_email ?? '');
          break;
        case 'status':
          cmp = a.status.localeCompare(b.status);
          break;
      }
      return sortDir === 'asc' ? cmp : -cmp;
    });
    return sorted;
  }, [logs, sortField, sortDir]);

  // Loading skeleton
  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <div
            key={i}
            className="h-12 animate-pulse rounded-md bg-muted"
          />
        ))}
      </div>
    );
  }

  // Empty state
  if (logs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16">
        <FileText className="h-12 w-12 text-muted-foreground/50" />
        <p className="mt-4 text-sm font-medium text-muted-foreground">
          No audit log entries found
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          Try adjusting your filters or date range.
        </p>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Table>
        <TableHeader>
          <TableRow>
            {/* Expand chevron column */}
            <TableHead className="w-8" />

            <TableHead>
              <button
                type="button"
                className="flex items-center text-xs font-medium hover:text-foreground"
                onClick={() => handleSort('timestamp')}
              >
                Timestamp
                <SortIndicator
                  field="timestamp"
                  currentField={sortField}
                  currentDir={sortDir}
                />
              </button>
            </TableHead>

            <TableHead>
              <button
                type="button"
                className="flex items-center text-xs font-medium hover:text-foreground"
                onClick={() => handleSort('action')}
              >
                Action
                <SortIndicator
                  field="action"
                  currentField={sortField}
                  currentDir={sortDir}
                />
              </button>
            </TableHead>

            <TableHead>
              <button
                type="button"
                className="flex items-center text-xs font-medium hover:text-foreground"
                onClick={() => handleSort('category')}
              >
                Category
                <SortIndicator
                  field="category"
                  currentField={sortField}
                  currentDir={sortDir}
                />
              </button>
            </TableHead>

            <TableHead>
              <button
                type="button"
                className="flex items-center text-xs font-medium hover:text-foreground"
                onClick={() => handleSort('actor_email')}
              >
                Actor
                <SortIndicator
                  field="actor_email"
                  currentField={sortField}
                  currentDir={sortDir}
                />
              </button>
            </TableHead>

            <TableHead>Resource</TableHead>

            <TableHead>
              <button
                type="button"
                className="flex items-center text-xs font-medium hover:text-foreground"
                onClick={() => handleSort('status')}
              >
                Status
                <SortIndicator
                  field="status"
                  currentField={sortField}
                  currentDir={sortDir}
                />
              </button>
            </TableHead>

            <TableHead>IP</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sortedLogs.map((log) => {
            const isExpanded = expandedId === log.id;
            const actionMeta = getActionMeta(log.action);
            const resourceLink = buildResourceLink(
              log.resource_type,
              log.resource_id,
            );

            return (
              <AuditTableRow
                key={log.id}
                log={log}
                isExpanded={isExpanded}
                actionMeta={actionMeta}
                resourceLink={resourceLink}
                onToggle={() => toggleExpand(log.id)}
              />
            );
          })}
        </TableBody>
      </Table>
    </TooltipProvider>
  );
}

// ---------------------------------------------------------------------------
// Row (extracted for readability)
// ---------------------------------------------------------------------------

interface AuditTableRowProps {
  log: AuditLog;
  isExpanded: boolean;
  actionMeta: ActionMeta;
  resourceLink: string | null;
  onToggle: () => void;
}

function AuditTableRow({
  log,
  isExpanded,
  actionMeta,
  resourceLink,
  onToggle,
}: AuditTableRowProps) {
  // Generate initials for actor avatar fallback
  const initials = log.actor_email
    ? log.actor_email
        .split('@')[0]
        .split('.')
        .map((p) => p[0]?.toUpperCase() ?? '')
        .join('')
        .slice(0, 2)
    : 'SY';

  return (
    <>
      <TableRow
        className="cursor-pointer"
        onClick={onToggle}
        data-state={isExpanded ? 'selected' : undefined}
      >
        {/* Expand chevron */}
        <TableCell className="w-8 pr-0">
          {isExpanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </TableCell>

        {/* Timestamp */}
        <TableCell className="whitespace-nowrap">
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="text-sm">
                {formatShortTimestamp(log.timestamp)}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top">
              <span className="font-mono text-xs">{log.timestamp}</span>
            </TooltipContent>
          </Tooltip>
        </TableCell>

        {/* Action */}
        <TableCell>
          <Badge variant={actionMeta.variant} className="text-xs whitespace-nowrap">
            {actionMeta.label}
          </Badge>
        </TableCell>

        {/* Category */}
        <TableCell>
          <Badge
            variant={getCategoryVariant(log.category)}
            className="text-[10px] uppercase tracking-wider"
          >
            {log.category}
          </Badge>
        </TableCell>

        {/* Actor */}
        <TableCell>
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-semibold text-primary">
              {initials}
            </div>
            <span className="max-w-[160px] truncate text-sm">
              {log.actor_email ?? 'System'}
            </span>
          </div>
        </TableCell>

        {/* Resource */}
        <TableCell>
          {log.resource_type ? (
            <div className="flex items-center gap-1.5">
              <span className="text-sm text-muted-foreground capitalize">
                {log.resource_type}
              </span>
              {log.resource_name && (
                <span className="max-w-[120px] truncate font-mono text-xs text-muted-foreground">
                  {log.resource_name}
                </span>
              )}
              {resourceLink && (
                <Link
                  href={resourceLink}
                  onClick={(e) => e.stopPropagation()}
                  className="text-primary hover:text-primary/80"
                >
                  <ExternalLink className="h-3 w-3" />
                </Link>
              )}
            </div>
          ) : (
            <span className="text-xs text-muted-foreground">--</span>
          )}
        </TableCell>

        {/* Status */}
        <TableCell>
          <Tooltip>
            <TooltipTrigger asChild>
              <span>
                <StatusIcon status={log.status} />
              </span>
            </TooltipTrigger>
            <TooltipContent side="top">
              <span className="text-xs capitalize">{log.status}</span>
            </TooltipContent>
          </Tooltip>
        </TableCell>

        {/* IP */}
        <TableCell>
          <span className="font-mono text-xs text-muted-foreground">
            {log.ip_address ?? '--'}
          </span>
        </TableCell>
      </TableRow>

      {/* Expanded detail row */}
      {isExpanded && (
        <TableRow>
          <TableCell colSpan={8} className="bg-muted/20 p-0">
            <div className="p-4">
              <AuditDetail log={log} />
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
