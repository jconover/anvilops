'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/shared/page-header';
import { ScalingCard } from '@/components/scaling/scaling-card';
import {
  useScalingGroups,
  useScaleGroup,
  usePauseGroup,
  useResumeGroup,
} from '@/lib/api/scaling';
import { AlertCircle, Layers, Plus } from 'lucide-react';
import { toast } from 'sonner';

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function ScalingGroupsPage() {
  const { data: groups, isLoading, isError, error } = useScalingGroups();

  const scaleMutation = useScaleGroup();
  const pauseMutation = usePauseGroup();
  const resumeMutation = useResumeGroup();

  const handleScale = (id: string, desiredCount: number) => {
    scaleMutation.mutate(
      { id, desiredCount },
      {
        onSuccess: (group) => {
          toast.success(`Scaling ${group.name} to ${desiredCount} instances`);
        },
        onError: (err) => {
          toast.error('Failed to scale group', {
            description: err.message ?? 'An unexpected error occurred.',
          });
        },
      },
    );
  };

  const handlePause = (id: string) => {
    pauseMutation.mutate(id, {
      onSuccess: (group) => {
        toast.success(`Paused scaling for ${group.name}`);
      },
      onError: (err) => {
        toast.error('Failed to pause group', {
          description: err.message ?? 'An unexpected error occurred.',
        });
      },
    });
  };

  const handleResume = (id: string) => {
    resumeMutation.mutate(id, {
      onSuccess: (group) => {
        toast.success(`Resumed scaling for ${group.name}`);
      },
      onError: (err) => {
        toast.error('Failed to resume group', {
          description: err.message ?? 'An unexpected error occurred.',
        });
      },
    });
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Auto Scaling Groups"
        description="Create and manage auto scaling groups for your server fleet."
      >
        <Button asChild size="sm">
          <Link href="/dashboard/scaling/new">
            <Plus className="mr-2 h-4 w-4" />
            Create Group
          </Link>
        </Button>
      </PageHeader>

      {/* Error state */}
      {isError && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
          <AlertCircle className="h-5 w-5 text-red-500" />
          <div>
            <p className="text-sm font-medium text-red-800 dark:text-red-300">
              Failed to load scaling groups
            </p>
            <p className="mt-0.5 text-xs text-red-700 dark:text-red-400">
              {error instanceof Error
                ? error.message
                : 'An unexpected error occurred.'}
            </p>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[260px] rounded-lg" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && !isError && groups?.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-16 text-center">
          <Layers className="h-12 w-12 text-muted-foreground/50 mb-4" />
          <h3 className="text-lg font-semibold">No scaling groups yet</h3>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm">
            Create your first auto scaling group to automatically manage server
            capacity across your environments.
          </p>
          <Button asChild className="mt-6" size="sm">
            <Link href="/dashboard/scaling/new">
              <Plus className="mr-2 h-4 w-4" />
              Create Group
            </Link>
          </Button>
        </div>
      )}

      {/* Cards grid */}
      {!isLoading && groups && groups.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((group) => (
            <ScalingCard
              key={group.id}
              group={group}
              onScale={handleScale}
              onPause={handlePause}
              onResume={handleResume}
              isScaling={
                scaleMutation.isPending &&
                scaleMutation.variables?.id === group.id
              }
              isPausing={
                pauseMutation.isPending &&
                pauseMutation.variables === group.id
              }
              isResuming={
                resumeMutation.isPending &&
                resumeMutation.variables === group.id
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
