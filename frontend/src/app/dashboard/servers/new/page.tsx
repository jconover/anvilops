'use client';

import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { WizardLayout } from '@/components/server-builder/wizard-layout';
import { useServerForm } from '@/hooks/use-server-form';
import { useCreateServer } from '@/lib/api/hooks';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function NewServerPage() {
  const router = useRouter();
  const toCreateRequest = useServerForm((s) => s.toCreateRequest);
  const resetForm = useServerForm((s) => s.reset);

  const mutation = useCreateServer();

  const handleSubmit = () => {
    const request = toCreateRequest();
    mutation.mutate(request, {
      onSuccess: (data) => {
        toast.success('Server build request submitted', {
          description: `Request ${data.server_name ?? data.id} is now queued.`,
        });
        resetForm();
        // Navigate to the request tracker (build pipeline) page
        router.push(`/dashboard/requests/${data.id}`);
      },
      onError: (error: Error) => {
        toast.error('Failed to submit build request', {
          description: error.message ?? 'An unexpected error occurred.',
        });
      },
    });
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8">
      {/* Page header */}
      <div className="flex items-center gap-4">
        <Button
          variant="ghost"
          size="icon"
          onClick={() => router.back()}
          className="shrink-0"
        >
          <ArrowLeft className="h-5 w-5" />
          <span className="sr-only">Go back</span>
        </Button>
        <div>
          <h1 className="text-2xl font-bold tracking-tight">New Server</h1>
          <p className="text-sm text-muted-foreground">
            Configure and provision a new server on AWS.
          </p>
        </div>
      </div>

      {/* Wizard */}
      <WizardLayout
        onSubmit={handleSubmit}
        isSubmitting={mutation.isPending}
      />
    </div>
  );
}
