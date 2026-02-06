'use client';

import {
  Settings,
  LayoutTemplate,
  Cog,
  Activity,
  CheckCircle2,
  XCircle,
  ShieldAlert,
} from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { RoleGate } from '@/components/auth/role-gate';
import { TemplateManagement } from '@/components/admin/template-management';
import { SettingsPanel } from '@/components/admin/settings-panel';

// ---------------------------------------------------------------------------
// System Health (placeholder)
// ---------------------------------------------------------------------------

interface HealthStatus {
  name: string;
  status: 'healthy' | 'degraded' | 'down';
  latency?: string;
  details: string;
}

const SYSTEM_HEALTH: HealthStatus[] = [
  {
    name: 'FastAPI Backend',
    status: 'healthy',
    latency: '12ms',
    details: 'All endpoints responding normally.',
  },
  {
    name: 'PostgreSQL (RDS)',
    status: 'healthy',
    latency: '3ms',
    details: 'Primary instance healthy. 2 read replicas active.',
  },
  {
    name: 'Redis (ElastiCache)',
    status: 'healthy',
    latency: '1ms',
    details: 'Memory usage: 23%. No evictions.',
  },
  {
    name: 'Celery Workers',
    status: 'healthy',
    latency: undefined,
    details: '4 workers online. 0 tasks in queue.',
  },
  {
    name: 'AWX / Ansible Tower',
    status: 'healthy',
    latency: '45ms',
    details: 'Connected. 3 job templates available.',
  },
  {
    name: 'Puppet Enterprise',
    status: 'healthy',
    latency: '78ms',
    details: 'PuppetDB reachable. 10 nodes licensed.',
  },
];

function StatusIcon({ status }: { status: HealthStatus['status'] }) {
  switch (status) {
    case 'healthy':
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case 'degraded':
      return <Activity className="h-4 w-4 text-yellow-500" />;
    case 'down':
      return <XCircle className="h-4 w-4 text-red-500" />;
  }
}

function StatusBadge({ status }: { status: HealthStatus['status'] }) {
  switch (status) {
    case 'healthy':
      return <Badge variant="success">Healthy</Badge>;
    case 'degraded':
      return <Badge variant="warning">Degraded</Badge>;
    case 'down':
      return <Badge variant="destructive">Down</Badge>;
  }
}

function SystemHealthPanel() {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">System Health Overview</CardTitle>
          <CardDescription>
            Real-time status of all platform components. Data shown is
            placeholder for the demo.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {SYSTEM_HEALTH.map((service) => (
              <div
                key={service.name}
                className="flex items-center justify-between rounded-lg border p-4"
              >
                <div className="flex items-center gap-3">
                  <StatusIcon status={service.status} />
                  <div>
                    <p className="text-sm font-medium">{service.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {service.details}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {service.latency && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {service.latency}
                    </span>
                  )}
                  <StatusBadge status={service.status} />
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Platform Versions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {[
              { label: 'AnvilOps API', version: 'v0.1.0' },
              { label: 'AnvilOps UI', version: 'v0.1.0' },
              { label: 'Terraform', version: '1.7.4' },
              { label: 'Ansible / AWX', version: '24.2.0' },
              { label: 'Puppet Enterprise', version: '2023.7' },
              { label: 'PostgreSQL', version: '16.2' },
              { label: 'Redis', version: '7.2' },
              { label: 'Python', version: '3.12' },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">{item.label}</p>
                <p className="mt-0.5 font-mono text-sm font-medium">
                  {item.version}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Admin Page
// ---------------------------------------------------------------------------

function AdminAccessDenied() {
  return (
    <div className="flex flex-col items-center justify-center py-24">
      <ShieldAlert className="h-16 w-16 text-muted-foreground" />
      <h2 className="mt-4 text-xl font-semibold">Access Denied</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        You need administrator privileges to access this page.
      </p>
    </div>
  );
}

export default function AdminPage() {
  return (
    <RoleGate permission="admin:access" fallback={<AdminAccessDenied />}>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2">
            <Settings className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Administration
            </h1>
            <p className="text-sm text-muted-foreground">
              Manage server templates, application settings, and system health
            </p>
          </div>
        </div>

        {/* Tabs */}
        <Tabs defaultValue="templates">
          <TabsList>
            <TabsTrigger value="templates" className="gap-2">
              <LayoutTemplate className="h-4 w-4" />
              Templates
            </TabsTrigger>
            <TabsTrigger value="settings" className="gap-2">
              <Cog className="h-4 w-4" />
              Settings
            </TabsTrigger>
            <TabsTrigger value="system" className="gap-2">
              <Activity className="h-4 w-4" />
              System
            </TabsTrigger>
          </TabsList>

          <TabsContent value="templates" className="mt-6">
            <TemplateManagement />
          </TabsContent>

          <TabsContent value="settings" className="mt-6">
            <SettingsPanel />
          </TabsContent>

          <TabsContent value="system" className="mt-6">
            <SystemHealthPanel />
          </TabsContent>
        </Tabs>
      </div>
    </RoleGate>
  );
}
