'use client';

import { useState, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { ServerActions } from './server-actions';
import {
  columns,
  getDefaultVisibleColumns,
  type ColumnDef,
} from './columns';
import type { ServerResponse } from '@/lib/api/types';
import {
  ArrowDown,
  ArrowUp,
  ArrowUpDown,
  Columns3,
  ServerOff,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SortDirection = 'asc' | 'desc';

interface SortState {
  columnId: string;
  direction: SortDirection;
}

interface ServerTableProps {
  servers: ServerResponse[];
  isLoading: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ServerTable({ servers, isLoading }: ServerTableProps) {
  const router = useRouter();
  const [visibleColumns, setVisibleColumns] = useState<string[]>(
    getDefaultVisibleColumns,
  );
  const [sort, setSort] = useState<SortState>({
    columnId: 'created_at',
    direction: 'desc',
  });

  // Determine which column definitions are visible
  const activeColumns = useMemo(
    () => columns.filter((col) => visibleColumns.includes(col.id)),
    [visibleColumns],
  );

  // Sort the data
  const sortedServers = useMemo(() => {
    const col = columns.find((c) => c.id === sort.columnId);
    if (!col || !col.sortable) return servers;

    return [...servers].sort((a, b) => {
      const aVal = col.accessorFn(a);
      const bVal = col.accessorFn(b);

      if (aVal === null && bVal === null) return 0;
      if (aVal === null) return 1;
      if (bVal === null) return -1;

      let comparison: number;
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        comparison = aVal - bVal;
      } else {
        comparison = String(aVal).localeCompare(String(bVal));
      }

      return sort.direction === 'asc' ? comparison : -comparison;
    });
  }, [servers, sort]);

  // Toggle sort on a column
  const handleSort = (columnId: string) => {
    setSort((prev) => {
      if (prev.columnId === columnId) {
        return {
          columnId,
          direction: prev.direction === 'asc' ? 'desc' : 'asc',
        };
      }
      return { columnId, direction: 'asc' };
    });
  };

  // Toggle column visibility
  const toggleColumn = (columnId: string) => {
    setVisibleColumns((prev) =>
      prev.includes(columnId)
        ? prev.filter((id) => id !== columnId)
        : [...prev, columnId],
    );
  };

  // Sort icon for column headers
  const SortIcon = ({ columnId }: { columnId: string }) => {
    if (sort.columnId !== columnId) {
      return <ArrowUpDown className="ml-1 h-3.5 w-3.5 text-muted-foreground/50" />;
    }
    return sort.direction === 'asc' ? (
      <ArrowUp className="ml-1 h-3.5 w-3.5" />
    ) : (
      <ArrowDown className="ml-1 h-3.5 w-3.5" />
    );
  };

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {activeColumns.map((col) => (
                <TableHead key={col.id}>{col.header}</TableHead>
              ))}
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {Array.from({ length: 5 }).map((_, i) => (
              <TableRow key={i}>
                {activeColumns.map((col) => (
                  <TableCell key={col.id}>
                    <Skeleton className="h-5 w-full" />
                  </TableCell>
                ))}
                <TableCell>
                  <Skeleton className="h-8 w-8" />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Empty state
  // ---------------------------------------------------------------------------
  if (sortedServers.length === 0) {
    return (
      <div className="rounded-md border">
        <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
          <div className="rounded-full bg-muted p-4 mb-4">
            <ServerOff className="h-8 w-8 text-muted-foreground" />
          </div>
          <h3 className="text-lg font-semibold mb-1">No servers found</h3>
          <p className="text-sm text-muted-foreground max-w-sm">
            No servers match the current filters. Try adjusting your search or
            filter criteria, or create a new server to get started.
          </p>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Data table
  // ---------------------------------------------------------------------------
  return (
    <div className="space-y-2">
      {/* Column visibility toggle */}
      <div className="flex justify-end">
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="h-8">
              <Columns3 className="mr-2 h-4 w-4" />
              Columns
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-[180px]">
            <DropdownMenuLabel>Toggle columns</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {columns.map((col) => (
              <DropdownMenuCheckboxItem
                key={col.id}
                checked={visibleColumns.includes(col.id)}
                onCheckedChange={() => toggleColumn(col.id)}
              >
                {col.header}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              {activeColumns.map((col) => (
                <TableHead key={col.id}>
                  {col.sortable ? (
                    <button
                      className="inline-flex items-center hover:text-foreground transition-colors -ml-1 px-1"
                      onClick={() => handleSort(col.id)}
                    >
                      {col.header}
                      <SortIcon columnId={col.id} />
                    </button>
                  ) : (
                    col.header
                  )}
                </TableHead>
              ))}
              <TableHead className="w-[50px]" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedServers.map((server) => (
              <TableRow
                key={server.id}
                className="cursor-pointer"
                onClick={() =>
                  router.push(`/dashboard/servers/${server.id}`)
                }
              >
                {activeColumns.map((col) => (
                  <TableCell key={col.id}>{col.cell(server)}</TableCell>
                ))}
                <TableCell>
                  <ServerActions server={server} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
