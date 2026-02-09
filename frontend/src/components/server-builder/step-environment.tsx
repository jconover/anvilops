'use client';

import {
  Server,
  FlaskConical,
  Rocket,
  Monitor,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { useServerForm } from '@/hooks/use-server-form';
import type { OsType } from '@/lib/api/types';
import { RegionSelector } from './region-selector';

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const ENVIRONMENTS = [
  {
    value: 'dev' as const,
    label: 'Development',
    description: 'For feature development and experimentation. No approval required.',
    icon: FlaskConical,
    color: 'text-blue-600 dark:text-blue-400',
    ring: 'ring-blue-500',
    bg: 'bg-blue-50 dark:bg-blue-950',
  },
  {
    value: 'staging' as const,
    label: 'Staging',
    description: 'Pre-production testing and QA validation. No approval required.',
    icon: Server,
    color: 'text-amber-600 dark:text-amber-400',
    ring: 'ring-amber-500',
    bg: 'bg-amber-50 dark:bg-amber-950',
  },
  {
    value: 'production' as const,
    label: 'Production',
    description: 'Live workloads. Requires manager approval before provisioning.',
    icon: Rocket,
    color: 'text-red-600 dark:text-red-400',
    ring: 'ring-red-500',
    bg: 'bg-red-50 dark:bg-red-950',
  },
];

const OS_OPTIONS: { value: OsType; label: string; family: 'windows' | 'linux' }[] = [
  { value: 'windows_2022', label: 'Windows Server 2022', family: 'windows' },
  { value: 'windows_2019', label: 'Windows Server 2019', family: 'windows' },
  { value: 'amazon_linux_2023', label: 'Amazon Linux 2023', family: 'linux' },
  { value: 'ubuntu_2204', label: 'Ubuntu 22.04 LTS', family: 'linux' },
  { value: 'rhel_9', label: 'Red Hat Enterprise Linux 9', family: 'linux' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepEnvironment() {
  const environment = useServerForm((s) => s.environment);
  const os_type = useServerForm((s) => s.os_type);
  const region = useServerForm((s) => s.region);
  const setField = useServerForm((s) => s.setField);

  const handleRegionChange = (regionId: string) => {
    setField('region', regionId);
    // Clear downstream selections when region changes
    setField('vpc_id', '');
    setField('subnet_id', '');
  };

  return (
    <div className="space-y-8">
      {/* Environment selector */}
      <fieldset className="space-y-3">
        <legend className="text-base font-semibold">Target Environment</legend>
        <p className="text-sm text-muted-foreground">
          Select the environment where this server will be deployed.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {ENVIRONMENTS.map((env) => {
            const Icon = env.icon;
            const isSelected = environment === env.value;
            return (
              <Card
                key={env.value}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md',
                  isSelected && `ring-2 ${env.ring}`,
                )}
                onClick={() => setField('environment', env.value)}
              >
                <CardContent className="flex flex-col items-center gap-2 p-5 text-center">
                  <div
                    className={cn(
                      'flex h-11 w-11 items-center justify-center rounded-full',
                      isSelected ? env.bg : 'bg-muted',
                    )}
                  >
                    <Icon
                      className={cn(
                        'h-5 w-5',
                        isSelected ? env.color : 'text-muted-foreground',
                      )}
                    />
                  </div>
                  <span className="text-sm font-semibold">{env.label}</span>
                  <span className="text-xs leading-relaxed text-muted-foreground">
                    {env.description}
                  </span>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </fieldset>

      {/* OS type selector */}
      <fieldset className="space-y-3">
        <legend className="text-base font-semibold">Operating System</legend>
        <p className="text-sm text-muted-foreground">
          Choose the operating system for your server.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {OS_OPTIONS.map((os) => {
            const isSelected = os_type === os.value;
            return (
              <Card
                key={os.value}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md',
                  isSelected && 'ring-2 ring-primary',
                )}
                onClick={() => setField('os_type', os.value)}
              >
                <CardContent className="flex items-center gap-3 p-4">
                  <div
                    className={cn(
                      'flex h-9 w-9 items-center justify-center rounded-lg',
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    <Monitor className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium">{os.label}</p>
                    <p className="text-xs capitalize text-muted-foreground">
                      {os.family}
                    </p>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </fieldset>

      {/* Region selector */}
      <div className="space-y-3">
        <Label className="text-base font-semibold">AWS Region</Label>
        <p className="text-sm text-muted-foreground">
          Select the AWS region where this server will be deployed. VPC and
          subnet options will update based on your selection.
        </p>
        <RegionSelector value={region} onChange={handleRegionChange} />
      </div>
    </div>
  );
}
