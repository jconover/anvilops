'use client';

import Link from 'next/link';
import {
  Server,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Activity,
  Plus,
  ArrowRight,
} from 'lucide-react';

import { useServers } from '@/hooks/use-servers';
import { useComplianceSummary } from '@/hooks/use-compliance';
import { PageHeader } from '@/components/shared/page-header';
import { PageSkeleton } from '@/components/shared/loading-skeleton';
import { StatusBadge } from '@/components/shared/status-badge';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';

/** Stat card shown at the top of the dashboard. */
function StatCard({
  title,
  value,
  description,
  icon: Icon,
  iconClassName,
  href,
}: {
  title: string;
  value: string | number;
  description?: string;
  icon: React.ComponentType<{ className?: string }>;
  iconClassName?: string;
  href?: string;
}) {
  const content = (
    <Card className="relative overflow-hidden transition-colors hover:bg-accent/50">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        <div
          className={cn(
            'flex h-9 w-9 items-center justify-center rounded-lg',
            iconClassName || 'bg-primary/10 text-primary'
          )}
        >
          <Icon className="h-4 w-4" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );

  if (href) {
    return <Link href={href}>{content}</Link>;
  }
  return content;
}

export default function DashboardPage() {
  const {
    data: serverData,
    isLoading: serversLoading,
    error: serversError,
  } = useServers({ limit: 5 });
  const {
    data: complianceData,
    isLoading: complianceLoading,
  } = useComplianceSummary();

  const isLoading = serversLoading || complianceLoading;

  if (isLoading) {
    return (
      <>
        <PageHeader title="Dashboard" description="Overview of your server fleet" />
        <PageSkeleton />
      </>
    );
  }

  const totalServers = serverData?.total ?? 0;
  const servers = serverData?.servers ?? [];

  // Compute active builds: servers in provisioning, configuring, or validating status
  const activeBuilds = servers.filter((s) =>
    ['provisioning', 'configuring', 'validating'].includes(s.status)
  ).length;

  // Compute pending approvals
  const pendingApprovals = servers.filter((s) => s.status === 'pending').length;

  // Compliance rate
  const complianceRate = complianceData?.compliance_rate ?? 0;
  const complianceLabel = `${Math.round(complianceRate)}%`;

  // Recent servers (already limited to 5 from the query)
  const recentServers = servers.slice(0, 5);

  return (
    <>
      <PageHeader title="Dashboard" description="Overview of your server fleet">
        <Link href="/dashboard/servers/new">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            New Server
          </Button>
        </Link>
      </PageHeader>

      {/* ---------------------------------------------------------------- */}
      {/* Summary cards                                                    */}
      {/* ---------------------------------------------------------------- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <StatCard
          title="Total Servers"
          value={totalServers}
          description="Across all environments"
          icon={Server}
          iconClassName="bg-blue-100 text-blue-600 dark:bg-blue-900/50 dark:text-blue-400"
          href="/dashboard/servers"
        />
        <StatCard
          title="Active Builds"
          value={activeBuilds}
          description="Currently provisioning"
          icon={Loader2}
          iconClassName="bg-indigo-100 text-indigo-600 dark:bg-indigo-900/50 dark:text-indigo-400"
          href="/dashboard/requests"
        />
        <StatCard
          title="Pending Approvals"
          value={pendingApprovals}
          description="Awaiting review"
          icon={AlertTriangle}
          iconClassName="bg-yellow-100 text-yellow-600 dark:bg-yellow-900/50 dark:text-yellow-400"
          href="/dashboard/approvals"
        />
        <StatCard
          title="Compliance Rate"
          value={complianceLabel}
          description={`${complianceData?.compliant ?? 0} of ${complianceData?.total ?? 0} nodes compliant`}
          icon={complianceRate >= 90 ? CheckCircle2 : AlertTriangle}
          iconClassName={cn(
            complianceRate >= 90
              ? 'bg-green-100 text-green-600 dark:bg-green-900/50 dark:text-green-400'
              : 'bg-red-100 text-red-600 dark:bg-red-900/50 dark:text-red-400'
          )}
          href="/dashboard/compliance"
        />
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Recent Activity                                                  */}
      {/* ---------------------------------------------------------------- */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-base">Recent Activity</CardTitle>
            <CardDescription>Latest server requests</CardDescription>
          </div>
          <Link href="/dashboard/requests">
            <Button variant="ghost" size="sm" className="text-muted-foreground">
              View all
              <ArrowRight className="ml-1 h-4 w-4" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {serversError ? (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <AlertTriangle className="mr-2 h-4 w-4" />
              Failed to load recent activity.
            </div>
          ) : recentServers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Activity className="mb-3 h-8 w-8 text-muted-foreground/50" />
              <p className="text-sm text-muted-foreground">No server requests yet.</p>
              <Link href="/dashboard/servers/new" className="mt-3">
                <Button variant="outline" size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  Create your first server
                </Button>
              </Link>
            </div>
          ) : (
            <div className="space-y-3">
              {recentServers.map((server) => (
                <Link
                  key={server.id}
                  href={`/dashboard/servers/${server.id}`}
                  className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent/50"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-muted">
                      <Server className="h-4 w-4 text-muted-foreground" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {server.server_name}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {server.environment} &middot; {server.os_type} &middot; {server.region}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <StatusBadge status={server.status} />
                    <span className="hidden text-xs text-muted-foreground sm:inline">
                      {new Date(server.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </>
  );
}
