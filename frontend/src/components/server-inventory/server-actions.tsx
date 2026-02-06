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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useDeleteServer } from '@/lib/api/hooks';
import { useAuth } from '@/lib/auth/context';
import type { ServerResponse } from '@/lib/api/types';
import {
  MoreHorizontal,
  Eye,
  GitBranch,
  Trash2,
  Copy,
} from 'lucide-react';
import { toast } from 'sonner';

interface ServerActionsProps {
  server: ServerResponse;
}

export function ServerActions({ server }: ServerActionsProps) {
  const router = useRouter();
  const { hasPermission } = useAuth();
  const deleteServer = useDeleteServer();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);

  const canDelete = hasPermission('servers:delete');

  const handleCopyName = () => {
    navigator.clipboard.writeText(server.server_name);
    toast.success('Server name copied to clipboard');
  };

  const handleDelete = () => {
    deleteServer.mutate(server.id, {
      onSuccess: () => {
        toast.success(`Server ${server.server_name} decommission initiated`);
        setShowDeleteDialog(false);
      },
      onError: () => {
        toast.error('Failed to delete server');
      },
    });
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
          {canDelete && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDeleteDialog(true);
                }}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete Server
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Delete confirmation dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent onClick={(e) => e.stopPropagation()}>
          <DialogHeader>
            <DialogTitle>Delete Server</DialogTitle>
            <DialogDescription>
              Are you sure you want to decommission{' '}
              <span className="font-semibold text-foreground">
                {server.server_name}
              </span>
              ? This will initiate the full decommission workflow: Ansible
              decommission playbook, Terraform destroy, DNS cleanup, and Puppet
              node purge. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={deleteServer.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteServer.isPending}
            >
              {deleteServer.isPending ? 'Deleting...' : 'Delete Server'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
