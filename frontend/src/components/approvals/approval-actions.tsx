'use client';

import { useState } from 'react';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Textarea } from '@/components/ui/textarea';
import { useApproveServer } from '@/lib/api/hooks';

interface ApprovalActionsProps {
  serverId: string;
  serverName: string;
  onActionComplete?: () => void;
}

export function ApprovalActions({
  serverId,
  serverName,
  onActionComplete,
}: ApprovalActionsProps) {
  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const approveMutation = useApproveServer();

  function handleApprove() {
    approveMutation.mutate(serverId, {
      onSuccess: () => {
        toast.success('Server request approved', {
          description: `${serverName} has been approved and the build pipeline will start shortly.`,
        });
        setApproveOpen(false);
        onActionComplete?.();
      },
      onError: (error) => {
        toast.error('Failed to approve request', {
          description: error.message || 'An unexpected error occurred. Please try again.',
        });
      },
    });
  }

  function handleReject() {
    // TODO: Wire up a reject endpoint when the backend supports it.
    // For now, simulate the rejection flow for the UI.
    toast.success('Server request rejected', {
      description: `${serverName} has been rejected.${rejectReason ? ` Reason: ${rejectReason}` : ''}`,
    });
    setRejectReason('');
    setRejectOpen(false);
    onActionComplete?.();
  }

  const isLoading = approveMutation.isPending;

  return (
    <div className="flex items-center gap-2">
      {/* Approve Dialog */}
      <Dialog open={approveOpen} onOpenChange={setApproveOpen}>
        <DialogTrigger asChild>
          <Button
            size="sm"
            className="bg-green-600 hover:bg-green-700 text-white"
            disabled={isLoading}
          >
            {isLoading ? (
              <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
            ) : (
              <CheckCircle2 className="mr-1.5 h-4 w-4" />
            )}
            Approve
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Approve Server Request</DialogTitle>
            <DialogDescription>
              Are you sure you want to approve <strong>{serverName}</strong>?
              This will trigger the build pipeline and begin provisioning the
              server on AWS.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setApproveOpen(false)}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              className="bg-green-600 hover:bg-green-700 text-white"
              onClick={handleApprove}
              disabled={isLoading}
            >
              {isLoading ? (
                <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              ) : (
                <CheckCircle2 className="mr-1.5 h-4 w-4" />
              )}
              Confirm Approval
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reject Dialog */}
      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogTrigger asChild>
          <Button size="sm" variant="destructive" disabled={isLoading}>
            <XCircle className="mr-1.5 h-4 w-4" />
            Reject
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reject Server Request</DialogTitle>
            <DialogDescription>
              Provide a reason for rejecting <strong>{serverName}</strong>. The
              requester will be notified with this explanation.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4">
            <Textarea
              placeholder="Reason for rejection (required)..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setRejectReason('');
                setRejectOpen(false);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleReject}
              disabled={!rejectReason.trim()}
            >
              <XCircle className="mr-1.5 h-4 w-4" />
              Confirm Rejection
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
