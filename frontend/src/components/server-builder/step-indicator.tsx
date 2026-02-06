'use client';

import { Check } from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Step metadata
// ---------------------------------------------------------------------------

const STEPS = [
  { title: 'Environment & OS', description: 'Region, OS, and target environment' },
  { title: 'Instance Config', description: 'Size, VPC, and server naming' },
  { title: 'Security', description: 'Security profile and domain join' },
  { title: 'Software & Config', description: 'Puppet role and packages' },
  { title: 'Review & Submit', description: 'Confirm and launch the build' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface StepIndicatorProps {
  currentStep: number;
  onStepClick: (step: number) => void;
}

export function StepIndicator({ currentStep, onStepClick }: StepIndicatorProps) {
  return (
    <nav aria-label="Wizard steps" className="flex flex-col gap-1">
      {STEPS.map((step, index) => {
        const isCompleted = index < currentStep;
        const isCurrent = index === currentStep;
        const isFuture = index > currentStep;

        return (
          <button
            key={step.title}
            type="button"
            onClick={() => {
              if (isCompleted) onStepClick(index);
            }}
            disabled={isFuture}
            className={cn(
              'group flex items-start gap-3 rounded-lg px-3 py-3 text-left transition-colors',
              isCompleted && 'cursor-pointer hover:bg-muted/60',
              isCurrent && 'bg-primary/5',
              isFuture && 'cursor-default opacity-50',
            )}
          >
            {/* Step circle */}
            <div
              className={cn(
                'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-semibold transition-colors',
                isCompleted &&
                  'border-green-500 bg-green-500 text-white',
                isCurrent &&
                  'border-primary bg-primary text-primary-foreground',
                isFuture && 'border-muted-foreground/30 text-muted-foreground/50',
              )}
            >
              {isCompleted ? (
                <Check className="h-4 w-4" />
              ) : (
                <span>{index + 1}</span>
              )}
            </div>

            {/* Labels */}
            <div className="flex flex-col">
              <span
                className={cn(
                  'text-sm font-medium leading-tight',
                  isCurrent && 'text-foreground',
                  isCompleted && 'text-foreground',
                  isFuture && 'text-muted-foreground',
                )}
              >
                {step.title}
              </span>
              <span className="mt-0.5 text-xs text-muted-foreground">
                {step.description}
              </span>
            </div>
          </button>
        );
      })}
    </nav>
  );
}
