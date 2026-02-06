'use client';

import {
  AlertTriangle,
  Pencil,
  DollarSign,
  Server,
  Shield,
  Package,
  HardDrive,
  Tag,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { useServerForm } from '@/hooks/use-server-form';

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

const OS_LABELS: Record<string, string> = {
  windows_2022: 'Windows Server 2022',
  windows_2019: 'Windows Server 2019',
  amazon_linux_2023: 'Amazon Linux 2023',
  ubuntu_2204: 'Ubuntu 22.04 LTS',
  rhel_9: 'Red Hat Enterprise Linux 9',
};

const SIZE_LABELS: Record<string, string> = {
  small: 'Small (t3.medium -- 2 vCPU / 4 GB)',
  medium: 'Medium (t3.xlarge -- 4 vCPU / 16 GB)',
  large: 'Large (m5.2xlarge -- 8 vCPU / 32 GB)',
  xl: 'X-Large (m5.4xlarge -- 16 vCPU / 64 GB)',
};

const PROFILE_LABELS: Record<string, string> = {
  web_facing: 'Web Facing',
  internal_only: 'Internal Only',
  database: 'Database',
  custom: 'Custom',
};

const ENV_LABELS: Record<string, string> = {
  dev: 'Development',
  staging: 'Staging',
  production: 'Production',
};

const ROLE_LABELS: Record<string, string> = {
  base: 'Base',
  web_server: 'Web Server',
  db_server: 'Database Server',
  app_server: 'Application Server',
  dev_workstation: 'Dev Workstation',
};

// ---------------------------------------------------------------------------
// Reusable row
// ---------------------------------------------------------------------------

function ReviewRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-1.5">
      <span className="shrink-0 text-sm text-muted-foreground">{label}</span>
      <span className="text-right text-sm font-medium">{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface StepReviewProps {
  onGoToStep: (step: number) => void;
}

export function StepReview({ onGoToStep }: StepReviewProps) {
  const form = useServerForm();

  const isProduction = form.environment === 'production';
  const isXl = form.instance_size === 'xl';
  const requiresApproval = isProduction || isXl;

  return (
    <div className="space-y-6">
      {/* Approval warning */}
      {requiresApproval && (
        <div className="flex items-start gap-3 rounded-lg border border-amber-300 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" />
          <div>
            <p className="text-sm font-semibold text-amber-800 dark:text-amber-200">
              Approval Required
            </p>
            <p className="mt-0.5 text-sm text-amber-700 dark:text-amber-300">
              {isProduction && isXl
                ? 'Production environment and X-Large instance size both require manager approval before provisioning begins.'
                : isProduction
                  ? 'Production environment requests require manager approval before provisioning begins.'
                  : 'X-Large instance requests require manager approval before provisioning begins.'}
            </p>
          </div>
        </div>
      )}

      {/* Section 1: Environment & OS */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Environment & OS</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => onGoToStep(0)}
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
        </CardHeader>
        <CardContent className="space-y-1 pt-0">
          <ReviewRow
            label="Environment"
            value={
              <Badge
                variant={
                  form.environment === 'production'
                    ? 'destructive'
                    : form.environment === 'staging'
                      ? 'warning'
                      : 'info'
                }
              >
                {ENV_LABELS[form.environment] ?? form.environment}
              </Badge>
            }
          />
          <ReviewRow
            label="Operating System"
            value={OS_LABELS[form.os_type] ?? form.os_type}
          />
          <ReviewRow label="Region" value={form.region} />
        </CardContent>
      </Card>

      {/* Section 2: Instance Config */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Instance Configuration</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => onGoToStep(1)}
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
        </CardHeader>
        <CardContent className="space-y-1 pt-0">
          <ReviewRow
            label="Instance Size"
            value={SIZE_LABELS[form.instance_size] ?? form.instance_size}
          />
          <ReviewRow
            label="VPC"
            value={form.vpc_id || <span className="italic text-muted-foreground">Not set</span>}
          />
          <ReviewRow
            label="Subnet"
            value={form.subnet_id || <span className="italic text-muted-foreground">Not set</span>}
          />
          <ReviewRow
            label="Server Name"
            value={
              form.server_name || (
                <span className="italic text-muted-foreground">Auto-generated</span>
              )
            }
          />
        </CardContent>
      </Card>

      {/* Section 3: Security */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Security & Networking</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => onGoToStep(2)}
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
        </CardHeader>
        <CardContent className="space-y-1 pt-0">
          <ReviewRow
            label="Security Profile"
            value={PROFILE_LABELS[form.security_profile] ?? form.security_profile}
          />
          <ReviewRow
            label="Domain Join"
            value={form.domain_join ? 'Yes' : 'No'}
          />
          {Object.keys(form.tags).length > 0 && (
            <>
              <Separator className="my-2" />
              <div className="space-y-1.5">
                <span className="text-sm text-muted-foreground">Tags</span>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(form.tags).map(([key, value]) => (
                    <Badge key={key} variant="outline" className="font-mono text-xs">
                      <Tag className="mr-1 h-3 w-3" />
                      {key}={value}
                    </Badge>
                  ))}
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Section 4: Software & Configuration */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-3">
          <div className="flex items-center gap-2">
            <Package className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Software & Configuration</CardTitle>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 gap-1.5 text-xs"
            onClick={() => onGoToStep(3)}
          >
            <Pencil className="h-3 w-3" />
            Edit
          </Button>
        </CardHeader>
        <CardContent className="space-y-1 pt-0">
          <ReviewRow
            label="Puppet Role"
            value={ROLE_LABELS[form.puppet_role] ?? form.puppet_role}
          />
          <ReviewRow
            label="Software Packages"
            value={
              form.software_packages.length > 0 ? (
                <div className="flex flex-wrap justify-end gap-1">
                  {form.software_packages.map((pkg) => (
                    <Badge key={pkg} variant="secondary" className="text-xs">
                      {pkg}
                    </Badge>
                  ))}
                </div>
              ) : (
                <span className="italic text-muted-foreground">None</span>
              )
            }
          />

          {form.additional_storage.length > 0 && (
            <>
              <Separator className="my-2" />
              <div className="space-y-2">
                <span className="text-sm text-muted-foreground">
                  Additional Storage
                </span>
                {form.additional_storage.map((vol, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm"
                  >
                    <HardDrive className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="font-medium">
                      {vol.drive_letter
                        ? `${vol.drive_letter}:\\`
                        : vol.mount_point || '/data'}
                    </span>
                    <span className="text-muted-foreground">--</span>
                    <span>{vol.size_gb} GB</span>
                    <Badge variant="outline" className="ml-auto text-xs">
                      {vol.volume_type}
                    </Badge>
                  </div>
                ))}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Cost estimation placeholder */}
      <Card className="border-dashed">
        <CardContent className="flex items-center gap-3 p-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
            <DollarSign className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold">Estimated Monthly Cost</p>
            <p className="text-sm text-muted-foreground">
              Coming soon -- real-time cost estimation from the AWS Pricing API.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
