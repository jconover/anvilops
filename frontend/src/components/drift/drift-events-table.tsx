'use client';

import { useState } from 'react';
import {
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Filter,
  RotateCcw,
  Search,
  Shield,
  X,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import type { EnhancedDriftEvent, DriftEventsParams } from '@/lib/api/drift';

// ---------------------------------------------------------------------------
// Severity badge mapping
// ---------------------------------------------------------------------------

const SEVERITY_BADGE: Record<
  string,
  { variant: 'destructive' | 'warning' | 'secondary' | 'outline'; className?: string }
> = {
  critical: { variant: 'destructive' },
  high: { variant: 'warning', className: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 border-transparent' },
  medium: { variant: 'warning' },
  low: { variant: 'secondary' },
};

function getSeverityBadge(severity: string) {
  return SEVERITY_BADGE[severity.toLowerCase()] || SEVERITY_BADGE.low;
}

// ---------------------------------------------------------------------------
// Category badge colors
// ---------------------------------------------------------------------------

const CATEGORY_COLORS: Record<string, string> = {
  security: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300',
  configuration: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300',
  package: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300',
  service: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300',
  file: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300',
};

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

function truncateValue(value: string | null, maxLength: number = 80): string {
  if (!value) return '(none)';
  if (value.length <= maxLength) return value;
  return value.slice(0, maxLength) + '...';
}

// ---------------------------------------------------------------------------
// Filter options
// ---------------------------------------------------------------------------

const SEVERITY_OPTIONS = [
  { value: 'all', label: 'All Severities' },
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
] as const;

const CATEGORY_OPTIONS = [
  { value: 'all', label: 'All Categories' },
  { value: 'security', label: 'Security' },
  { value: 'configuration', label: 'Configuration' },
  { value: 'package', label: 'Package' },
  { value: 'service', label: 'Service' },
  { value: 'file', label: 'File' },
] as const;

const RESOLVED_OPTIONS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'unresolved', label: 'Unresolved' },
  { value: 'resolved', label: 'Resolved' },
] as const;

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DriftEventsTableProps {
  events: EnhancedDriftEvent[];
  total: number;
  isLoading: boolean;
  params: DriftEventsParams;
  onParamsChange: (params: DriftEventsParams) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DriftEventsTable({
  events,
  total,
  isLoading,
  params,
  onParamsChange,
}: DriftEventsTableProps) {
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [showFilters, setShowFilters] = useState(false);

  function toggleRow(id: string) {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function updateFilter(key: keyof DriftEventsParams, value: string) {
    const updated: DriftEventsParams = { ...params, page: 1 };
    if (value === 'all' || value === '') {
      delete updated[key];
    } else if (key === 'is_resolved') {
      updated.is_resolved = value === 'resolved';
    } else {
      (updated as any)[key] = value;
    }
    onParamsChange(updated);
  }

  function clearFilters() {
    onParamsChange({ page: 1, page_size: params.page_size || 20 });
  }

  const hasActiveFilters =
    params.severity || params.category || params.is_resolved !== undefined || params.server_id;

  const currentPage = params.page || 1;
  const pageSize = params.page_size || 20;
  const totalPages = Math.ceil(total / pageSize);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">
            Drift Events
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              ({total.toLocaleString()} total)
            </span>
          </CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant={showFilters ? 'default' : 'outline'}
              size="sm"
              className="h-8 gap-1.5"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="h-3.5 w-3.5" />
              Filters
              {hasActiveFilters && (
                <span className="ml-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary-foreground/20 px-1 text-[10px] font-bold">
                  !
                </span>
              )}
            </Button>
            {hasActiveFilters && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1 text-xs"
                onClick={clearFilters}
              >
                <X className="h-3 w-3" />
                Clear
              </Button>
            )}
          </div>
        </div>

        {/* Filter bar */}
        {showFilters && (
          <div className="mt-3 flex flex-wrap gap-2 rounded-lg border bg-muted/30 p-3">
            <Select
              value={params.severity || 'all'}
              onValueChange={(v) => updateFilter('severity', v)}
            >
              <SelectTrigger className="h-8 w-[150px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SEVERITY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={params.category || 'all'}
              onValueChange={(v) => updateFilter('category', v)}
            >
              <SelectTrigger className="h-8 w-[160px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select
              value={
                params.is_resolved === undefined
                  ? 'all'
                  : params.is_resolved
                    ? 'resolved'
                    : 'unresolved'
              }
              onValueChange={(v) => updateFilter('is_resolved', v)}
            >
              <SelectTrigger className="h-8 w-[150px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {RESOLVED_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <div className="relative">
              <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Filter by server..."
                className="h-8 w-[180px] pl-7 text-xs"
                value={params.server_id || ''}
                onChange={(e) => updateFilter('server_id', e.target.value)}
              />
            </div>
          </div>
        )}
      </CardHeader>

      <CardContent className="px-0 pb-0">
        {isLoading ? (
          <div className="space-y-2 px-6 pb-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-12 text-center">
            <Shield className="h-8 w-8 text-muted-foreground" />
            <p className="text-sm font-medium">No drift events found</p>
            <p className="text-xs text-muted-foreground">
              {hasActiveFilters
                ? 'Try adjusting your filters.'
                : 'No drift has been detected across the fleet.'}
            </p>
          </div>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-8" />
                  <TableHead>Detected</TableHead>
                  <TableHead>Server</TableHead>
                  <TableHead>Resource</TableHead>
                  <TableHead>Property</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>CIS Control</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {events.map((event) => {
                  const isExpanded = expandedRows.has(event.id);
                  const sevBadge = getSeverityBadge(event.severity);
                  const catColor =
                    CATEGORY_COLORS[event.drift_category.toLowerCase()] || '';

                  return (
                    <>
                      <TableRow
                        key={event.id}
                        className="cursor-pointer"
                        onClick={() => toggleRow(event.id)}
                      >
                        <TableCell className="w-8 pr-0">
                          {isExpanded ? (
                            <ChevronDown className="h-4 w-4 text-muted-foreground" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-muted-foreground" />
                          )}
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-xs">
                          {formatTimestamp(event.detected_at)}
                        </TableCell>
                        <TableCell>
                          <a
                            href={`/dashboard/requests/${event.server_request_id}`}
                            className="text-xs font-medium text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {event.certname}
                          </a>
                        </TableCell>
                        <TableCell className="max-w-[200px] truncate text-xs font-mono">
                          {event.resource_type}[{event.resource_title}]
                        </TableCell>
                        <TableCell className="text-xs font-mono">
                          {event.property_name}
                        </TableCell>
                        <TableCell>
                          <Badge
                            variant={sevBadge.variant}
                            className={`text-[11px] ${sevBadge.className || ''}`}
                          >
                            {event.severity}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <span
                            className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium capitalize ${catColor}`}
                          >
                            {event.drift_category}
                          </span>
                        </TableCell>
                        <TableCell className="text-xs font-mono text-muted-foreground">
                          {event.cis_control_id || '--'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1.5">
                            {event.is_resolved ? (
                              <Badge variant="success" className="gap-1 text-[11px]">
                                Resolved
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="gap-1 text-[11px]">
                                Unresolved
                              </Badge>
                            )}
                            {event.is_corrective && (
                              <Badge variant="info" className="gap-1 text-[11px]">
                                <RotateCcw className="h-3 w-3" />
                                Auto-fixed
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>

                      {/* Expanded detail row */}
                      {isExpanded && (
                        <TableRow key={`${event.id}-detail`}>
                          <TableCell colSpan={9} className="bg-muted/30 px-8 py-3">
                            <div className="space-y-2">
                              <p className="text-xs font-medium text-muted-foreground">
                                Value Change
                              </p>
                              <div className="flex items-center gap-3 text-xs">
                                <div className="min-w-0 flex-1">
                                  <p className="mb-1 text-[11px] font-medium text-muted-foreground">
                                    Previous Value
                                  </p>
                                  <code className="block overflow-x-auto rounded bg-red-50 px-2 py-1.5 text-red-700 dark:bg-red-950/40 dark:text-red-300">
                                    {event.old_value || '(none)'}
                                  </code>
                                </div>
                                <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                                <div className="min-w-0 flex-1">
                                  <p className="mb-1 text-[11px] font-medium text-muted-foreground">
                                    Current Value
                                  </p>
                                  <code className="block overflow-x-auto rounded bg-green-50 px-2 py-1.5 text-green-700 dark:bg-green-950/40 dark:text-green-300">
                                    {event.new_value || '(none)'}
                                  </code>
                                </div>
                              </div>
                              <div className="flex gap-4 pt-1 text-[11px] text-muted-foreground">
                                {event.resolved_at && (
                                  <span>
                                    Resolved: {formatTimestamp(event.resolved_at)}
                                  </span>
                                )}
                                {event.resolution_type && (
                                  <span>
                                    Resolution: <span className="capitalize">{event.resolution_type}</span>
                                  </span>
                                )}
                                {event.cis_control_id && (
                                  <span>CIS: {event.cis_control_id}</span>
                                )}
                              </div>
                            </div>
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  );
                })}
              </TableBody>
            </Table>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between border-t px-4 py-3">
                <p className="text-xs text-muted-foreground">
                  Showing {(currentPage - 1) * pageSize + 1}--
                  {Math.min(currentPage * pageSize, total)} of {total}
                </p>
                <div className="flex items-center gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    disabled={currentPage <= 1}
                    onClick={() =>
                      onParamsChange({ ...params, page: currentPage - 1 })
                    }
                  >
                    Previous
                  </Button>
                  <span className="px-2 text-xs text-muted-foreground">
                    Page {currentPage} of {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2 text-xs"
                    disabled={currentPage >= totalPages}
                    onClick={() =>
                      onParamsChange({ ...params, page: currentPage + 1 })
                    }
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
