"use client";

import { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ServerResponse, ServerStatus } from "@/lib/api/types";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Server,
  ExternalLink,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Status badge configuration
// ---------------------------------------------------------------------------

const STATUS_BADGE_CONFIG: Record<
  ServerStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info";
  }
> = {
  pending: { label: "Pending", variant: "secondary" },
  approved: { label: "Approved", variant: "info" },
  provisioning: { label: "Provisioning", variant: "info" },
  configuring: { label: "Configuring", variant: "info" },
  validating: { label: "Validating", variant: "warning" },
  ready: { label: "Ready", variant: "success" },
  failed: { label: "Failed", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "secondary" },
  decommissioning: { label: "Decommissioning", variant: "warning" },
  decommissioned: { label: "Decommissioned", variant: "secondary" },
};

function StatusBadge({ status }: { status: ServerStatus }) {
  const config = STATUS_BADGE_CONFIG[status] ?? {
    label: status,
    variant: "outline" as const,
  };

  return (
    <Badge variant={config.variant} className="whitespace-nowrap">
      {/* Animated dot for active statuses */}
      {(status === "provisioning" ||
        status === "configuring" ||
        status === "validating") && (
        <span className="mr-1.5 flex h-2 w-2">
          <span className="absolute inline-flex h-2 w-2 animate-ping rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
        </span>
      )}
      {config.label}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// OS display name
// ---------------------------------------------------------------------------

const OS_DISPLAY: Record<string, string> = {
  windows_2022: "Windows 2022",
  windows_2019: "Windows 2019",
  amazon_linux_2023: "Amazon Linux 2023",
  ubuntu_2204: "Ubuntu 22.04",
  rhel_9: "RHEL 9",
};

// ---------------------------------------------------------------------------
// Sorting
// ---------------------------------------------------------------------------

type SortField =
  | "server_name"
  | "environment"
  | "os_type"
  | "status"
  | "created_at"
  | "updated_at";
type SortDirection = "asc" | "desc";

interface SortConfig {
  field: SortField;
  direction: SortDirection;
}

function compareValues(a: string, b: string, direction: SortDirection): number {
  const cmp = a.localeCompare(b);
  return direction === "asc" ? cmp : -cmp;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface RequestListTableProps {
  servers: ServerResponse[];
  className?: string;
}

/**
 * A sortable data table showing all server requests.
 * Click a column header to sort. Click a row to navigate to the detail page.
 */
export function RequestListTable({
  servers,
  className,
}: RequestListTableProps) {
  const router = useRouter();
  const [sort, setSort] = useState<SortConfig>({
    field: "updated_at",
    direction: "desc",
  });

  // Toggle sort when a column header is clicked
  function toggleSort(field: SortField) {
    setSort((prev) => ({
      field,
      direction:
        prev.field === field && prev.direction === "asc" ? "desc" : "asc",
    }));
  }

  // Sort the servers list
  const sorted = useMemo(() => {
    return [...servers].sort((a, b) => {
      const af = String(a[sort.field] ?? "");
      const bf = String(b[sort.field] ?? "");

      // Date fields: compare as timestamps
      if (sort.field === "created_at" || sort.field === "updated_at") {
        const diff =
          new Date(af).getTime() - new Date(bf).getTime();
        return sort.direction === "asc" ? diff : -diff;
      }

      return compareValues(af, bf, sort.direction);
    });
  }, [servers, sort]);

  function SortIcon({ field }: { field: SortField }) {
    if (sort.field !== field) {
      return <ArrowUpDown className="ml-1 inline h-3 w-3 text-muted-foreground/50" />;
    }
    return sort.direction === "asc" ? (
      <ArrowUp className="ml-1 inline h-3 w-3" />
    ) : (
      <ArrowDown className="ml-1 inline h-3 w-3" />
    );
  }

  // Empty state
  if (servers.length === 0) {
    return (
      <div
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border border-dashed py-16",
          className
        )}
      >
        <Server className="h-10 w-10 text-muted-foreground/40" />
        <h3 className="mt-4 text-lg font-medium">No requests found</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          No server requests match the current filters.
        </p>
      </div>
    );
  }

  return (
    <div className={cn("rounded-lg border", className)}>
      <Table>
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead>
              <button
                type="button"
                onClick={() => toggleSort("server_name")}
                className="inline-flex items-center font-medium hover:text-foreground transition-colors"
              >
                Server Name
                <SortIcon field="server_name" />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                onClick={() => toggleSort("environment")}
                className="inline-flex items-center font-medium hover:text-foreground transition-colors"
              >
                Environment
                <SortIcon field="environment" />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                onClick={() => toggleSort("os_type")}
                className="inline-flex items-center font-medium hover:text-foreground transition-colors"
              >
                OS
                <SortIcon field="os_type" />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                onClick={() => toggleSort("status")}
                className="inline-flex items-center font-medium hover:text-foreground transition-colors"
              >
                Status
                <SortIcon field="status" />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                onClick={() => toggleSort("created_at")}
                className="inline-flex items-center font-medium hover:text-foreground transition-colors"
              >
                Created
                <SortIcon field="created_at" />
              </button>
            </TableHead>
            <TableHead>
              <button
                type="button"
                onClick={() => toggleSort("updated_at")}
                className="inline-flex items-center font-medium hover:text-foreground transition-colors"
              >
                Updated
                <SortIcon field="updated_at" />
              </button>
            </TableHead>
            <TableHead className="w-[60px]">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {sorted.map((server) => (
            <TableRow
              key={server.id}
              onClick={() => router.push(`/dashboard/requests/${server.id}`)}
              className="cursor-pointer"
            >
              <TableCell className="font-medium">
                {server.server_name}
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="capitalize">
                  {server.environment}
                </Badge>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {OS_DISPLAY[server.os_type] ?? server.os_type}
              </TableCell>
              <TableCell>
                <StatusBadge status={server.status} />
              </TableCell>
              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                {formatDistanceToNow(new Date(server.created_at), {
                  addSuffix: true,
                })}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                {formatDistanceToNow(new Date(server.updated_at), {
                  addSuffix: true,
                })}
              </TableCell>
              <TableCell>
                <ExternalLink className="h-4 w-4 text-muted-foreground" />
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
