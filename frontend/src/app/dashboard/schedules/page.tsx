'use client';

import { useState } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { PageHeader } from '@/components/shared/page-header';
import { ConfirmationDialog } from '@/components/shared/confirmation-dialog';
import { ScheduleCard } from '@/components/schedules/schedule-card';
import {
  useSchedules,
  usePauseSchedule,
  useResumeSchedule,
  useRunNow,
  useDeleteSchedule,
  type ScheduleStatus,
  type ScheduleListParams,
} from '@/lib/api/schedules';
import { Calendar, Plus } from 'lucide-react';

// ---------------------------------------------------------------------------
// Filter tabs
// ---------------------------------------------------------------------------

type FilterTab = 'all' | ScheduleStatus;

const FILTER_TABS: { value: FilterTab; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'paused', label: 'Paused' },
  { value: 'completed', label: 'Completed' },
];

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function SchedulesPage() {
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  // Build params from active filter tab
  const params: ScheduleListParams | undefined =
    activeTab !== 'all' ? { status: activeTab as ScheduleStatus } : undefined;

  const { data, isLoading } = useSchedules(params);
  const pauseMutation = usePauseSchedule();
  const resumeMutation = useResumeSchedule();
  const runNowMutation = useRunNow();
  const deleteMutation = useDeleteSchedule();

  const schedules = data?.schedules ?? [];

  // ------------------------------------------------------------------
  // Action handlers
  // ------------------------------------------------------------------

  const handlePause = (id: string) => {
    pauseMutation.mutate(id, {
      onSuccess: () => toast.success('Schedule paused'),
      onError: (err) =>
        toast.error('Failed to pause schedule', {
          description: err.message,
        }),
    });
  };

  const handleResume = (id: string) => {
    resumeMutation.mutate(id, {
      onSuccess: () => toast.success('Schedule resumed'),
      onError: (err) =>
        toast.error('Failed to resume schedule', {
          description: err.message,
        }),
    });
  };

  const handleRunNow = (id: string) => {
    runNowMutation.mutate(id, {
      onSuccess: () =>
        toast.success('Execution triggered', {
          description: 'The schedule is running now.',
        }),
      onError: (err) =>
        toast.error('Failed to trigger execution', {
          description: err.message,
        }),
    });
  };

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return;
    deleteMutation.mutate(deleteTarget, {
      onSuccess: () => {
        toast.success('Schedule deleted');
        setDeleteTarget(null);
      },
      onError: (err) =>
        toast.error('Failed to delete schedule', {
          description: err.message,
        }),
    });
  };

  return (
    <div className="space-y-6">
      {/* Page header */}
      <PageHeader
        title="Scheduled Builds"
        description="Schedule server provisioning for future times or recurring intervals."
      >
        <Button asChild size="sm">
          <Link href="/dashboard/schedules/new">
            <Plus className="mr-2 h-4 w-4" />
            New Schedule
          </Link>
        </Button>
      </PageHeader>

      {/* Filter tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(v) => setActiveTab(v as FilterTab)}
      >
        <TabsList>
          {FILTER_TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {/* Loading state */}
      {isLoading && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-[220px] rounded-lg" />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!isLoading && schedules.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed p-12 text-center">
          <Calendar className="mb-4 h-12 w-12 text-muted-foreground/50" />
          <h3 className="text-lg font-semibold">No schedules found</h3>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            {activeTab === 'all'
              ? 'Create your first scheduled build to provision servers automatically.'
              : `No ${activeTab} schedules. Try a different filter or create a new schedule.`}
          </p>
          <Button asChild className="mt-4" size="sm">
            <Link href="/dashboard/schedules/new">
              <Plus className="mr-2 h-4 w-4" />
              New Schedule
            </Link>
          </Button>
        </div>
      )}

      {/* Schedule cards */}
      {!isLoading && schedules.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {schedules.map((schedule) => (
            <ScheduleCard
              key={schedule.id}
              schedule={schedule}
              onPause={handlePause}
              onResume={handleResume}
              onRunNow={handleRunNow}
              onDelete={(id) => setDeleteTarget(id)}
            />
          ))}
        </div>
      )}

      {/* Delete confirmation dialog */}
      <ConfirmationDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete Schedule"
        description="Are you sure you want to delete this schedule? This action cannot be undone. Future scheduled executions will be cancelled."
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={handleDeleteConfirm}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
