'use client';

import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

const STATUS_STYLES: Record<string, { className: string; label: string }> = {
  pending: {
    className: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
    label: 'Pending',
  },
  approved: {
    className: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
    label: 'Approved',
  },
  provisioning: {
    className: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200',
    label: 'Provisioning',
  },
  configuring: {
    className: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200',
    label: 'Configuring',
  },
  validating: {
    className: 'bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200',
    label: 'Validating',
  },
  ready: {
    className: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    label: 'Ready',
  },
  failed: {
    className: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    label: 'Failed',
  },
  decommissioning: {
    className: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
    label: 'Decommissioning',
  },
  decommissioned: {
    className: 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200',
    label: 'Decommissioned',
  },
};

interface StatusBadgeProps {
  status: string;
  className?: string;
  pulse?: boolean;
}

export function StatusBadge({ status, className, pulse }: StatusBadgeProps) {
  const style = STATUS_STYLES[status] || {
    className: 'bg-gray-100 text-gray-800',
    label: status,
  };
  const isActive = ['provisioning', 'configuring', 'validating', 'decommissioning'].includes(
    status
  );

  return (
    <Badge
      variant="outline"
      className={cn(
        style.className,
        'border-0 font-medium',
        (pulse || isActive) && 'animate-pulse',
        className
      )}
    >
      {style.label}
    </Badge>
  );
}
