"use client";

import { useState } from "react";
import { useServers } from "@/lib/api/hooks";
import type { ServerStatus } from "@/lib/api/types";
import { RequestListTable } from "@/components/request-tracker/request-list-table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { AlertCircle, Server } from "lucide-react";

// ---------------------------------------------------------------------------
// Filter tabs configuration
// ---------------------------------------------------------------------------

type FilterTab = "all" | "pending" | "in_progress" | "ready" | "failed";

const IN_PROGRESS_STATUSES: ServerStatus[] = [
  "approved",
  "provisioning",
  "configuring",
  "validating",
];

function filterByTab(tab: FilterTab) {
  return function (status: ServerStatus): boolean {
    switch (tab) {
      case "all":
        return true;
      case "pending":
        return status === "pending";
      case "in_progress":
        return IN_PROGRESS_STATUSES.includes(status);
      case "ready":
        return status === "ready";
      case "failed":
        return status === "failed";
    }
  };
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * Server Requests list page.
 *
 * Displays a filterable, sortable table of all server provisioning requests.
 * Auto-refreshes every 10 seconds (handled inside `useServers` hook when
 * in-progress servers are present).
 */
export default function RequestsPage() {
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const { data, isLoading, isError, error } = useServers();

  const servers = data?.servers ?? [];
  const filtered = servers.filter((s) => filterByTab(activeTab)(s.status));

  // Count badges for each tab
  const counts = {
    all: servers.length,
    pending: servers.filter((s) => s.status === "pending").length,
    in_progress: servers.filter((s) => IN_PROGRESS_STATUSES.includes(s.status))
      .length,
    ready: servers.filter((s) => s.status === "ready").length,
    failed: servers.filter((s) => s.status === "failed").length,
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Server Requests</h1>
        <p className="mt-1 text-muted-foreground">
          Track and manage server provisioning requests across all environments.
        </p>
      </div>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-4">
          <Skeleton className="h-10 w-[400px]" />
          <Skeleton className="h-[400px] w-full rounded-lg" />
        </div>
      )}

      {/* Error state */}
      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Failed to load server requests
            </p>
            <p className="mt-0.5 text-xs text-red-700 dark:text-red-400">
              {error instanceof Error ? error.message : "An unexpected error occurred."}
            </p>
          </div>
        </div>
      )}

      {/* Data loaded successfully */}
      {!isLoading && !isError && (
        <Tabs
          value={activeTab}
          onValueChange={(val) => setActiveTab(val as FilterTab)}
        >
          <TabsList>
            <TabsTrigger value="all" className="gap-1.5">
              All
              <CountBadge count={counts.all} active={activeTab === "all"} />
            </TabsTrigger>
            <TabsTrigger value="pending" className="gap-1.5">
              Pending
              <CountBadge
                count={counts.pending}
                active={activeTab === "pending"}
              />
            </TabsTrigger>
            <TabsTrigger value="in_progress" className="gap-1.5">
              In Progress
              <CountBadge
                count={counts.in_progress}
                active={activeTab === "in_progress"}
              />
            </TabsTrigger>
            <TabsTrigger value="ready" className="gap-1.5">
              Ready
              <CountBadge
                count={counts.ready}
                active={activeTab === "ready"}
              />
            </TabsTrigger>
            <TabsTrigger value="failed" className="gap-1.5">
              Failed
              <CountBadge
                count={counts.failed}
                active={activeTab === "failed"}
              />
            </TabsTrigger>
          </TabsList>

          {/* All tabs share the same table; filtering is done at the data level */}
          <TabsContent value={activeTab} className="mt-4">
            <RequestListTable servers={filtered} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Count badge (small number next to tab label)
// ---------------------------------------------------------------------------

function CountBadge({ count, active }: { count: number; active: boolean }) {
  if (count === 0) return null;
  return (
    <span
      className={
        active
          ? "ml-1 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary px-1.5 text-[10px] font-semibold text-primary-foreground"
          : "ml-1 inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-muted px-1.5 text-[10px] font-semibold text-muted-foreground"
      }
    >
      {count}
    </span>
  );
}
