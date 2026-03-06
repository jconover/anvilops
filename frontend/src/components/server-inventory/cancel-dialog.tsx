'use client';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useCancelRequest } from '@/hooks/use-cancel-request';
import type { ServerResponse } from '@/lib/api/types';
import {
  Ban,
  Loader2,
  Server,
} from 'lucide-react';

interface CancelDialogProps {
  server: ServerResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CancelDialog({
  server,
  open,
  onOpenChange,
}: CancelDialogProps) {
  const cancel = useCancelRequest();

  const handleConfirm = () => {
    cancel.mutate(server.id, {
      onSuccess: () => {
        onOpenChange(false);
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-950">
              <Ban className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <DialogTitle>Cancel Server Request</DialogTitle>
              <DialogDescription>
                This will cancel the pending build request.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        {/* Server identity */}
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4 dark:border-amber-900 dark:bg-amber-950/30">
          <div className="flex items-center gap-3">
            <Server className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0" />
            <div>
              <p className="font-mono font-semibold text-sm text-amber-800 dark:text-amber-300">
                {server.server_name}
              </p>
              <p className="text-xs text-amber-600/80 dark:text-amber-400/80">
                {server.environment} &middot; {server.os_type} &middot;{' '}
                {server.instance_size}
              </p>
            </div>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          No infrastructure has been provisioned yet. Cancelling this request
          will prevent the build pipeline from starting. This action cannot be
          undone.
        </p>

        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={cancel.isPending}
          >
            Keep Request
          </Button>
          <Button
            variant="destructive"
            onClick={handleConfirm}
            disabled={cancel.isPending}
          >
            {cancel.isPending ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Cancelling...
              </>
            ) : (
              <>
                <Ban className="mr-2 h-4 w-4" />
                Cancel Request
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
