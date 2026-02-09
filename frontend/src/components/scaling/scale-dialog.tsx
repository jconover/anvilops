'use client';

import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Loader2, Minus, Plus, TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScaleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  groupName: string;
  currentCount: number;
  minInstances: number;
  maxInstances: number;
  onConfirm: (desiredCount: number) => void;
  isLoading?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Dialog for manually scaling a group.
 *
 * Provides a number input with +/- buttons, respects min/max bounds,
 * and shows a preview of the resulting action (e.g. "Will create 2 new servers").
 */
export function ScaleDialog({
  open,
  onOpenChange,
  groupName,
  currentCount,
  minInstances,
  maxInstances,
  onConfirm,
  isLoading = false,
}: ScaleDialogProps) {
  const [desiredCount, setDesiredCount] = useState(currentCount);

  // Reset desired count when dialog opens with new values.
  const handleOpenChange = (nextOpen: boolean) => {
    if (nextOpen) {
      setDesiredCount(currentCount);
    }
    onOpenChange(nextOpen);
  };

  const diff = desiredCount - currentCount;
  const isScaleUp = diff > 0;
  const isScaleDown = diff < 0;
  const isNoChange = diff === 0;

  const clamp = (value: number) =>
    Math.min(maxInstances, Math.max(minInstances, value));

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = parseInt(e.target.value, 10);
    if (isNaN(raw)) return;
    setDesiredCount(clamp(raw));
  };

  const increment = () => setDesiredCount((c) => clamp(c + 1));
  const decrement = () => setDesiredCount((c) => clamp(c - 1));

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Scale Group</DialogTitle>
          <DialogDescription>
            Adjust the desired instance count for{' '}
            <span className="font-medium text-foreground">{groupName}</span>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 py-4">
          {/* Current state */}
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Current instances</span>
            <span className="font-semibold">{currentCount}</span>
          </div>

          {/* Desired count input */}
          <div className="space-y-2">
            <Label htmlFor="desired-count">Desired count</Label>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="icon"
                onClick={decrement}
                disabled={desiredCount <= minInstances || isLoading}
                className="shrink-0"
              >
                <Minus className="h-4 w-4" />
                <span className="sr-only">Decrease</span>
              </Button>
              <Input
                id="desired-count"
                type="number"
                min={minInstances}
                max={maxInstances}
                value={desiredCount}
                onChange={handleInputChange}
                disabled={isLoading}
                className="text-center text-lg font-semibold"
              />
              <Button
                variant="outline"
                size="icon"
                onClick={increment}
                disabled={desiredCount >= maxInstances || isLoading}
                className="shrink-0"
              >
                <Plus className="h-4 w-4" />
                <span className="sr-only">Increase</span>
              </Button>
            </div>
            <p className="text-xs text-muted-foreground text-center">
              Range: {minInstances} (min) &ndash; {maxInstances} (max)
            </p>
          </div>

          {/* Preview message */}
          <div
            className={cn(
              'rounded-lg border p-3 text-sm',
              isScaleUp && 'border-green-200 bg-green-50 dark:border-green-900 dark:bg-green-950/30',
              isScaleDown && 'border-orange-200 bg-orange-50 dark:border-orange-900 dark:bg-orange-950/30',
              isNoChange && 'border-muted bg-muted/30',
            )}
          >
            {isScaleUp && (
              <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
                <TrendingUp className="h-4 w-4 shrink-0" />
                <span>
                  Will create <strong>{diff}</strong> new server
                  {diff > 1 ? 's' : ''}
                </span>
              </div>
            )}
            {isScaleDown && (
              <div className="flex items-center gap-2 text-orange-700 dark:text-orange-400">
                <TrendingDown className="h-4 w-4 shrink-0" />
                <span>
                  Will remove <strong>{Math.abs(diff)}</strong> server
                  {Math.abs(diff) > 1 ? 's' : ''}
                </span>
              </div>
            )}
            {isNoChange && (
              <span className="text-muted-foreground">
                No change from current count.
              </span>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={() => onConfirm(desiredCount)}
            disabled={isNoChange || isLoading}
          >
            {isLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {isScaleUp ? 'Scale Up' : isScaleDown ? 'Scale Down' : 'Confirm'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
