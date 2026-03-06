'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { CancelDialog } from '@/components/server-inventory/cancel-dialog';
import { DecommissionDialog } from '@/components/server-inventory/decommission-dialog';
import { useAuth } from '@/lib/auth/context';
import type { ServerResponse } from '@/lib/api/types';
import {
  MoreHorizontal,
  Eye,
  GitBranch,
  Trash2,
  Ban,
  Copy,
} from 'lucide-react';
import { toast } from 'sonner';

interface ServerActionsProps {
  server: ServerResponse;
}

export function ServerActions({ server }: ServerActionsProps) {
  const router = useRouter();
  const { hasPermission } = useAuth();
  const [showCancelDialog, setShowCancelDialog] = useState(false);
  const [showDecommissionDialog, setShowDecommissionDialog] = useState(false);

  const canCancel = hasPermission('servers:delete') && server.status === 'pending';
  const canDecommission = hasPermission('servers:delete');
  const canShowDecommission =
    canDecommission &&
    (server.status === 'ready' || server.status === 'failed');

  const handleCopyName = () => {
    navigator.clipboard.writeText(server.server_name);
    toast.success('Server name copied to clipboard');
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-4 w-4" />
            <span className="sr-only">Open menu</span>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-[180px]">
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              router.push(`/dashboard/servers/${server.id}`);
            }}
          >
            <Eye className="mr-2 h-4 w-4" />
            View Details
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              router.push(`/dashboard/requests/${server.id}`);
            }}
          >
            <GitBranch className="mr-2 h-4 w-4" />
            View Build Pipeline
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={(e) => {
              e.stopPropagation();
              handleCopyName();
            }}
          >
            <Copy className="mr-2 h-4 w-4" />
            Copy Server Name
          </DropdownMenuItem>
          {canCancel && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowCancelDialog(true);
                }}
              >
                <Ban className="mr-2 h-4 w-4" />
                Cancel Request
              </DropdownMenuItem>
            </>
          )}
          {canShowDecommission && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDecommissionDialog(true);
                }}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Decommission Server
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Cancel confirmation dialog */}
      <CancelDialog
        server={server}
        open={showCancelDialog}
        onOpenChange={setShowCancelDialog}
      />

      {/* Decommission confirmation dialog */}
      <DecommissionDialog
        server={server}
        open={showDecommissionDialog}
        onOpenChange={setShowDecommissionDialog}
      />
    </>
  );
}
