"use client";

import { useMemo } from "react";
import { formatDistanceStrict } from "date-fns";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { BuildStep, BuildStepStatus } from "@/lib/api/types";
import { FileSearch, Cloud, Wrench, Shield, CheckCircle } from "lucide-react";

// ---------------------------------------------------------------------------
// Stage configuration
// ---------------------------------------------------------------------------

interface StageConfig {
  key: string;
  label: string;
  icon: React.ElementType;
}

const STAGES: StageConfig[] = [
  { key: "terraform_plan", label: "Plan", icon: FileSearch },
  { key: "terraform_apply", label: "Provision", icon: Cloud },
  { key: "awx_configure", label: "Configure", icon: Wrench },
  { key: "puppet_enroll", label: "Puppet", icon: Shield },
  { key: "validation", label: "Validate", icon: CheckCircle },
];

// Color mapping per status
const STATUS_STYLES: Record<
  BuildStepStatus,
  {
    ring: string;
    bg: string;
    iconColor: string;
    label: string;
  }
> = {
  pending: {
    ring: "ring-zinc-200 dark:ring-zinc-700",
    bg: "bg-zinc-100 dark:bg-zinc-800",
    iconColor: "text-zinc-400 dark:text-zinc-500",
    label: "Pending",
  },
  in_progress: {
    ring: "ring-blue-400 dark:ring-blue-500",
    bg: "bg-blue-50 dark:bg-blue-950",
    iconColor: "text-blue-600 dark:text-blue-400",
    label: "Running",
  },
  completed: {
    ring: "ring-green-400 dark:ring-green-500",
    bg: "bg-green-50 dark:bg-green-950",
    iconColor: "text-green-600 dark:text-green-400",
    label: "Completed",
  },
  failed: {
    ring: "ring-red-400 dark:ring-red-500",
    bg: "bg-red-50 dark:bg-red-950",
    iconColor: "text-red-600 dark:text-red-400",
    label: "Failed",
  },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStepDuration(step: BuildStep): string | null {
  if (!step.started_at) return null;
  const start = new Date(step.started_at);
  const end = step.completed_at ? new Date(step.completed_at) : new Date();
  return formatDistanceStrict(start, end);
}

function getConnectorStatus(
  leftStatus: BuildStepStatus,
  rightStatus: BuildStepStatus
): "idle" | "active" | "completed" {
  if (leftStatus === "completed" && rightStatus === "completed") return "completed";
  if (leftStatus === "completed" && rightStatus === "in_progress") return "active";
  if (leftStatus === "completed") return "completed";
  return "idle";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function PipelineNode({
  stage,
  step,
}: {
  stage: StageConfig;
  step: BuildStep | undefined;
}) {
  const status: BuildStepStatus = step?.status ?? "pending";
  const style = STATUS_STYLES[status];
  const Icon = stage.icon;
  const duration = step ? getStepDuration(step) : null;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <div className="flex flex-col items-center gap-2">
            {/* Node circle */}
            <div className="relative">
              {/* Animated pulse ring for in_progress */}
              {status === "in_progress" && (
                <div className="absolute inset-0 animate-ping rounded-full bg-blue-400/30 dark:bg-blue-500/20" />
              )}
              {/* Glow effect for in_progress */}
              {status === "in_progress" && (
                <div className="absolute -inset-1 rounded-full bg-blue-400/20 blur-sm dark:bg-blue-500/15" />
              )}
              <div
                className={cn(
                  "relative flex h-14 w-14 items-center justify-center rounded-full ring-2 transition-all duration-500",
                  style.ring,
                  style.bg
                )}
              >
                <Icon
                  className={cn(
                    "h-6 w-6 transition-colors duration-500",
                    style.iconColor,
                    status === "in_progress" && "animate-pulse"
                  )}
                />
              </div>
            </div>

            {/* Label */}
            <span
              className={cn(
                "text-xs font-medium transition-colors duration-300",
                status === "pending"
                  ? "text-muted-foreground"
                  : status === "failed"
                  ? "text-red-600 dark:text-red-400"
                  : status === "in_progress"
                  ? "text-blue-600 dark:text-blue-400"
                  : "text-foreground"
              )}
            >
              {stage.label}
            </span>

            {/* Duration */}
            <span className="h-4 text-[11px] text-muted-foreground">
              {duration ?? ""}
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="text-xs">
          <p className="font-medium">{stage.label}</p>
          <p className="text-muted-foreground">{style.label}</p>
          {duration && <p className="text-muted-foreground">{duration}</p>}
          {step?.error_message && (
            <p className="mt-1 max-w-[200px] text-red-500 break-words">
              {step.error_message}
            </p>
          )}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function PipelineConnector({
  status,
}: {
  status: "idle" | "active" | "completed";
}) {
  return (
    <div className="relative flex flex-1 items-center self-start mt-7 mx-1">
      {/* Background track */}
      <div className="h-0.5 w-full rounded-full bg-zinc-200 dark:bg-zinc-700" />

      {/* Filled overlay */}
      <div
        className={cn(
          "absolute inset-y-0 left-0 h-0.5 rounded-full transition-all duration-700 ease-out",
          status === "completed" && "w-full bg-green-400 dark:bg-green-500",
          status === "active" && "w-1/2 bg-blue-400 dark:bg-blue-500",
          status === "idle" && "w-0"
        )}
      />

      {/* Animated shimmer for active connectors */}
      {status === "active" && (
        <div className="absolute inset-y-0 left-0 h-0.5 w-1/2 overflow-hidden rounded-full">
          <div className="h-full w-full animate-shimmer bg-gradient-to-r from-transparent via-blue-300/60 to-transparent dark:via-blue-400/40" />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

interface PipelineVisualizationProps {
  steps: BuildStep[];
  className?: string;
}

/**
 * Horizontal pipeline visualization showing the 5 build stages as connected
 * nodes. Each stage is color-coded by status with animated transitions,
 * connecting lines that fill as stages complete, and an overall progress bar.
 */
export function PipelineVisualization({
  steps,
  className,
}: PipelineVisualizationProps) {
  // Build a map from step_name -> BuildStep for quick lookup
  const stepMap = useMemo(() => {
    const map = new Map<string, BuildStep>();
    steps.forEach((s) => map.set(s.step_name, s));
    return map;
  }, [steps]);

  // Calculate overall progress percentage
  const progress = useMemo(() => {
    if (steps.length === 0) return 0;
    const completed = steps.filter((s) => s.status === "completed").length;
    const inProgress = steps.filter((s) => s.status === "in_progress").length;
    // Count in_progress as half completion for the progress bar
    return Math.round(((completed + inProgress * 0.5) / STAGES.length) * 100);
  }, [steps]);

  // Determine if the pipeline has failed
  const hasFailed = steps.some((s) => s.status === "failed");
  // Determine if all complete
  const allComplete =
    steps.length > 0 && steps.every((s) => s.status === "completed");

  return (
    <div className={cn("space-y-6", className)}>
      {/* Overall progress bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">
            {hasFailed
              ? "Build Failed"
              : allComplete
              ? "Build Complete"
              : "Build Progress"}
          </span>
          <span
            className={cn(
              "text-xs font-medium",
              hasFailed
                ? "text-red-600 dark:text-red-400"
                : allComplete
                ? "text-green-600 dark:text-green-400"
                : "text-muted-foreground"
            )}
          >
            {progress}%
          </span>
        </div>
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-secondary">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-700 ease-out",
              hasFailed
                ? "bg-red-500"
                : allComplete
                ? "bg-green-500"
                : "bg-blue-500"
            )}
            style={{ width: `${progress}%` }}
          />
          {/* Animated pulse on the progress edge while in progress */}
          {!hasFailed && !allComplete && progress > 0 && (
            <div
              className="absolute top-0 h-full w-4 animate-pulse rounded-full bg-blue-300/50 dark:bg-blue-400/30"
              style={{ left: `calc(${progress}% - 8px)` }}
            />
          )}
        </div>
      </div>

      {/* Pipeline stages */}
      <div className="flex items-start justify-between px-2">
        {STAGES.map((stage, index) => {
          const step = stepMap.get(stage.key);
          const nextStage = STAGES[index + 1];
          const nextStep = nextStage ? stepMap.get(nextStage.key) : undefined;

          return (
            <div key={stage.key} className="contents">
              <PipelineNode stage={stage} step={step} />

              {index < STAGES.length - 1 && (
                <PipelineConnector
                  status={getConnectorStatus(
                    step?.status ?? "pending",
                    nextStep?.status ?? "pending"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>

    </div>
  );
}
