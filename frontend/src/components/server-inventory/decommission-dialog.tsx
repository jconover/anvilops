'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useDecommission } from '@/hooks/use-decommission';
import type { ServerResponse } from '@/lib/api/types';
import {
  AlertTriangle,
  Trash2,
  Server,
  HardDrive,
  Shield,
  Globe,
  Wrench,
  ChevronRight,
  Loader2,
  XCircle,
} from 'lucide-react';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DecommissionDialogProps {
  server: ServerResponse;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

// ---------------------------------------------------------------------------
// Cleanup items shown to the user
// ---------------------------------------------------------------------------

const CLEANUP_ITEMS = [
  {
    icon: Server,
    label: 'EC2 instance will be terminated',
    description: 'The virtual machine and all running processes will be stopped permanently.',
  },
  {
    icon: HardDrive,
    label: 'EBS volumes will be deleted',
    description: 'All attached storage volumes and their data will be permanently destroyed.',
  },
  {
    icon: Shield,
    label: 'Security groups will be removed',
    description: 'Firewall rules associated with this server will be cleaned up.',
  },
  {
    icon: Globe,
    label: 'DNS records will be cleaned up',
    description: 'All DNS entries pointing to this server will be removed.',
  },
  {
    icon: XCircle,
    label: 'Puppet node will be purged',
    description: 'The node certificate and classification will be revoked and removed from Puppet Enterprise.',
  },
  {
    icon: Wrench,
    label: 'AWX host will be removed',
    description: 'The host entry and job history in AWX will be cleaned up.',
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DecommissionDialog({
  server,
  open,
  onOpenChange,
}: DecommissionDialogProps) {
  const [step, setStep] = useState<1 | 2>(1);
  const [confirmationText, setConfirmationText] = useState('');
  const decommission = useDecommission();

  const nameMatches = confirmationText === server.server_name;

  // Reset state when the dialog is opened/closed
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      // Small delay so the closing animation plays before we reset
      setTimeout(() => {
        setStep(1);
        setConfirmationText('');
      }, 200);
    }
    onOpenChange(nextOpen);
  };

  const handleConfirm = () => {
    if (!nameMatches) return;
    decommission.mutate(server.id, {
      onSuccess: () => {
        handleOpenChange(false);
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent
        className="sm:max-w-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* ---------------------------------------------------------------- */}
        {/* Step 1: Warning & overview                                       */}
        {/* ---------------------------------------------------------------- */}
        {step === 1 && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-950">
                  <Trash2 className="h-5 w-5 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <DialogTitle className="text-red-600 dark:text-red-400">
                    Decommission Server
                  </DialogTitle>
                  <DialogDescription>
                    This action is permanent and cannot be undone.
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            {/* Server identity */}
            <div className="rounded-md border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
              <div className="flex items-center gap-3">
                <Server className="h-5 w-5 text-red-600 dark:text-red-400 flex-shrink-0" />
                <div>
                  <p className="font-mono font-semibold text-sm text-red-800 dark:text-red-300">
                    {server.server_name}
                  </p>
                  <p className="text-xs text-red-600/80 dark:text-red-400/80">
                    {server.environment} &middot; {server.region}
                    {server.aws_instance_id && (
                      <> &middot; {server.aws_instance_id}</>
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* What will be destroyed */}
            <div className="space-y-3">
              <p className="text-sm font-medium text-red-700 dark:text-red-400">
                The following resources will be permanently destroyed:
              </p>
              <div className="space-y-2">
                {CLEANUP_ITEMS.map((item) => (
                  <div
                    key={item.label}
                    className="flex items-start gap-3 rounded-md border border-border/50 bg-muted/30 px-3 py-2.5"
                  >
                    <item.icon className="h-4 w-4 mt-0.5 text-red-500 dark:text-red-400 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium leading-tight">
                        {item.label}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {item.description}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <Separator />

            <div className="flex items-center gap-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 dark:bg-amber-950/30 dark:border-amber-800">
              <AlertTriangle className="h-4 w-4 text-amber-600 dark:text-amber-400 flex-shrink-0" />
              <p className="text-xs text-amber-800 dark:text-amber-300">
                The decommission pipeline will execute: Puppet Purge, AWX
                Decommission, Terraform Destroy, and DNS Cleanup. This process
                typically takes 5-10 minutes.
              </p>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => handleOpenChange(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => setStep(2)}
              >
                I understand, continue
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </DialogFooter>
          </>
        )}

        {/* ---------------------------------------------------------------- */}
        {/* Step 2: Type server name to confirm                              */}
        {/* ---------------------------------------------------------------- */}
        {step === 2 && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-2">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-red-100 dark:bg-red-950">
                  <AlertTriangle className="h-5 w-5 text-red-600 dark:text-red-400" />
                </div>
                <div>
                  <DialogTitle className="text-red-600 dark:text-red-400">
                    Confirm Decommission
                  </DialogTitle>
                  <DialogDescription>
                    Type the server name to confirm this irreversible action.
                  </DialogDescription>
                </div>
              </div>
            </DialogHeader>

            <div className="space-y-4">
              <div className="rounded-md border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-red-950/30">
                <p className="text-sm text-red-800 dark:text-red-300">
                  To confirm, type{' '}
                  <Badge
                    variant="destructive"
                    className="font-mono text-xs px-1.5 py-0"
                  >
                    {server.server_name}
                  </Badge>{' '}
                  below.
                </p>
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="confirm-server-name"
                  className="text-sm font-medium"
                >
                  Server name
                </Label>
                <Input
                  id="confirm-server-name"
                  placeholder={server.server_name}
                  value={confirmationText}
                  onChange={(e) => setConfirmationText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && nameMatches) {
                      handleConfirm();
                    }
                  }}
                  className={
                    confirmationText.length > 0 && !nameMatches
                      ? 'border-red-500 focus-visible:ring-red-500'
                      : confirmationText.length > 0 && nameMatches
                        ? 'border-green-500 focus-visible:ring-green-500'
                        : ''
                  }
                  autoComplete="off"
                  autoFocus
                  disabled={decommission.isPending}
                />
                {confirmationText.length > 0 && !nameMatches && (
                  <p className="text-xs text-red-500">
                    Server name does not match. Please type it exactly as shown.
                  </p>
                )}
              </div>
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => {
                  setStep(1);
                  setConfirmationText('');
                }}
                disabled={decommission.isPending}
              >
                Back
              </Button>
              <Button
                variant="destructive"
                onClick={handleConfirm}
                disabled={!nameMatches || decommission.isPending}
              >
                {decommission.isPending ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Decommissioning...
                  </>
                ) : (
                  <>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Decommission Server
                  </>
                )}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
