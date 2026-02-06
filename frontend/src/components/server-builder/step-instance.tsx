'use client';

import { Cpu } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useServerForm } from '@/hooks/use-server-form';
import type { InstanceSize } from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Instance size data
// ---------------------------------------------------------------------------

const INSTANCE_SIZES: {
  value: InstanceSize;
  label: string;
  awsType: string;
  vcpu: number;
  ram: string;
}[] = [
  { value: 'small', label: 'Small', awsType: 't3.medium', vcpu: 2, ram: '4 GB' },
  { value: 'medium', label: 'Medium', awsType: 't3.xlarge', vcpu: 4, ram: '16 GB' },
  { value: 'large', label: 'Large', awsType: 'm5.2xlarge', vcpu: 8, ram: '32 GB' },
  { value: 'xl', label: 'X-Large', awsType: 'm5.4xlarge', vcpu: 16, ram: '64 GB' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function StepInstance() {
  const instance_size = useServerForm((s) => s.instance_size);
  const vpc_id = useServerForm((s) => s.vpc_id);
  const subnet_id = useServerForm((s) => s.subnet_id);
  const server_name = useServerForm((s) => s.server_name);
  const setField = useServerForm((s) => s.setField);

  return (
    <div className="space-y-8">
      {/* Instance size */}
      <fieldset className="space-y-3">
        <legend className="text-base font-semibold">Instance Size</legend>
        <p className="text-sm text-muted-foreground">
          Select the compute capacity for your server. X-Large instances require
          approval.
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {INSTANCE_SIZES.map((size) => {
            const isSelected = instance_size === size.value;
            return (
              <Card
                key={size.value}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md',
                  isSelected && 'ring-2 ring-primary',
                )}
                onClick={() => setField('instance_size', size.value)}
              >
                <CardContent className="flex flex-col items-center gap-2 p-5 text-center">
                  <div
                    className={cn(
                      'flex h-10 w-10 items-center justify-center rounded-lg',
                      isSelected
                        ? 'bg-primary text-primary-foreground'
                        : 'bg-muted text-muted-foreground',
                    )}
                  >
                    <Cpu className="h-5 w-5" />
                  </div>
                  <span className="text-sm font-semibold">{size.label}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {size.awsType}
                  </span>
                  <div className="mt-1 flex flex-col text-xs text-muted-foreground">
                    <span>{size.vcpu} vCPU</span>
                    <span>{size.ram} RAM</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </fieldset>

      {/* VPC & Subnet */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="vpc_id" className="text-base font-semibold">
            VPC ID
          </Label>
          <p className="text-sm text-muted-foreground">
            The VPC where this server will be launched.
          </p>
          <Input
            id="vpc_id"
            placeholder="vpc-0abc123def456789"
            value={vpc_id}
            onChange={(e) => setField('vpc_id', e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="subnet_id" className="text-base font-semibold">
            Subnet ID
          </Label>
          <p className="text-sm text-muted-foreground">
            The subnet within the VPC.
          </p>
          <Input
            id="subnet_id"
            placeholder="subnet-0abc123def456789"
            value={subnet_id}
            onChange={(e) => setField('subnet_id', e.target.value)}
          />
        </div>
      </div>

      {/* Server name */}
      <div className="space-y-2">
        <Label htmlFor="server_name" className="text-base font-semibold">
          Server Name{' '}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <p className="text-sm text-muted-foreground">
          Auto-generated if left blank (format: ENV-ROLE-xxxx).
        </p>
        <Input
          id="server_name"
          placeholder="e.g. PROD-WEB-a3f8"
          value={server_name}
          onChange={(e) => setField('server_name', e.target.value)}
          className="max-w-md"
        />
      </div>
    </div>
  );
}
