'use client';

import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowDownAZ,
  ArrowUpAZ,
  Filter,
  Inbox,
  ShieldAlert,
  Server,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { ApprovalCard } from '@/components/approvals/approval-card';
import type { ServerResponse } from '@/lib/api/types';

type SortOption = 'newest' | 'oldest' | 'environment' | 'instance_size';

interface ApprovalQueueProps {
  servers: ServerResponse[];
  isLoading?: boolean;
}

const SORT_LABELS: Record<SortOption, string> = {
  newest: 'Newest First',
  oldest: 'Oldest First',
  environment: 'Environment',
  instance_size: 'Instance Size',
};

const ENV_ORDER: Record<string, number> = {
  production: 0,
  staging: 1,
  dev: 2,
};

const SIZE_ORDER: Record<string, number> = {
  xl: 0,
  large: 1,
  medium: 2,
  small: 3,
};

export function ApprovalQueue({ servers, isLoading }: ApprovalQueueProps) {
  const [sortBy, setSortBy] = useState<SortOption>('newest');
  const [filterEnv, setFilterEnv] = useState<string>('all');

  // Compute summary stats
  const stats = useMemo(() => {
    const total = servers.length;
    const production = servers.filter((s) => s.environment === 'production').length;
    const largeInstance = servers.filter((s) => s.instance_size === 'xl').length;
    return { total, production, largeInstance };
  }, [servers]);

  // Unique environments in the current set (for filter dropdown)
  const environments = useMemo(() => {
    const envSet = new Set(servers.map((s) => s.environment));
    return Array.from(envSet).sort(
      (a, b) => (ENV_ORDER[a] ?? 99) - (ENV_ORDER[b] ?? 99),
    );
  }, [servers]);

  // Filter then sort
  const displayed = useMemo(() => {
    let filtered = servers;
    if (filterEnv !== 'all') {
      filtered = filtered.filter((s) => s.environment === filterEnv);
    }

    const sorted = [...filtered];
    switch (sortBy) {
      case 'newest':
        sorted.sort(
          (a, b) =>
            new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
        );
        break;
      case 'oldest':
        sorted.sort(
          (a, b) =>
            new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
        );
        break;
      case 'environment':
        sorted.sort(
          (a, b) =>
            (ENV_ORDER[a.environment] ?? 99) - (ENV_ORDER[b.environment] ?? 99),
        );
        break;
      case 'instance_size':
        sorted.sort(
          (a, b) =>
            (SIZE_ORDER[a.instance_size] ?? 99) -
            (SIZE_ORDER[b.instance_size] ?? 99),
        );
        break;
    }
    return sorted;
  }, [servers, sortBy, filterEnv]);

  if (isLoading) {
    return (
      <div className="space-y-4">
        {/* Summary skeleton */}
        <div className="grid grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-20 rounded-lg" />
          ))}
        </div>
        {/* Card skeletons */}
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={`card-${i}`} className="h-48 rounded-lg" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
              <Server className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.total}</p>
              <p className="text-xs text-muted-foreground">Total Pending</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-950/30">
              <ShieldAlert className="h-5 w-5 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.production}</p>
              <p className="text-xs text-muted-foreground">Production Requests</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-yellow-100 dark:bg-yellow-950/30">
              <AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.largeInstance}</p>
              <p className="text-xs text-muted-foreground">Large Instance Requests</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sort + Filter controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          {sortBy === 'newest' || sortBy === 'oldest' ? (
            sortBy === 'newest' ? (
              <ArrowDownAZ className="h-4 w-4 text-muted-foreground" />
            ) : (
              <ArrowUpAZ className="h-4 w-4 text-muted-foreground" />
            )
          ) : (
            <ArrowDownAZ className="h-4 w-4 text-muted-foreground" />
          )}
          <Select
            value={sortBy}
            onValueChange={(val) => setSortBy(val as SortOption)}
          >
            <SelectTrigger className="w-[170px]">
              <SelectValue placeholder="Sort by..." />
            </SelectTrigger>
            <SelectContent>
              {(Object.keys(SORT_LABELS) as SortOption[]).map((key) => (
                <SelectItem key={key} value={key}>
                  {SORT_LABELS[key]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select value={filterEnv} onValueChange={setFilterEnv}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Filter environment" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Environments</SelectItem>
              {environments.map((env) => (
                <SelectItem key={env} value={env}>
                  {env.charAt(0).toUpperCase() + env.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {filterEnv !== 'all' && (
          <Badge variant="secondary" className="gap-1">
            {filterEnv}
            <button
              onClick={() => setFilterEnv('all')}
              className="ml-1 hover:text-foreground"
              aria-label="Clear filter"
            >
              x
            </button>
          </Badge>
        )}
      </div>

      {/* Card list or empty state */}
      {displayed.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-16 text-center">
            <Inbox className="h-12 w-12 text-muted-foreground/50 mb-4" />
            <h3 className="text-lg font-semibold">No pending approvals</h3>
            <p className="mt-1 text-sm text-muted-foreground max-w-md">
              {filterEnv !== 'all'
                ? `There are no pending requests for the "${filterEnv}" environment. Try clearing the filter.`
                : 'All server requests have been reviewed. New requests requiring approval will appear here.'}
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {displayed.map((server) => (
            <ApprovalCard key={server.id} server={server} />
          ))}
        </div>
      )}
    </div>
  );
}
