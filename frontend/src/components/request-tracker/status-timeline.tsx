"use client";

import { formatDistanceToNow } from "date-fns";
import { cn } from "@/lib/utils";
import type { ServerStatus, BuildStepStatus } from "@/lib/api/types";

export interface TimelineEntry {
  timestamp: string;
  status: ServerStatus | BuildStepStatus | string;
  message?: string;
}

interface StatusTimelineProps {
  entries: TimelineEntry[];
  className?: string;
}

const STATUS_DOT_COLORS: Record<string, string> = {
  // Server statuses
  pending: "bg-zinc-400",
  approved: "bg-blue-400",
  provisioning: "bg-blue-500",
  configuring: "bg-indigo-500",
  validating: "bg-purple-500",
  ready: "bg-green-500",
  failed: "bg-red-500",
  decommissioning: "bg-orange-500",
  decommissioned: "bg-zinc-500",
  // Build step statuses
  in_progress: "bg-blue-500",
  completed: "bg-green-500",
};

const STATUS_LABELS: Record<string, string> = {
  pending: "Pending",
  approved: "Approved",
  provisioning: "Provisioning",
  configuring: "Configuring",
  validating: "Validating",
  ready: "Ready",
  failed: "Failed",
  decommissioning: "Decommissioning",
  decommissioned: "Decommissioned",
  in_progress: "In Progress",
  completed: "Completed",
};

/**
 * A vertical timeline showing status transitions, most recent at the top.
 * Each entry displays a color-coded dot, relative timestamp, status label,
 * and an optional message.
 */
export function StatusTimeline({ entries, className }: StatusTimelineProps) {
  // Sort most-recent-first
  const sorted = [...entries].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  if (sorted.length === 0) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        No status history available.
      </p>
    );
  }

  return (
    <div className={cn("relative", className)}>
      {sorted.map((entry, index) => {
        const isLast = index === sorted.length - 1;
        const dotColor =
          STATUS_DOT_COLORS[entry.status] ?? "bg-zinc-400";
        const label =
          STATUS_LABELS[entry.status] ?? entry.status;

        return (
          <div key={index} className="relative flex gap-4 pb-6 last:pb-0">
            {/* Vertical connector line */}
            {!isLast && (
              <div className="absolute left-[7px] top-4 h-full w-px bg-border" />
            )}

            {/* Dot */}
            <div className="relative z-10 mt-1 flex-shrink-0">
              <div
                className={cn(
                  "h-[15px] w-[15px] rounded-full border-2 border-background shadow-sm",
                  dotColor
                )}
              />
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">{label}</span>
                <span className="text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(entry.timestamp), {
                    addSuffix: true,
                  })}
                </span>
              </div>
              {entry.message && (
                <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                  {entry.message}
                </p>
              )}
              <p className="mt-0.5 text-[11px] text-muted-foreground/60">
                {new Date(entry.timestamp).toLocaleString()}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
