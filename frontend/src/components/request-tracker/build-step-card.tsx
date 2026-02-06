"use client";

import { useState } from "react";
import { formatDistanceStrict } from "date-fns";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { LogViewer } from "./log-viewer";
import type { BuildStep, BuildStepStatus } from "@/lib/api/types";
import {
  ChevronDown,
  Clock,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Circle,
} from "lucide-react";

interface BuildStepCardProps {
  step: BuildStep;
  className?: string;
}

const STATUS_CONFIG: Record<
  BuildStepStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info";
    icon: React.ElementType;
    iconClass: string;
  }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: Circle,
    iconClass: "text-zinc-400",
  },
  in_progress: {
    label: "Running",
    variant: "info",
    icon: Loader2,
    iconClass: "text-blue-500 animate-spin",
  },
  completed: {
    label: "Completed",
    variant: "success",
    icon: CheckCircle2,
    iconClass: "text-green-500",
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: AlertCircle,
    iconClass: "text-red-500",
  },
};

const STEP_DISPLAY_NAMES: Record<string, string> = {
  terraform_plan: "Terraform Plan",
  terraform_apply: "Terraform Apply",
  awx_configure: "AWX Configuration",
  puppet_enroll: "Puppet Enrollment",
  validation: "Validation",
};

function getDuration(step: BuildStep): string | null {
  if (!step.started_at) return null;
  const start = new Date(step.started_at);
  const end = step.completed_at ? new Date(step.completed_at) : new Date();
  return formatDistanceStrict(start, end);
}

/**
 * An expandable card for a single build pipeline step.
 * Collapsed: step name, status badge, duration.
 * Expanded: full output log and error messages.
 */
export function BuildStepCard({ step, className }: BuildStepCardProps) {
  const [expanded, setExpanded] = useState(
    step.status === "failed" || step.status === "in_progress"
  );

  const config = STATUS_CONFIG[step.status];
  const Icon = config.icon;
  const duration = getDuration(step);
  const displayName =
    STEP_DISPLAY_NAMES[step.step_name] ?? step.step_name;

  return (
    <div
      className={cn(
        "rounded-lg border bg-card text-card-foreground shadow-sm transition-all",
        step.status === "failed" && "border-red-200 dark:border-red-900/50",
        step.status === "in_progress" &&
          "border-blue-200 dark:border-blue-900/50",
        className
      )}
    >
      {/* Collapsed header — always visible */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 p-4 text-left transition-colors hover:bg-muted/50"
      >
        <Icon className={cn("h-5 w-5 flex-shrink-0", config.iconClass)} />

        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium">{displayName}</span>
        </div>

        {duration && (
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            {duration}
          </div>
        )}

        <Badge variant={config.variant} className="flex-shrink-0">
          {config.label}
        </Badge>

        <ChevronDown
          className={cn(
            "h-4 w-4 flex-shrink-0 text-muted-foreground transition-transform duration-200",
            expanded && "rotate-180"
          )}
        />
      </button>

      {/* Expandable content */}
      <div
        className={cn(
          "grid transition-all duration-200 ease-in-out",
          expanded ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <div className="border-t px-4 pb-4 pt-3 space-y-3">
            {/* Error message */}
            {step.error_message && (
              <div className="flex items-start gap-2 rounded-md bg-red-50 p-3 dark:bg-red-950/30">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-red-800 dark:text-red-300">
                    Error
                  </p>
                  <p className="mt-0.5 text-xs text-red-700 dark:text-red-400 whitespace-pre-wrap break-words">
                    {step.error_message}
                  </p>
                </div>
              </div>
            )}

            {/* Log output */}
            {step.output_log ? (
              <LogViewer content={step.output_log} maxHeight="20rem" />
            ) : (
              <p className="text-sm text-muted-foreground">
                {step.status === "pending"
                  ? "This step has not started yet."
                  : "No log output recorded for this step."}
              </p>
            )}

            {/* Timestamps */}
            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted-foreground">
              {step.started_at && (
                <span>
                  Started:{" "}
                  {new Date(step.started_at).toLocaleString()}
                </span>
              )}
              {step.completed_at && (
                <span>
                  Completed:{" "}
                  {new Date(step.completed_at).toLocaleString()}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
