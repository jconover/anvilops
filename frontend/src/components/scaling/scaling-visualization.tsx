'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScalingVisualizationProps {
  min: number;
  max: number;
  current: number;
  desired: number;
  className?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Determine the color state of the scaling group. */
function getScaleState(
  current: number,
  desired: number,
  min: number,
  max: number,
): 'normal' | 'scaling' | 'at_limit' {
  if (current === min || current === max) return 'at_limit';
  if (current !== desired) return 'scaling';
  return 'normal';
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Horizontal bar visualization of the scaling range.
 *
 * Shows markers for min, current, desired, and max with color coding:
 *   - Green: normal (current matches desired, within range)
 *   - Yellow: scaling (current does not match desired)
 *   - Red: at limits (current is at min or max)
 */
export function ScalingVisualization({
  min,
  max,
  current,
  desired,
  className,
}: ScalingVisualizationProps) {
  const state = useMemo(
    () => getScaleState(current, desired, min, max),
    [current, desired, min, max],
  );

  // Compute positions as percentages of the full range.
  // Prevent division by zero when min === max.
  const range = max - min || 1;
  const currentPct = ((current - min) / range) * 100;
  const desiredPct = ((desired - min) / range) * 100;

  // Bar fill goes from 0 to current position.
  const fillColor = {
    normal: 'bg-green-500',
    scaling: 'bg-yellow-500',
    at_limit: 'bg-red-500',
  }[state];

  const markerColors = {
    normal: 'border-green-600',
    scaling: 'border-yellow-600',
    at_limit: 'border-red-600',
  }[state];

  return (
    <div className={cn('space-y-3', className)}>
      {/* Labels row */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>Min: {min}</span>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-1">
            <span
              className={cn(
                'inline-block h-2 w-2 rounded-full',
                fillColor,
              )}
            />
            Current: {current}
          </span>
          {current !== desired && (
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full border-2 border-dashed border-blue-500 bg-transparent" />
              Desired: {desired}
            </span>
          )}
        </div>
        <span>Max: {max}</span>
      </div>

      {/* Bar track */}
      <div className="relative h-6 w-full rounded-full bg-muted/50 border">
        {/* Fill bar */}
        <div
          className={cn(
            'absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-in-out',
            fillColor,
            'opacity-30',
          )}
          style={{ width: `${Math.min(100, Math.max(0, currentPct))}%` }}
        />

        {/* Current marker */}
        <div
          className={cn(
            'absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-5 w-5 rounded-full border-2 bg-background shadow-sm transition-all duration-700 ease-in-out',
            markerColors,
          )}
          style={{ left: `${Math.min(100, Math.max(0, currentPct))}%` }}
        >
          <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] font-medium whitespace-nowrap">
            {current}
          </span>
        </div>

        {/* Desired marker (only visible when different from current) */}
        {current !== desired && (
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-5 w-5 rounded-full border-2 border-dashed border-blue-500 bg-background/80 shadow-sm transition-all duration-700 ease-in-out"
            style={{ left: `${Math.min(100, Math.max(0, desiredPct))}%` }}
          >
            <span className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-[10px] font-medium text-blue-600 whitespace-nowrap">
              {desired}
            </span>
          </div>
        )}

        {/* Min endpoint marker */}
        <div className="absolute top-1/2 left-0 -translate-y-1/2 h-3 w-0.5 bg-muted-foreground/40 rounded-full" />

        {/* Max endpoint marker */}
        <div className="absolute top-1/2 right-0 -translate-y-1/2 h-3 w-0.5 bg-muted-foreground/40 rounded-full" />
      </div>

      {/* Status label */}
      <div className="flex justify-center">
        <span
          className={cn(
            'text-xs font-medium px-2 py-0.5 rounded-full',
            state === 'normal' && 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
            state === 'scaling' && 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
            state === 'at_limit' && 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
          )}
        >
          {state === 'normal' && 'Stable'}
          {state === 'scaling' && 'Scaling in progress'}
          {state === 'at_limit' && 'At capacity limit'}
        </span>
      </div>
    </div>
  );
}
