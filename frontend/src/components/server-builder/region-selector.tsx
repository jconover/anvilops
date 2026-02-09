'use client';

import { MapPin, Globe } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { cn } from '@/lib/utils';
import { useRegions } from '@/lib/api/regions';

// ---------------------------------------------------------------------------
// Region metadata for visual display
// ---------------------------------------------------------------------------

const REGION_META: Record<string, { flag: string; shortLabel: string }> = {
  'us-east-1': { flag: 'US', shortLabel: 'N. Virginia' },
  'us-east-2': { flag: 'US', shortLabel: 'Ohio' },
  'us-west-1': { flag: 'US', shortLabel: 'N. California' },
  'us-west-2': { flag: 'US', shortLabel: 'Oregon' },
  'eu-west-1': { flag: 'EU', shortLabel: 'Ireland' },
  'eu-west-2': { flag: 'EU', shortLabel: 'London' },
  'eu-central-1': { flag: 'EU', shortLabel: 'Frankfurt' },
  'ap-southeast-1': { flag: 'AP', shortLabel: 'Singapore' },
  'ap-southeast-2': { flag: 'AP', shortLabel: 'Sydney' },
  'ap-northeast-1': { flag: 'AP', shortLabel: 'Tokyo' },
  'ca-central-1': { flag: 'CA', shortLabel: 'Canada' },
  'sa-east-1': { flag: 'SA', shortLabel: 'Sao Paulo' },
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface RegionSelectorProps {
  value: string;
  onChange: (regionId: string) => void;
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function RegionSelectorSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {Array.from({ length: 4 }).map((_, i) => (
        <Skeleton key={i} className="h-[88px] rounded-lg" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RegionSelector({ value, onChange }: RegionSelectorProps) {
  const { data: regions, isLoading, isError } = useRegions();

  if (isLoading) {
    return <RegionSelectorSkeleton />;
  }

  if (isError || !regions) {
    return (
      <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
        Failed to load regions. Please try again later.
      </div>
    );
  }

  if (regions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
        No regions are currently available.
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {regions.map((region) => {
        const isSelected = value === region.id;
        const isDisabled = !region.enabled;
        const meta = REGION_META[region.id];

        return (
          <Card
            key={region.id}
            className={cn(
              'transition-all',
              isDisabled
                ? 'cursor-not-allowed opacity-50'
                : 'cursor-pointer hover:shadow-md',
              isSelected && !isDisabled && 'ring-2 ring-primary',
            )}
            onClick={() => {
              if (!isDisabled) {
                onChange(region.id);
              }
            }}
          >
            <CardContent className="flex items-center gap-4 p-4">
              {/* Icon */}
              <div
                className={cn(
                  'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg',
                  isSelected && !isDisabled
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted text-muted-foreground',
                )}
              >
                {isSelected ? (
                  <MapPin className="h-5 w-5" />
                ) : (
                  <Globe className="h-5 w-5" />
                )}
              </div>

              {/* Details */}
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">
                  {region.name}
                </p>
                <p className="truncate font-mono text-xs text-muted-foreground">
                  {region.short_name}
                </p>
                {meta && (
                  <span className="mt-0.5 inline-block rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                    {meta.flag}
                  </span>
                )}
              </div>

              {/* Disabled badge */}
              {isDisabled && (
                <span className="shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  Unavailable
                </span>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
