'use client';

import type { BuildStepStatus } from '@/lib/api/types';
import {
  Shield,
  Wrench,
  CloudOff,
  Globe,
  CheckCircle2,
  Circle,
  XCircle,
  Loader2,
  SkipForward,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type DecommissionStageStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'skipped'
  | 'failed';

export interface DecommissionStage {
  id: string;
  name: string;
  status: DecommissionStageStatus;
  started_at?: string | null;
  completed_at?: string | null;
  error_message?: string | null;
}

// ---------------------------------------------------------------------------
// Stage definitions
// ---------------------------------------------------------------------------

const STAGE_META: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; label: string }
> = {
  puppet_purge: { icon: Shield, label: 'Puppet Purge' },
  awx_decommission: { icon: Wrench, label: 'AWX Decommission' },
  terraform_destroy: { icon: CloudOff, label: 'Terraform Destroy' },
  dns_cleanup: { icon: Globe, label: 'DNS Cleanup' },
};

const STAGE_ORDER = [
  'puppet_purge',
  'awx_decommission',
  'terraform_destroy',
  'dns_cleanup',
];

// ---------------------------------------------------------------------------
// Status styling
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<
  DecommissionStageStatus,
  {
    statusIcon: React.ComponentType<{ className?: string }>;
    color: string;
    bgColor: string;
    borderColor: string;
    label: string;
  }
> = {
  pending: {
    statusIcon: Circle,
    color: 'text-muted-foreground',
    bgColor: 'bg-muted',
    borderColor: 'border-border',
    label: 'Pending',
  },
  in_progress: {
    statusIcon: Loader2,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950/30',
    borderColor: 'border-blue-200 dark:border-blue-800',
    label: 'In Progress',
  },
  completed: {
    statusIcon: CheckCircle2,
    color: 'text-green-600 dark:text-green-400',
    bgColor: 'bg-green-50 dark:bg-green-950/30',
    borderColor: 'border-green-200 dark:border-green-800',
    label: 'Completed',
  },
  skipped: {
    statusIcon: SkipForward,
    color: 'text-orange-600 dark:text-orange-400',
    bgColor: 'bg-orange-50 dark:bg-orange-950/30',
    borderColor: 'border-orange-200 dark:border-orange-800',
    label: 'Skipped',
  },
  failed: {
    statusIcon: XCircle,
    color: 'text-red-600 dark:text-red-400',
    bgColor: 'bg-red-50 dark:bg-red-950/30',
    borderColor: 'border-red-200 dark:border-red-800',
    label: 'Failed',
  },
};

// ---------------------------------------------------------------------------
// Helper: derive decommission stages from build steps
// ---------------------------------------------------------------------------

/**
 * Maps backend build step data to decommission stage display objects.
 * If explicit stages are not provided, creates default pending stages.
 */
export function deriveDecommissionStages(
  buildSteps?: Array<{
    step_name: string;
    status: BuildStepStatus;
    started_at?: string | null;
    completed_at?: string | null;
    error_message?: string | null;
  }>,
): DecommissionStage[] {
  if (!buildSteps || buildSteps.length === 0) {
    // Return default pending stages
    return STAGE_ORDER.map((id) => ({
      id,
      name: STAGE_META[id]?.label ?? id,
      status: 'pending' as DecommissionStageStatus,
    }));
  }

  // Map step names to our stage IDs (handle various naming conventions)
  const stepMap = new Map<string, (typeof buildSteps)[number]>();
  for (const step of buildSteps) {
    const normalized = step.step_name
      .toLowerCase()
      .replace(/[\s-]+/g, '_');

    for (const stageId of STAGE_ORDER) {
      if (normalized.includes(stageId) || stageId.includes(normalized)) {
        stepMap.set(stageId, step);
        break;
      }
    }
  }

  return STAGE_ORDER.map((id) => {
    const step = stepMap.get(id);
    if (!step) {
      return {
        id,
        name: STAGE_META[id]?.label ?? id,
        status: 'pending' as DecommissionStageStatus,
      };
    }
    return {
      id,
      name: STAGE_META[id]?.label ?? id,
      status: step.status as DecommissionStageStatus,
      started_at: step.started_at,
      completed_at: step.completed_at,
      error_message: step.error_message,
    };
  });
}

// ---------------------------------------------------------------------------
// DecommissionTracker component
// ---------------------------------------------------------------------------

interface DecommissionTrackerProps {
  /** Pre-built stages to display. If not provided, uses buildSteps to derive them. */
  stages?: DecommissionStage[];
  /** Raw build step data from the API (used if stages prop is not provided). */
  buildSteps?: Array<{
    step_name: string;
    status: BuildStepStatus;
    started_at?: string | null;
    completed_at?: string | null;
    error_message?: string | null;
  }>;
}

export function DecommissionTracker({
  stages: stagesProp,
  buildSteps,
}: DecommissionTrackerProps) {
  const stages = stagesProp ?? deriveDecommissionStages(buildSteps);

  const completedCount = stages.filter(
    (s) => s.status === 'completed' || s.status === 'skipped',
  ).length;
  const hasFailed = stages.some((s) => s.status === 'failed');
  const isComplete = completedCount === stages.length;

  return (
    <div className="space-y-4">
      {/* Progress summary */}
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">
          {hasFailed
            ? 'Decommission failed'
            : isComplete
              ? 'Decommission complete'
              : 'Decommission in progress'}
        </span>
        <span className="text-muted-foreground">
          {completedCount} / {stages.length} steps
        </span>
      </div>

      {/* Progress bar */}
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={`h-full transition-all duration-500 ease-out rounded-full ${
            hasFailed
              ? 'bg-red-500'
              : isComplete
                ? 'bg-green-500'
                : 'bg-blue-500'
          }`}
          style={{
            width: `${(completedCount / stages.length) * 100}%`,
          }}
        />
      </div>

      {/* Stage timeline */}
      <div className="space-y-1">
        {stages.map((stage, index) => {
          const meta = STAGE_META[stage.id];
          const config = STATUS_CONFIG[stage.status] ?? STATUS_CONFIG.pending;
          const StageIcon = meta?.icon ?? Circle;
          const StatusIcon = config.statusIcon;
          const isLast = index === stages.length - 1;

          return (
            <div key={stage.id} className="flex gap-3">
              {/* Timeline connector */}
              <div className="flex flex-col items-center">
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full border ${config.borderColor} ${config.bgColor}`}
                >
                  <StageIcon className={`h-4 w-4 ${config.color}`} />
                </div>
                {!isLast && (
                  <div
                    className={`w-px flex-1 min-h-[16px] ${
                      stage.status === 'completed' || stage.status === 'skipped'
                        ? 'bg-green-300 dark:bg-green-700'
                        : 'bg-border'
                    }`}
                  />
                )}
              </div>

              {/* Stage content */}
              <div className="pb-4 pt-1 flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium leading-tight">
                    {stage.name}
                  </p>
                  <div className="flex items-center gap-1.5 flex-shrink-0">
                    <StatusIcon
                      className={`h-3.5 w-3.5 ${config.color} ${
                        stage.status === 'in_progress' ? 'animate-spin' : ''
                      }`}
                    />
                    <span className={`text-xs font-medium ${config.color}`}>
                      {config.label}
                    </span>
                  </div>
                </div>

                {/* Timestamps */}
                {stage.started_at && (
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {stage.completed_at
                      ? `Completed ${new Date(stage.completed_at).toLocaleString()}`
                      : `Started ${new Date(stage.started_at).toLocaleString()}`}
                  </p>
                )}

                {/* Error message */}
                {stage.error_message && (
                  <div className="mt-1.5 rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 dark:border-red-900 dark:bg-red-950/30">
                    <p className="text-xs text-red-700 dark:text-red-400">
                      {stage.error_message}
                    </p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
