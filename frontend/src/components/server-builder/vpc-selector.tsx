'use client';

import { Loader2, Network, AlertCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useVPCs } from '@/lib/api/regions';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface VPCSelectorProps {
  region: string | undefined;
  value: string;
  onChange: (vpcId: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function VPCSelector({ region, value, onChange }: VPCSelectorProps) {
  const { data: vpcs, isLoading, isError } = useVPCs(region);

  // No region selected yet — show disabled placeholder
  if (!region) {
    return (
      <Select disabled>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select a region first" />
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
            Loading VPCs...
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
        Failed to load VPCs. Please try again.
      </div>
    );
  }

  // Empty state
  if (!vpcs || vpcs.length === 0) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
        <Network className="h-4 w-4 shrink-0" />
        No VPCs found in this region.
      </div>
    );
  }

  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-full">
        <SelectValue placeholder="Select a VPC" />
      </SelectTrigger>
      <SelectContent>
        {vpcs.map((vpc) => (
          <SelectItem key={vpc.vpc_id} value={vpc.vpc_id}>
            <span className="flex items-center gap-2">
              <Network className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="flex flex-col">
                <span className="flex items-center gap-2">
                  <span className="font-medium">
                    {vpc.name || vpc.vpc_id}
                  </span>
                  {vpc.is_default && (
                    <Badge variant="info" className="px-1.5 py-0 text-[10px]">
                      Default
                    </Badge>
                  )}
                </span>
                <span className="font-mono text-xs text-muted-foreground">
                  {vpc.vpc_id} &middot; {vpc.cidr_block}
                </span>
              </span>
            </span>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
