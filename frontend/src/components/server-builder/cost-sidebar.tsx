'use client';

import { useEffect, useRef, useState } from 'react';
import { DollarSign } from 'lucide-react';
import { Skeleton } from '@/components/ui/skeleton';
import { useCostEstimate } from '@/hooks/use-cost-estimate';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCompactCurrency(amount: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

// ---------------------------------------------------------------------------
// Animated number component
// ---------------------------------------------------------------------------

/**
 * Renders a currency value with a brief highlight animation whenever the
 * displayed value changes. Uses a CSS transition on opacity/color to draw
 * the user's eye to the update without being distracting.
 */
function AnimatedCost({ value }: { value: number }) {
  const [displayValue, setDisplayValue] = useState(value);
  const [isAnimating, setIsAnimating] = useState(false);
  const prevValue = useRef(value);

  useEffect(() => {
    if (prevValue.current !== value) {
      setIsAnimating(true);
      // Brief delay before showing new value to let the "flash" register.
      const updateTimer = setTimeout(() => {
        setDisplayValue(value);
      }, 80);
      // Remove highlight class after transition completes.
      const resetTimer = setTimeout(() => {
        setIsAnimating(false);
      }, 600);
      prevValue.current = value;
      return () => {
        clearTimeout(updateTimer);
        clearTimeout(resetTimer);
      };
    }
  }, [value]);

  return (
    <span
      className={cn(
        'transition-all duration-500',
        isAnimating
          ? 'scale-105 text-emerald-600 dark:text-emerald-400'
          : 'scale-100',
      )}
    >
      {formatCompactCurrency(displayValue)}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface CostSidebarProps {
  /** The current wizard step index (0-based). */
  currentStep: number;
}

export function CostSidebar({ currentStep }: CostSidebarProps) {
  const { estimate, isLoading } = useCostEstimate();

  // Only show after step 2 (i.e. when we're on step index 2 or later),
  // which means instance_size has been selected.
  if (currentStep < 2) {
    return null;
  }

  return (
    <div className="mt-4 rounded-lg border bg-gradient-to-br from-emerald-50/50 to-background p-3 dark:from-emerald-950/20">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
          <DollarSign className="h-3.5 w-3.5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-muted-foreground">
            Est. Cost
          </p>
          {isLoading ? (
            <Skeleton className="mt-0.5 h-5 w-20" />
          ) : estimate ? (
            <p className="text-sm font-bold leading-tight tracking-tight">
              <AnimatedCost value={estimate.total_monthly} />
              <span className="ml-0.5 text-xs font-normal text-muted-foreground">
                /mo
              </span>
            </p>
          ) : (
            <p className="mt-0.5 text-xs text-muted-foreground">--</p>
          )}
        </div>
      </div>
    </div>
  );
}
