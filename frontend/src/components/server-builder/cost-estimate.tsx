'use client';

import { useState } from 'react';
import {
  DollarSign,
  ChevronDown,
  ChevronUp,
  Info,
  Monitor,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Button } from '@/components/ui/button';
import { useCostEstimate } from '@/hooks/use-cost-estimate';
import { useServerForm } from '@/hooks/use-server-form';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Format a number as US currency. Falls back to the raw number if
 * Intl.NumberFormat is unavailable (shouldn't happen in modern browsers).
 */
function formatCurrency(amount: number, currency = 'USD'): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/** True when the OS type represents a Windows variant. */
function isWindowsOs(osType: string): boolean {
  return osType.startsWith('windows');
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function CostEstimateSkeleton() {
  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 dark:bg-emerald-950">
            <DollarSign className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="space-y-1.5">
            <Skeleton className="h-4 w-44" />
            <Skeleton className="h-3 w-28" />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        <div className="space-y-2">
          <Skeleton className="h-10 w-36" />
          <Skeleton className="h-4 w-24" />
        </div>
        <Separator />
        <div className="space-y-2">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-3 w-3/5" />
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

function CostEstimateError() {
  return (
    <Card className="border-dashed">
      <CardContent className="flex items-center gap-3 p-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted text-muted-foreground">
          <DollarSign className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-semibold">Cost Estimate Unavailable</p>
          <p className="text-sm text-muted-foreground">
            Unable to retrieve pricing data. The estimate will appear once the
            pricing service is reachable.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CostEstimate() {
  const { estimate, isLoading, error } = useCostEstimate();
  const osType = useServerForm((s) => s.os_type);
  const [breakdownOpen, setBreakdownOpen] = useState(false);

  // Loading state
  if (isLoading) {
    return <CostEstimateSkeleton />;
  }

  // Error state
  if (error && !estimate) {
    return <CostEstimateError />;
  }

  // No estimate yet (shouldn't normally happen on the review step, but guard)
  if (!estimate) {
    return <CostEstimateSkeleton />;
  }

  const currency = estimate.currency || 'USD';

  return (
    <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50/50 to-background dark:border-emerald-900 dark:from-emerald-950/30">
      {/* Header */}
      <CardHeader className="pb-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <DollarSign className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-base">Estimated Monthly Cost</CardTitle>
            <p className="text-xs text-muted-foreground">
              Instance type: {estimate.instance_type}
            </p>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pt-0">
        {/* Primary cost display */}
        <div>
          <p className="text-3xl font-bold tracking-tight text-emerald-700 dark:text-emerald-400">
            {formatCurrency(estimate.total_monthly, currency)}
            <span className="ml-1.5 text-base font-normal text-muted-foreground">
              /mo
            </span>
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {formatCurrency(estimate.total_annual, currency)} per year
          </p>
        </div>

        {/* Cost summary badges */}
        <div className="flex flex-wrap gap-2">
          <Badge variant="secondary" className="gap-1 font-normal">
            Compute: {formatCurrency(estimate.instance_cost, currency)}
          </Badge>
          <Badge variant="secondary" className="gap-1 font-normal">
            Storage: {formatCurrency(estimate.storage_cost, currency)}
          </Badge>
          {estimate.os_license_cost > 0 && (
            <Badge variant="secondary" className="gap-1 font-normal">
              License: {formatCurrency(estimate.os_license_cost, currency)}
            </Badge>
          )}
        </div>

        {/* Windows license indicator */}
        {isWindowsOs(osType) && (
          <div className="flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 dark:border-blue-900 dark:bg-blue-950">
            <Monitor className="h-4 w-4 shrink-0 text-blue-600 dark:text-blue-400" />
            <p className="text-xs text-blue-700 dark:text-blue-300">
              Includes Windows Server license cost (SA not included)
            </p>
          </div>
        )}

        <Separator />

        {/* Expandable breakdown */}
        {estimate.breakdown.length > 0 && (
          <div>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-full justify-between px-0 text-sm font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setBreakdownOpen(!breakdownOpen)}
            >
              <span>Cost Breakdown ({estimate.breakdown.length} items)</span>
              {breakdownOpen ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>

            {breakdownOpen && (
              <div className="mt-2 rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="h-9 text-xs">Category</TableHead>
                      <TableHead className="h-9 text-xs">Description</TableHead>
                      <TableHead className="h-9 text-right text-xs">
                        Monthly
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {estimate.breakdown.map((item, index) => (
                      <TableRow key={`${item.category}-${index}`}>
                        <TableCell className="py-2 text-xs font-medium">
                          {item.category}
                        </TableCell>
                        <TableCell className="py-2 text-xs text-muted-foreground">
                          {item.description}
                        </TableCell>
                        <TableCell className="py-2 text-right text-xs font-medium">
                          {formatCurrency(item.monthly_cost, currency)}
                        </TableCell>
                      </TableRow>
                    ))}
                    {/* Total row */}
                    <TableRow className="border-t-2">
                      <TableCell
                        colSpan={2}
                        className="py-2 text-xs font-semibold"
                      >
                        Total
                      </TableCell>
                      <TableCell className="py-2 text-right text-xs font-bold text-emerald-700 dark:text-emerald-400">
                        {formatCurrency(estimate.total_monthly, currency)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        )}

        {/* Disclaimer */}
        <div className="flex items-start gap-2 rounded-md bg-muted/50 px-3 py-2">
          <Info className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <p className="text-xs leading-relaxed text-muted-foreground">
            Estimates are approximate and based on on-demand pricing. Actual
            costs may vary based on usage, data transfer, reserved instance
            discounts, and other factors.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
