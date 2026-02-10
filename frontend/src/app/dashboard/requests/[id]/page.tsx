"use client";

import { useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import { useServer, useServerBuildSteps } from "@/lib/api/hooks";
import type { ServerStatus } from "@/lib/api/types";
import { PipelineVisualization } from "@/components/request-tracker/pipeline-visualization";
import { BuildStepCard } from "@/components/request-tracker/build-step-card";
import { StatusTimeline, type TimelineEntry } from "@/components/request-tracker/status-timeline";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import {
  ArrowLeft,
  AlertCircle,
  Globe,
  HardDrive,
  MapPin,
  Monitor,
  Network,
  Server,
  Tag,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Status styling
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
  decommissioning: { label: "Decommissioning", variant: "warning" },
  decommissioned: { label: "Decommissioned", variant: "secondary" },
};

const OS_DISPLAY: Record<string, string> = {
  windows_2022: "Windows Server 2022",
  windows_2019: "Windows Server 2019",
  amazon_linux_2023: "Amazon Linux 2023",
  ubuntu_2204: "Ubuntu 22.04 LTS",
  rhel_9: "RHEL 9",
};

const SIZE_DISPLAY: Record<string, string> = {
  small: "Small",
  medium: "Medium",
  large: "Large",
  xl: "XL",
};

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

/**
 * Request detail page with the pipeline visualization as its centrepiece.
 *
 * Auto-refreshes every 5 seconds while the build is in progress (handled by
 * the `useServer` and `useServerBuildSteps` hooks).
 */
export default function RequestDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const {
    data: server,
    isLoading: serverLoading,
    isError: serverError,
    error: serverErr,
  } = useServer(id);

  const {
    data: steps,
    isLoading: stepsLoading,
    isError: stepsError,
  } = useServerBuildSteps(id);

  // Build timeline entries from build steps
  const timelineEntries: TimelineEntry[] = useMemo(() => {
    if (!steps) return [];
    const entries: TimelineEntry[] = [];

    for (const step of steps) {
      if (step.started_at) {
        entries.push({
          timestamp: step.started_at,
          status: "in_progress",
          message: `${stepDisplayName(step.step_name)} started`,
        });
      }
      if (step.completed_at && step.status === "completed") {
        entries.push({
          timestamp: step.completed_at,
          status: "completed",
          message: `${stepDisplayName(step.step_name)} completed successfully`,
        });
      }
      if (step.completed_at && step.status === "failed") {
        entries.push({
          timestamp: step.completed_at,
          status: "failed",
          message: `${stepDisplayName(step.step_name)} failed${step.error_message ? `: ${step.error_message}` : ""}`,
        });
      }
    }

    // Add server-level status entries
    if (server) {
      entries.push({
        timestamp: server.created_at,
        status: "pending",
        message: "Server request created",
      });
      if (server.status === "ready") {
        entries.push({
          timestamp: server.updated_at,
          status: "ready",
          message: "Server is ready and operational",
        });
      }
    }

    return entries;
  }, [steps, server]);

  const sortedSteps = useMemo(() => {
    if (!steps) return [];
    return [...steps].sort((a, b) => a.step_order - b.step_order);
  }, [steps]);

  const isLoading = serverLoading || stepsLoading;
  const statusConfig = server
    ? STATUS_BADGE_CONFIG[server.status]
    : null;

  return (
    <div className="space-y-8">
      {/* Back button */}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.push("/requests")}
        className="gap-1.5 text-muted-foreground hover:text-foreground -ml-2"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Requests
      </Button>

      {/* Error state */}
      {serverError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Failed to load server request
            </p>
            <p className="mt-0.5 text-xs text-red-700 dark:text-red-400">
              {serverErr instanceof Error
                ? serverErr.message
                : "Server request not found or an unexpected error occurred."}
            </p>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="space-y-6">
          <div className="space-y-2">
            <Skeleton className="h-9 w-[300px]" />
            <Skeleton className="h-5 w-[200px]" />
          </div>
          <Skeleton className="h-[200px] w-full rounded-lg" />
          <div className="space-y-3">
            <Skeleton className="h-[80px] w-full rounded-lg" />
            <Skeleton className="h-[80px] w-full rounded-lg" />
            <Skeleton className="h-[80px] w-full rounded-lg" />
          </div>
        </div>
      )}

      {/* Server loaded */}
      {server && !isLoading && (
        <>
          {/* ---------- Server info header ---------- */}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-3xl font-bold tracking-tight">
                  {server.server_name}
                </h1>
                {statusConfig && (
                  <Badge variant={statusConfig.variant} className="text-sm">
                    {statusConfig.label}
                  </Badge>
                )}
              </div>
              {server.status_message && (
                <p className="mt-1 text-sm text-muted-foreground">
                  {server.status_message}
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
              <InfoChip icon={Monitor} label={OS_DISPLAY[server.os_type] ?? server.os_type} />
              <InfoChip icon={HardDrive} label={SIZE_DISPLAY[server.instance_size] ?? server.instance_size} />
              <InfoChip icon={MapPin} label={server.region} />
              <InfoChip icon={Tag} label={server.environment} />
            </div>
          </div>

          {/* ---------- Pipeline visualization (centrepiece) ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Build Pipeline</CardTitle>
              <CardDescription>
                Real-time visualization of the server provisioning pipeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <PipelineVisualization steps={sortedSteps} />
            </CardContent>
          </Card>

          {/* ---------- Build step details ---------- */}
          <div className="space-y-3">
            <h2 className="text-lg font-semibold">Build Steps</h2>
            {stepsError && (
              <p className="text-sm text-red-500">
                Failed to load build steps.
              </p>
            )}
            {sortedSteps.length === 0 && !stepsError && (
              <p className="text-sm text-muted-foreground">
                No build steps have been recorded yet.
              </p>
            )}
            {sortedSteps.map((step) => (
              <BuildStepCard key={step.id} step={step} />
            ))}
          </div>

          {/* ---------- Two-column: Server Details + Status Timeline ---------- */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* Server details */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Server Details</CardTitle>
                <CardDescription>
                  Infrastructure and connectivity information
                </CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="space-y-4">
                  <DetailRow
                    icon={Server}
                    label="AWS Instance ID"
                    value={server.aws_instance_id}
                  />
                  <DetailRow
                    icon={Network}
                    label="Private IP"
                    value={server.private_ip}
                  />
                  <DetailRow
                    icon={Globe}
                    label="Public IP"
                    value={server.public_ip}
                  />
                  <DetailRow
                    icon={Globe}
                    label="DNS Name"
                    value={server.dns_name}
                  />
                  <DetailRow
                    icon={Tag}
                    label="Puppet Certname"
                    value={server.puppet_certname}
                  />
                  <DetailRow
                    icon={Tag}
                    label="Puppet Status"
                    value={server.puppet_last_report_status}
                  />
                </dl>
              </CardContent>
            </Card>

            {/* Status timeline */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Status History</CardTitle>
                <CardDescription>
                  Timeline of status changes and events
                </CardDescription>
              </CardHeader>
              <CardContent>
                <StatusTimeline entries={timelineEntries} />
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function InfoChip({
  icon: Icon,
  label,
}: {
  icon: React.ElementType;
  label: string;
}) {
  return (
    <div className="inline-flex items-center gap-1.5 rounded-md border bg-muted/50 px-2.5 py-1 text-xs font-medium">
      <Icon className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}

function DetailRow({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ElementType;
  label: string;
  value: string | null;
}) {
  return (
    <div className="flex items-start gap-3">
      <Icon className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
      <div className="min-w-0">
        <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
        <dd className="mt-0.5 text-sm break-all">
          {value ?? (
            <span className="text-muted-foreground italic">Not available yet</span>
          )}
        </dd>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step name formatting
// ---------------------------------------------------------------------------

const STEP_DISPLAY_NAMES: Record<string, string> = {
  terraform_plan: "Terraform Plan",
  terraform_apply: "Terraform Apply",
  awx_configure: "AWX Configuration",
  puppet_enroll: "Puppet Enrollment",
  validation: "Validation",
};

function stepDisplayName(name: string): string {
  return STEP_DISPLAY_NAMES[name] ?? name;
}
