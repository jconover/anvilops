'use client';

import { useCallback, useState } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { CronBuilder, validateCron } from '@/components/schedules/cron-builder';
import {
  useCreateSchedule,
  type ScheduleCreateRequest,
  type ScheduleType,
  type ScheduleServerConfig,
} from '@/lib/api/schedules';
import {
  ArrowLeft,
  Calendar,
  Loader2,
  Repeat,
  Server,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Timezone options (common/abbreviated)
// ---------------------------------------------------------------------------

const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'US Eastern (ET)' },
  { value: 'America/Chicago', label: 'US Central (CT)' },
  { value: 'America/Denver', label: 'US Mountain (MT)' },
  { value: 'America/Los_Angeles', label: 'US Pacific (PT)' },
  { value: 'Europe/London', label: 'London (GMT/BST)' },
  { value: 'Europe/Berlin', label: 'Berlin (CET/CEST)' },
  { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
  { value: 'Asia/Shanghai', label: 'Shanghai (CST)' },
  { value: 'Australia/Sydney', label: 'Sydney (AEST/AEDT)' },
];

// ---------------------------------------------------------------------------
// Server config options (simplified version of wizard steps)
// ---------------------------------------------------------------------------

const ENVIRONMENT_OPTIONS = [
  { value: 'dev', label: 'Development' },
  { value: 'staging', label: 'Staging' },
  { value: 'production', label: 'Production' },
];

const OS_OPTIONS = [
  { value: 'windows_2022', label: 'Windows Server 2022' },
  { value: 'windows_2019', label: 'Windows Server 2019' },
  { value: 'amazon_linux_2023', label: 'Amazon Linux 2023' },
  { value: 'ubuntu_2204', label: 'Ubuntu 22.04 LTS' },
  { value: 'rhel_9', label: 'RHEL 9' },
];

const INSTANCE_SIZE_OPTIONS = [
  { value: 'small', label: 'Small' },
  { value: 'medium', label: 'Medium' },
  { value: 'large', label: 'Large' },
  { value: 'xl', label: 'XL' },
];

const REGION_OPTIONS = [
  { value: 'us-east-1', label: 'US East (N. Virginia)' },
  { value: 'us-west-2', label: 'US West (Oregon)' },
];

const PUPPET_ROLE_OPTIONS = [
  { value: 'base', label: 'Base' },
  { value: 'web_server', label: 'Web Server' },
  { value: 'app_server', label: 'Application Server' },
  { value: 'database', label: 'Database' },
  { value: 'workstation', label: 'Dev Workstation' },
];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function NewSchedulePage() {
  const router = useRouter();
  const createMutation = useCreateSchedule();

  // Form state
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [scheduleType, setScheduleType] = useState<ScheduleType>('recurring');
  const [cronExpression, setCronExpression] = useState('0 2 * * *');
  const [scheduledAt, setScheduledAt] = useState('');
  const [timezone, setTimezone] = useState('UTC');
  const [maxRuns, setMaxRuns] = useState('');

  // Server config state
  const [environment, setEnvironment] = useState('dev');
  const [osType, setOsType] = useState('amazon_linux_2023');
  const [instanceSize, setInstanceSize] = useState('medium');
  const [region, setRegion] = useState('us-east-1');
  const [puppetRole, setPuppetRole] = useState('base');

  // Validation
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = useCallback((): boolean => {
    const newErrors: Record<string, string> = {};

    if (!name.trim()) {
      newErrors.name = 'Schedule name is required';
    }

    if (scheduleType === 'recurring') {
      const cronError = validateCron(cronExpression);
      if (cronError) {
        newErrors.cron = cronError;
      }
    } else {
      if (!scheduledAt) {
        newErrors.scheduledAt = 'Scheduled date and time is required';
      } else {
        const scheduledDate = new Date(scheduledAt);
        if (scheduledDate <= new Date()) {
          newErrors.scheduledAt = 'Scheduled time must be in the future';
        }
      }
    }

    if (!environment) newErrors.environment = 'Environment is required';
    if (!osType) newErrors.osType = 'Operating system is required';
    if (!instanceSize) newErrors.instanceSize = 'Instance size is required';
    if (!region) newErrors.region = 'Region is required';
    if (!puppetRole) newErrors.puppetRole = 'Puppet role is required';

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [
    name,
    scheduleType,
    cronExpression,
    scheduledAt,
    environment,
    osType,
    instanceSize,
    region,
    puppetRole,
  ]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validate()) return;

    const serverConfig: ScheduleServerConfig = {
      environment,
      os_type: osType,
      instance_size: instanceSize,
      region,
      puppet_role: puppetRole,
    };

    const request: ScheduleCreateRequest = {
      name: name.trim(),
      description: description.trim() || undefined,
      schedule_type: scheduleType,
      timezone,
      server_config: serverConfig,
    };

    if (scheduleType === 'recurring') {
      request.cron_expression = cronExpression;
      if (maxRuns) {
        request.max_runs = parseInt(maxRuns, 10);
      }
    } else {
      request.scheduled_at = new Date(scheduledAt).toISOString();
    }

    createMutation.mutate(request, {
      onSuccess: (data) => {
        toast.success('Schedule created', {
          description: `"${data.name}" has been scheduled.`,
        });
        router.push(`/dashboard/schedules/${data.id}`);
      },
      onError: (error) => {
        toast.error('Failed to create schedule', {
          description: error.message ?? 'An unexpected error occurred.',
        });
      },
    });
  };

  return (
    <div className="mx-auto max-w-3xl space-y-8">
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
          <h1 className="text-2xl font-bold tracking-tight">New Schedule</h1>
          <p className="text-sm text-muted-foreground">
            Schedule server provisioning for a future time or recurring
            interval.
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ---------- Basic info ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Schedule Details</CardTitle>
            <CardDescription>
              Name and describe this scheduled build.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Nightly Dev Server Build"
                className={cn(errors.name && 'border-destructive')}
              />
              {errors.name && (
                <p className="text-xs text-destructive">{errors.name}</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description of this schedule's purpose"
                rows={2}
              />
            </div>
          </CardContent>
        </Card>

        {/* ---------- Schedule type ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Schedule Type</CardTitle>
            <CardDescription>
              Choose between a one-time or recurring schedule.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Type selector */}
            <div className="grid grid-cols-2 gap-4">
              <button
                type="button"
                onClick={() => setScheduleType('one_time')}
                className={cn(
                  'flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition-colors',
                  scheduleType === 'one_time'
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50',
                )}
              >
                <Calendar
                  className={cn(
                    'h-8 w-8',
                    scheduleType === 'one_time'
                      ? 'text-primary'
                      : 'text-muted-foreground',
                  )}
                />
                <div>
                  <p className="font-semibold">One-Time</p>
                  <p className="text-xs text-muted-foreground">
                    Run once at a specific date and time
                  </p>
                </div>
              </button>
              <button
                type="button"
                onClick={() => setScheduleType('recurring')}
                className={cn(
                  'flex flex-col items-center gap-2 rounded-lg border-2 p-4 text-center transition-colors',
                  scheduleType === 'recurring'
                    ? 'border-primary bg-primary/5'
                    : 'border-border hover:border-primary/50',
                )}
              >
                <Repeat
                  className={cn(
                    'h-8 w-8',
                    scheduleType === 'recurring'
                      ? 'text-primary'
                      : 'text-muted-foreground',
                  )}
                />
                <div>
                  <p className="font-semibold">Recurring</p>
                  <p className="text-xs text-muted-foreground">
                    Run on a cron-based recurring schedule
                  </p>
                </div>
              </button>
            </div>

            {/* One-time: date/time picker + timezone */}
            {scheduleType === 'one_time' && (
              <div className="space-y-4 rounded-lg border p-4">
                <div className="space-y-1.5">
                  <Label htmlFor="scheduledAt">
                    Date &amp; Time{' '}
                    <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="scheduledAt"
                    type="datetime-local"
                    value={scheduledAt}
                    onChange={(e) => setScheduledAt(e.target.value)}
                    className={cn(
                      errors.scheduledAt && 'border-destructive',
                    )}
                  />
                  {errors.scheduledAt && (
                    <p className="text-xs text-destructive">
                      {errors.scheduledAt}
                    </p>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label>Timezone</Label>
                  <Select value={timezone} onValueChange={setTimezone}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {TIMEZONE_OPTIONS.map((tz) => (
                        <SelectItem key={tz.value} value={tz.value}>
                          {tz.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            )}

            {/* Recurring: cron builder + timezone + max runs */}
            {scheduleType === 'recurring' && (
              <div className="space-y-4">
                <CronBuilder
                  value={cronExpression}
                  onChange={setCronExpression}
                />
                {errors.cron && (
                  <p className="text-xs text-destructive">{errors.cron}</p>
                )}
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <Label>Timezone</Label>
                    <Select value={timezone} onValueChange={setTimezone}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {TIMEZONE_OPTIONS.map((tz) => (
                          <SelectItem key={tz.value} value={tz.value}>
                            {tz.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="maxRuns">
                      Max Runs{' '}
                      <span className="text-xs text-muted-foreground">
                        (optional)
                      </span>
                    </Label>
                    <Input
                      id="maxRuns"
                      type="number"
                      min={1}
                      value={maxRuns}
                      onChange={(e) => setMaxRuns(e.target.value)}
                      placeholder="Unlimited"
                    />
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------- Server configuration ---------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-lg">
              <Server className="h-5 w-5" />
              Server Configuration
            </CardTitle>
            <CardDescription>
              Define the server parameters for each scheduled build.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Environment */}
              <div className="space-y-1.5">
                <Label>
                  Environment <span className="text-destructive">*</span>
                </Label>
                <Select value={environment} onValueChange={setEnvironment}>
                  <SelectTrigger
                    className={cn(
                      errors.environment && 'border-destructive',
                    )}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ENVIRONMENT_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.environment && (
                  <p className="text-xs text-destructive">
                    {errors.environment}
                  </p>
                )}
              </div>

              {/* Operating System */}
              <div className="space-y-1.5">
                <Label>
                  Operating System <span className="text-destructive">*</span>
                </Label>
                <Select value={osType} onValueChange={setOsType}>
                  <SelectTrigger
                    className={cn(errors.osType && 'border-destructive')}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {OS_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.osType && (
                  <p className="text-xs text-destructive">{errors.osType}</p>
                )}
              </div>

              {/* Instance Size */}
              <div className="space-y-1.5">
                <Label>
                  Instance Size <span className="text-destructive">*</span>
                </Label>
                <Select
                  value={instanceSize}
                  onValueChange={setInstanceSize}
                >
                  <SelectTrigger
                    className={cn(
                      errors.instanceSize && 'border-destructive',
                    )}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {INSTANCE_SIZE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.instanceSize && (
                  <p className="text-xs text-destructive">
                    {errors.instanceSize}
                  </p>
                )}
              </div>

              {/* Region */}
              <div className="space-y-1.5">
                <Label>
                  Region <span className="text-destructive">*</span>
                </Label>
                <Select value={region} onValueChange={setRegion}>
                  <SelectTrigger
                    className={cn(errors.region && 'border-destructive')}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REGION_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.region && (
                  <p className="text-xs text-destructive">{errors.region}</p>
                )}
              </div>

              {/* Puppet Role */}
              <div className="space-y-1.5 sm:col-span-2">
                <Label>
                  Puppet Role <span className="text-destructive">*</span>
                </Label>
                <Select value={puppetRole} onValueChange={setPuppetRole}>
                  <SelectTrigger
                    className={cn(
                      errors.puppetRole && 'border-destructive',
                    )}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PUPPET_ROLE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {errors.puppetRole && (
                  <p className="text-xs text-destructive">
                    {errors.puppetRole}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ---------- Submit ---------- */}
        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            onClick={() => router.back()}
            disabled={createMutation.isPending}
          >
            Cancel
          </Button>
          <Button type="submit" disabled={createMutation.isPending}>
            {createMutation.isPending && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Create Schedule
          </Button>
        </div>
      </form>
    </div>
  );
}
