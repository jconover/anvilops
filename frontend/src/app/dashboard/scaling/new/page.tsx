'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Textarea } from '@/components/ui/textarea';
import {
  useCreateScalingGroup,
  type ScalingGroupCreateRequest,
} from '@/lib/api/scaling';
import { useRegions, useVPCs, useSubnets } from '@/lib/api/regions';
import { toast } from 'sonner';
import { ArrowLeft, Layers, Loader2, Server, Settings2 } from 'lucide-react';

// ---------------------------------------------------------------------------
// Form state shape
// ---------------------------------------------------------------------------

interface FormState {
  name: string;
  description: string;
  environment: string;
  os_type: string;
  instance_size: string;
  region: string;
  vpc_id: string;
  subnet_id: string;
  puppet_role: string;
  min_instances: number;
  max_instances: number;
  desired_count: number;
  scale_up_threshold: number;
  scale_down_threshold: number;
  cooldown_seconds: number;
}

const INITIAL_STATE: FormState = {
  name: '',
  description: '',
  environment: '',
  os_type: '',
  instance_size: '',
  region: '',
  vpc_id: '',
  subnet_id: '',
  puppet_role: '',
  min_instances: 1,
  max_instances: 5,
  desired_count: 2,
  scale_up_threshold: 80,
  scale_down_threshold: 30,
  cooldown_seconds: 300,
};

// ---------------------------------------------------------------------------
// Options
// ---------------------------------------------------------------------------

const ENVIRONMENTS = [
  { value: 'dev', label: 'Development' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
];

const OS_TYPES = [
  { value: 'windows_2022', label: 'Windows Server 2022' },
  { value: 'windows_2019', label: 'Windows Server 2019' },
  { value: 'amazon_linux_2023', label: 'Amazon Linux 2023' },
  { value: 'ubuntu_2204', label: 'Ubuntu 22.04 LTS' },
  { value: 'rhel_9', label: 'RHEL 9' },
];

const INSTANCE_SIZES = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
  { value: 'xl', label: 'XL' },
];

const PUPPET_ROLES = [
  { value: 'web_server', label: 'Web Server' },
  { value: 'app_server', label: 'App Server' },
  { value: 'db_server', label: 'Database Server' },
  { value: 'dev_workstation', label: 'Dev Workstation' },
];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function NewScalingGroupPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [step, setStep] = useState<'config' | 'review'>('config');

  const createMutation = useCreateScalingGroup();

  // Region / VPC / Subnet cascading selectors
  const { data: regions } = useRegions();
  const { data: vpcs } = useVPCs(form.region || undefined);
  const { data: subnets } = useSubnets(
    form.region || undefined,
    form.vpc_id || undefined,
  );

  // Field updater helper
  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => {
      const next = { ...prev, [key]: value };
      // Reset cascading fields
      if (key === 'region') {
        next.vpc_id = '';
        next.subnet_id = '';
      }
      if (key === 'vpc_id') {
        next.subnet_id = '';
      }
      return next;
    });
  };

  const updateNumber = (key: keyof FormState, raw: string) => {
    const parsed = parseInt(raw, 10);
    if (!isNaN(parsed)) {
      update(key, parsed as never);
    }
  };

  // Validation
  const isTemplateComplete =
    form.name.trim() !== '' &&
    form.environment !== '' &&
    form.os_type !== '' &&
    form.instance_size !== '' &&
    form.region !== '' &&
    form.vpc_id !== '' &&
    form.subnet_id !== '' &&
    form.puppet_role !== '';

  const isPolicyValid =
    form.min_instances >= 0 &&
    form.max_instances >= form.min_instances &&
    form.desired_count >= form.min_instances &&
    form.desired_count <= form.max_instances &&
    form.scale_up_threshold > 0 &&
    form.scale_up_threshold <= 100 &&
    form.scale_down_threshold >= 0 &&
    form.scale_down_threshold < form.scale_up_threshold &&
    form.cooldown_seconds > 0;

  const canSubmit = isTemplateComplete && isPolicyValid;

  const handleSubmit = () => {
    if (!canSubmit) return;

    const request: ScalingGroupCreateRequest = {
      name: form.name.trim(),
      description: form.description.trim() || undefined,
      environment: form.environment,
      os_type: form.os_type,
      instance_size: form.instance_size,
      region: form.region,
      vpc_id: form.vpc_id,
      subnet_id: form.subnet_id,
      puppet_role: form.puppet_role,
      min_instances: form.min_instances,
      max_instances: form.max_instances,
      desired_count: form.desired_count,
      scale_up_threshold: form.scale_up_threshold,
      scale_down_threshold: form.scale_down_threshold,
      cooldown_seconds: form.cooldown_seconds,
    };

    createMutation.mutate(request, {
      onSuccess: (group) => {
        toast.success('Scaling group created', {
          description: `${group.name} is being provisioned with ${group.desired_count} instances.`,
        });
        router.push(`/dashboard/scaling/${group.id}`);
      },
      onError: (err) => {
        toast.error('Failed to create scaling group', {
          description: err.message ?? 'An unexpected error occurred.',
        });
      },
    });
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      {/* Page header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.back()}
          className="shrink-0"
        >
          <ArrowLeft className="h-5 w-5" />
          <span className="sr-only">Go back</span>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            Create Scaling Group
          </h1>
          <p className="text-sm text-muted-foreground">
            Define a new auto scaling group to manage server capacity
            automatically.
          </p>
        </div>
      </div>

      {step === 'config' && (
        <>
          {/* ---------- Name & Description ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Group Identity
              </CardTitle>
              <CardDescription>
                Name and description for this scaling group.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="group-name">
                  Name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="group-name"
                  placeholder="e.g., prod-web-fleet"
                  value={form.name}
                  onChange={(e) => update('name', e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="group-description">Description</Label>
                <Textarea
                  id="group-description"
                  placeholder="Optional description for this scaling group"
                  value={form.description}
                  onChange={(e) => update('description', e.target.value)}
                  rows={3}
                />
              </div>
            </CardContent>
          </Card>

          {/* ---------- Server Template ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Server className="h-5 w-5" />
                Server Template
              </CardTitle>
              <CardDescription>
                Configuration template applied to each server in the group.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                {/* Environment */}
                <div className="space-y-2">
                  <Label>
                    Environment <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.environment}
                    onValueChange={(v) => update('environment', v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select environment" />
                    </SelectTrigger>
                    <SelectContent>
                      {ENVIRONMENTS.map((env) => (
                        <SelectItem key={env.value} value={env.value}>
                          {env.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* OS Type */}
                <div className="space-y-2">
                  <Label>
                    Operating System <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.os_type}
                    onValueChange={(v) => update('os_type', v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select OS" />
                    </SelectTrigger>
                    <SelectContent>
                      {OS_TYPES.map((os) => (
                        <SelectItem key={os.value} value={os.value}>
                          {os.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Instance Size */}
                <div className="space-y-2">
                  <Label>
                    Instance Size <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.instance_size}
                    onValueChange={(v) => update('instance_size', v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select size" />
                    </SelectTrigger>
                    <SelectContent>
                      {INSTANCE_SIZES.map((size) => (
                        <SelectItem key={size.value} value={size.value}>
                          {size.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Puppet Role */}
                <div className="space-y-2">
                  <Label>
                    Puppet Role <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.puppet_role}
                    onValueChange={(v) => update('puppet_role', v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select role" />
                    </SelectTrigger>
                    <SelectContent>
                      {PUPPET_ROLES.map((role) => (
                        <SelectItem key={role.value} value={role.value}>
                          {role.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Separator />

              {/* Region / VPC / Subnet */}
              <div className="grid gap-4 sm:grid-cols-3">
                {/* Region */}
                <div className="space-y-2">
                  <Label>
                    Region <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.region}
                    onValueChange={(v) => update('region', v)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select region" />
                    </SelectTrigger>
                    <SelectContent>
                      {regions
                        ?.filter((r) => r.enabled)
                        .map((r) => (
                          <SelectItem key={r.id} value={r.id}>
                            {r.name}
                          </SelectItem>
                        ))}
                      {!regions && (
                        <>
                          <SelectItem value="us-east-1">
                            US East (N. Virginia)
                          </SelectItem>
                          <SelectItem value="us-west-2">
                            US West (Oregon)
                          </SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>

                {/* VPC */}
                <div className="space-y-2">
                  <Label>
                    VPC <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.vpc_id}
                    onValueChange={(v) => update('vpc_id', v)}
                    disabled={!form.region}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          form.region ? 'Select VPC' : 'Select region first'
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {vpcs?.map((vpc) => (
                        <SelectItem key={vpc.vpc_id} value={vpc.vpc_id}>
                          {vpc.name || vpc.vpc_id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {/* Subnet */}
                <div className="space-y-2">
                  <Label>
                    Subnet <span className="text-destructive">*</span>
                  </Label>
                  <Select
                    value={form.subnet_id}
                    onValueChange={(v) => update('subnet_id', v)}
                    disabled={!form.vpc_id}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={
                          form.vpc_id ? 'Select subnet' : 'Select VPC first'
                        }
                      />
                    </SelectTrigger>
                    <SelectContent>
                      {subnets?.map((subnet) => (
                        <SelectItem
                          key={subnet.subnet_id}
                          value={subnet.subnet_id}
                        >
                          {subnet.name || subnet.subnet_id} (
                          {subnet.availability_zone})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* ---------- Scaling Policy ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Settings2 className="h-5 w-5" />
                Scaling Policy
              </CardTitle>
              <CardDescription>
                Define the scaling boundaries and thresholds for automatic
                capacity management.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="min-instances">
                    Minimum Instances{' '}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="min-instances"
                    type="number"
                    min={0}
                    max={100}
                    value={form.min_instances}
                    onChange={(e) => updateNumber('min_instances', e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Lowest allowed instance count
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="desired-count">
                    Desired Count <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="desired-count"
                    type="number"
                    min={form.min_instances}
                    max={form.max_instances}
                    value={form.desired_count}
                    onChange={(e) => updateNumber('desired_count', e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Initial number of instances
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-instances">
                    Maximum Instances{' '}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="max-instances"
                    type="number"
                    min={form.min_instances}
                    max={100}
                    value={form.max_instances}
                    onChange={(e) => updateNumber('max_instances', e.target.value)}
                  />
                  <p className="text-xs text-muted-foreground">
                    Highest allowed instance count
                  </p>
                </div>
              </div>

              <Separator />

              <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="scale-up-threshold">
                    Scale Up Threshold (%)
                  </Label>
                  <Input
                    id="scale-up-threshold"
                    type="number"
                    min={1}
                    max={100}
                    value={form.scale_up_threshold}
                    onChange={(e) =>
                      updateNumber('scale_up_threshold', e.target.value)
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    CPU/load % that triggers scale up
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="scale-down-threshold">
                    Scale Down Threshold (%)
                  </Label>
                  <Input
                    id="scale-down-threshold"
                    type="number"
                    min={0}
                    max={99}
                    value={form.scale_down_threshold}
                    onChange={(e) =>
                      updateNumber('scale_down_threshold', e.target.value)
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    CPU/load % that triggers scale down
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="cooldown-seconds">Cooldown (seconds)</Label>
                  <Input
                    id="cooldown-seconds"
                    type="number"
                    min={60}
                    max={3600}
                    value={form.cooldown_seconds}
                    onChange={(e) =>
                      updateNumber('cooldown_seconds', e.target.value)
                    }
                  />
                  <p className="text-xs text-muted-foreground">
                    Wait time between scaling actions
                  </p>
                </div>
              </div>

              {/* Validation errors */}
              {!isPolicyValid && form.scale_down_threshold >= form.scale_up_threshold && (
                <p className="text-sm text-destructive">
                  Scale down threshold must be lower than scale up threshold.
                </p>
              )}
              {!isPolicyValid && form.desired_count < form.min_instances && (
                <p className="text-sm text-destructive">
                  Desired count cannot be less than minimum instances.
                </p>
              )}
              {!isPolicyValid && form.desired_count > form.max_instances && (
                <p className="text-sm text-destructive">
                  Desired count cannot exceed maximum instances.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Continue to review */}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => router.back()}
            >
              Cancel
            </Button>
            <Button
              disabled={!canSubmit}
              onClick={() => setStep('review')}
            >
              Review Configuration
            </Button>
          </div>
        </>
      )}

      {step === 'review' && (
        <>
          {/* ---------- Review ---------- */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Review Configuration</CardTitle>
              <CardDescription>
                Confirm the settings below before creating the scaling group.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Group identity */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Group Identity</h3>
                <dl className="grid gap-2 sm:grid-cols-2 text-sm">
                  <ReviewRow label="Name" value={form.name} />
                  <ReviewRow
                    label="Description"
                    value={form.description || 'None'}
                  />
                </dl>
              </div>

              <Separator />

              {/* Server template */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Server Template</h3>
                <dl className="grid gap-2 sm:grid-cols-2 text-sm">
                  <ReviewRow
                    label="Environment"
                    value={
                      ENVIRONMENTS.find((e) => e.value === form.environment)
                        ?.label ?? form.environment
                    }
                  />
                  <ReviewRow
                    label="OS"
                    value={
                      OS_TYPES.find((o) => o.value === form.os_type)?.label ??
                      form.os_type
                    }
                  />
                  <ReviewRow
                    label="Instance Size"
                    value={
                      INSTANCE_SIZES.find(
                        (s) => s.value === form.instance_size,
                      )?.label ?? form.instance_size
                    }
                  />
                  <ReviewRow
                    label="Puppet Role"
                    value={
                      PUPPET_ROLES.find((r) => r.value === form.puppet_role)
                        ?.label ?? form.puppet_role
                    }
                  />
                  <ReviewRow label="Region" value={form.region} />
                  <ReviewRow label="VPC" value={form.vpc_id} />
                  <ReviewRow label="Subnet" value={form.subnet_id} />
                </dl>
              </div>

              <Separator />

              {/* Scaling policy */}
              <div>
                <h3 className="text-sm font-semibold mb-2">Scaling Policy</h3>
                <dl className="grid gap-2 sm:grid-cols-3 text-sm">
                  <ReviewRow
                    label="Min Instances"
                    value={String(form.min_instances)}
                  />
                  <ReviewRow
                    label="Desired Count"
                    value={String(form.desired_count)}
                  />
                  <ReviewRow
                    label="Max Instances"
                    value={String(form.max_instances)}
                  />
                  <ReviewRow
                    label="Scale Up At"
                    value={`${form.scale_up_threshold}%`}
                  />
                  <ReviewRow
                    label="Scale Down At"
                    value={`${form.scale_down_threshold}%`}
                  />
                  <ReviewRow
                    label="Cooldown"
                    value={`${form.cooldown_seconds}s`}
                  />
                </dl>
              </div>

              {/* Summary message */}
              <div className="rounded-lg border bg-muted/30 p-4 text-sm">
                This will create a scaling group with an initial fleet of{' '}
                <strong>{form.desired_count}</strong> server
                {form.desired_count !== 1 ? 's' : ''}, automatically scaling
                between <strong>{form.min_instances}</strong> and{' '}
                <strong>{form.max_instances}</strong> based on load thresholds.
              </div>
            </CardContent>
          </Card>

          {/* Action buttons */}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setStep('config')}>
              Back to Edit
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create Scaling Group
            </Button>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper components
// ---------------------------------------------------------------------------

function ReviewRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-medium text-right">{value}</dd>
    </div>
  );
}
