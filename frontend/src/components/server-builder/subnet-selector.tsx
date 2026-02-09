'use client';

import { Loader2, Layers, AlertCircle, Globe, Lock } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectSeparator,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useSubnets, type Subnet } from '@/lib/api/regions';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface SubnetSelectorProps {
  region: string | undefined;
  vpcId: string | undefined;
  value: string;
  onChange: (subnetId: string) => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Group subnets by availability zone. */
function groupByAZ(subnets: Subnet[]): Record<string, Subnet[]> {
  const groups: Record<string, Subnet[]> = {};
  for (const subnet of subnets) {
    const az = subnet.availability_zone;
    if (!groups[az]) {
      groups[az] = [];
    }
    groups[az].push(subnet);
  }
  // Sort AZ keys alphabetically
  const sorted: Record<string, Subnet[]> = {};
  for (const key of Object.keys(groups).sort()) {
    sorted[key] = groups[key];
  }
  return sorted;
}

/** Return a color-coding variant based on available IP count. */
function ipCountVariant(
  ips: number,
): 'success' | 'warning' | 'destructive' {
  if (ips >= 100) return 'success';
  if (ips >= 20) return 'warning';
  return 'destructive';
}

/** Return the text color class for available IPs. */
function ipCountColor(ips: number): string {
  if (ips >= 100) return 'text-green-600 dark:text-green-400';
  if (ips >= 20) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SubnetSelector({
  region,
  vpcId,
  value,
  onChange,
}: SubnetSelectorProps) {
  const { data: subnets, isLoading, isError } = useSubnets(region, vpcId);

  // No VPC selected yet
  if (!vpcId || !region) {
    return (
      <Select disabled>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select a VPC first" />
        </SelectTrigger>
      </Select>
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <Select disabled>
        <SelectTrigger className="w-full">
          <span className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading subnets...
          </span>
        </SelectTrigger>
      </Select>
    );
  }

  // Error state
  if (isError) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive">
        <AlertCircle className="h-4 w-4 shrink-0" />
        Failed to load subnets. Please try again.
      </div>
    );
  }

  // Empty state
  if (!subnets || subnets.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
        <Layers className="h-4 w-4 shrink-0" />
        No subnets found in this VPC.
      </div>
    );
  }

  const grouped = groupByAZ(subnets);
  const azKeys = Object.keys(grouped);

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select a subnet" />
      </SelectTrigger>
      <SelectContent>
        {azKeys.map((az, azIndex) => (
          <SelectGroup key={az}>
            <SelectLabel className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              {az}
            </SelectLabel>
            {grouped[az].map((subnet) => (
              <SelectItem key={subnet.subnet_id} value={subnet.subnet_id}>
                <span className="flex items-center gap-2">
                  <Layers className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="flex flex-col">
                    <span className="flex items-center gap-2">
                      <span className="font-medium">
                        {subnet.name || subnet.subnet_id}
                      </span>
                      {subnet.is_public ? (
                        <Badge
                          variant="warning"
                          className="px-1.5 py-0 text-[10px]"
                        >
                          <Globe className="mr-0.5 h-2.5 w-2.5" />
                          Public
                        </Badge>
                      ) : (
                        <Badge
                          variant="secondary"
                          className="px-1.5 py-0 text-[10px]"
                        >
                          <Lock className="mr-0.5 h-2.5 w-2.5" />
                          Private
                        </Badge>
                      )}
                    </span>
                    <span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground">
                      <span>{subnet.subnet_id}</span>
                      <span>&middot;</span>
                      <span>{subnet.cidr_block}</span>
                      <span>&middot;</span>
                      <span className={ipCountColor(subnet.available_ips)}>
                        {subnet.available_ips} IPs
                      </span>
                    </span>
                  </span>
                </span>
              </SelectItem>
            ))}
            {azIndex < azKeys.length - 1 && <SelectSeparator />}
          </SelectGroup>
        ))}
      </SelectContent>
    </Select>
  );
}
