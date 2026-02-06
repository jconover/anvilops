'use client';

import { ShieldCheck, ShieldX, Clock, Lock } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { ApprovalQueue } from '@/components/approvals/approval-queue';
import { ApprovalHistory } from '@/components/approvals/approval-history';
import { useAuth } from '@/lib/auth/context';
import { useServers } from '@/lib/api/hooks';

export default function ApprovalsPage() {
  const { user, hasPermission, isLoading: authLoading } = useAuth();

  // Fetch servers by status for each tab
  const {
    data: pendingData,
    isLoading: pendingLoading,
  } = useServers({ status: 'pending' });

  const {
    data: approvedData,
    isLoading: approvedLoading,
  } = useServers({ status: 'approved' });

  // "rejected" is not a formal ServerStatus in the current types, but we
  // fetch with status filter anyway so the backend can return an empty list
  // gracefully. When a reject endpoint is added, this will work out of the box.
  const {
    data: rejectedData,
    isLoading: rejectedLoading,
  } = useServers({ status: 'failed' as any });

  // Auth loading state
  if (authLoading) {
    return (
      <div className="space-y-6 p-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-8 w-48" />
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  // Role gate: only approvers and admins
  const canApprove = hasPermission('servers:approve');
  if (!canApprove) {
    return (
      <div className="flex items-center justify-center min-h-[60vh] p-6">
        <Alert variant="destructive" className="max-w-lg">
          <Lock className="h-4 w-4" />
          <AlertTitle>Access Denied</AlertTitle>
          <AlertDescription>
            You do not have permission to view the approval queue. Only users
            with the <strong>Approver</strong> or <strong>Admin</strong> role can
            review and approve server requests. Contact your administrator if you
            believe this is an error.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const pendingServers = pendingData?.servers ?? [];
  const approvedServers = approvedData?.servers ?? [];
  const rejectedServers = rejectedData?.servers ?? [];

  const pendingCount = pendingData?.total ?? pendingServers.length;

  return (
    <div className="space-y-6 p-6">
      {/* Page header */}
      <div className="flex items-center gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Approval Queue</h1>
          <p className="mt-1 text-muted-foreground">
            Review and approve production and large instance server requests.
          </p>
        </div>
        {pendingCount > 0 && (
          <Badge variant="destructive" className="text-base px-3 py-1">
            {pendingCount} pending
          </Badge>
        )}
      </div>

      {/* Tabs */}
      <Tabs defaultValue="pending" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pending" className="gap-1.5">
            <Clock className="h-4 w-4" />
            Pending
            {pendingCount > 0 && (
              <Badge variant="destructive" className="ml-1 h-5 min-w-[20px] px-1.5 text-xs">
                {pendingCount}
              </Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="approved" className="gap-1.5">
            <ShieldCheck className="h-4 w-4" />
            Approved
          </TabsTrigger>
          <TabsTrigger value="rejected" className="gap-1.5">
            <ShieldX className="h-4 w-4" />
            Rejected
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pending">
          <ApprovalQueue
            servers={pendingServers}
            isLoading={pendingLoading}
          />
        </TabsContent>

        <TabsContent value="approved">
          <ApprovalHistory servers={approvedServers} />
          {approvedLoading && (
            <div className="space-y-4 mt-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="rejected">
          <ApprovalHistory servers={rejectedServers} />
          {rejectedLoading && (
            <div className="space-y-4 mt-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-16 rounded-lg" />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
