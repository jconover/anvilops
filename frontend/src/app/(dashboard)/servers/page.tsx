'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { ServerTable } from '@/components/server-inventory/server-table';
import { ServerFilters, type FilterState } from '@/components/server-inventory/filters';
import { useServers } from '@/lib/api/hooks';
import type { ServerListParams } from '@/lib/api/types';
import { Download, Plus, ChevronLeft, ChevronRight } from 'lucide-react';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 20;

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ServersPage() {
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState<FilterState>({
    search: '',
    environments: [],
    statuses: [],
    osTypes: [],
  });

  // Build API params from filter state.
  // The API supports a single `status` and `environment` filter plus `search`,
  // so we do server-side filtering for search/environment/status and
  // client-side filtering for OS type and multi-select combos the API
  // doesn't support natively.
  const apiParams: ServerListParams = useMemo(() => {
    const params: ServerListParams = {
      skip: page * PAGE_SIZE,
      limit: PAGE_SIZE,
    };
    if (filters.search) {
      params.search = filters.search;
    }
    // If exactly one environment is selected we can push it to the API
    if (filters.environments.length === 1) {
      params.environment = filters.environments[0];
    }
    // If exactly one status is selected we can push it to the API
    if (filters.statuses.length === 1) {
      params.status = filters.statuses[0] as ServerListParams['status'];
    }
    return params;
  }, [page, filters]);

  const { data, isLoading } = useServers(apiParams);

  // Client-side filtering for multi-select and OS type
  const filteredServers = useMemo(() => {
    if (!data?.servers) return [];
    let result = data.servers;

    // Multi-environment filter (when >1 selected, API only got the first)
    if (filters.environments.length > 1) {
      result = result.filter((s) =>
        filters.environments.includes(s.environment),
      );
    }

    // Multi-status filter (when >1 selected)
    if (filters.statuses.length > 1) {
      result = result.filter((s) => filters.statuses.includes(s.status));
    }

    // OS type filter (always client-side since API doesn't support it)
    if (filters.osTypes.length > 0) {
      result = result.filter((s) => filters.osTypes.includes(s.os_type));
    }

    return result;
  }, [data, filters]);

  const totalCount = data?.total ?? 0;
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const startItem = page * PAGE_SIZE + 1;
  const endItem = Math.min((page + 1) * PAGE_SIZE, totalCount);

  // Reset to first page when filters change
  const handleFiltersChange = (newFilters: FilterState) => {
    setFilters(newFilters);
    setPage(0);
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">
            Server Inventory
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage and monitor all provisioned servers across your
            environments.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm">
            <Download className="mr-2 h-4 w-4" />
            Export
          </Button>
          <Button asChild size="sm">
            <Link href="/dashboard/servers/new">
              <Plus className="mr-2 h-4 w-4" />
              New Server
            </Link>
          </Button>
        </div>
      </div>

      {/* Filters */}
      <ServerFilters filters={filters} onFiltersChange={handleFiltersChange} />

      {/* Data table */}
      <ServerTable servers={filteredServers} isLoading={isLoading} />

      {/* Pagination */}
      {totalCount > 0 && (
        <div className="flex items-center justify-between px-2">
          <p className="text-sm text-muted-foreground">
            Showing {startItem}&ndash;{endItem} of {totalCount} servers
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 0}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              <ChevronLeft className="h-4 w-4 mr-1" />
              Previous
            </Button>
            <span className="text-sm text-muted-foreground min-w-[80px] text-center">
              Page {page + 1} of {totalPages}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
