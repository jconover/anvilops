'use client';

import { Cpu } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { useServerForm } from '@/hooks/use-server-form';
import type { InstanceSize } from '@/lib/api/types';
import { VPCSelector } from './vpc-selector';
import { SubnetSelector } from './subnet-selector';

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
  const region = useServerForm((s) => s.region);
  const vpc_id = useServerForm((s) => s.vpc_id);
  const subnet_id = useServerForm((s) => s.subnet_id);
  const server_name = useServerForm((s) => s.server_name);
  const setField = useServerForm((s) => s.setField);

  const handleVPCChange = (vpcId: string) => {
    setField('vpc_id', vpcId);
    // Clear subnet when VPC changes — subnets belong to a specific VPC
    setField('subnet_id', '');
  };

  const handleSubnetChange = (subnetId: string) => {
    setField('subnet_id', subnetId);
  };

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

      {/* VPC & Subnet — cascading selectors */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        <div className="space-y-2">
          <Label className="text-base font-semibold">VPC</Label>
          <p className="text-sm text-muted-foreground">
            The VPC where this server will be launched.
            {!region && (
              <span className="ml-1 italic">
                Select a region in the previous step to see available VPCs.
              </span>
            )}
          </p>
          <VPCSelector
            region={region || undefined}
            value={vpc_id}
            onChange={handleVPCChange}
          />
        </div>
        <div className="space-y-2">
          <Label className="text-base font-semibold">Subnet</Label>
          <p className="text-sm text-muted-foreground">
            The subnet within the VPC.
            {region && !vpc_id && (
              <span className="ml-1 italic">
                Select a VPC to see available subnets.
              </span>
            )}
          </p>
          <SubnetSelector
            region={region || undefined}
            vpcId={vpc_id || undefined}
            value={subnet_id}
            onChange={handleSubnetChange}
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
