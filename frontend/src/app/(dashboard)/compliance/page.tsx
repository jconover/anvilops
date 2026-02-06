'use client';

import { useState, useEffect } from 'react';
import { Download, RefreshCw, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { useComplianceSummary } from '@/lib/api/hooks';
import { ComplianceSummary } from '@/components/compliance/compliance-summary';
import { ComplianceGauge } from '@/components/compliance/compliance-gauge';
import { NodeComplianceTable } from '@/components/compliance/node-compliance-table';

const STATUS_FILTERS = [
  { value: 'all', label: 'All Statuses' },
  { value: 'compliant', label: 'Compliant' },
  { value: 'changed', label: 'Changed' },
  { value: 'failed', label: 'Failed' },
  { value: 'unresponsive', label: 'Unresponsive' },
] as const;

export default function ComplianceDashboardPage() {
  const [statusFilter, setStatusFilter] = useState('all');
  const { data, isLoading, isError, refetch, dataUpdatedAt } =
    useComplianceSummary();

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refetch();
    }, 30_000);
    return () => clearInterval(interval);
  }, [refetch]);

  function handleDownloadReport() {
    if (!data) return;

    const report = {
      generated_at: new Date().toISOString(),
      compliance_rate: data.compliance_rate,
      total: data.total,
      compliant: data.compliant,
      changed: data.changed,
      failed: data.failed,
      unresponsive: data.unresponsive,
      nodes: data.nodes,
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `compliance-report-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2">
            <ShieldCheck className="h-6 w-6 text-primary" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Compliance Dashboard
            </h1>
            <p className="text-sm text-muted-foreground">
              Fleet-wide Puppet compliance monitoring and drift detection
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {dataUpdatedAt > 0 && (
            <span className="text-xs text-muted-foreground">
              Updated {new Date(dataUpdatedAt).toLocaleTimeString()}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            className="gap-2"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
          <Button
            size="sm"
            onClick={handleDownloadReport}
            disabled={!data}
            className="gap-2"
          >
            <Download className="h-3.5 w-3.5" />
            Download Report
          </Button>
        </div>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            <Skeleton className="h-64 lg:col-span-1" />
            <Skeleton className="h-64 lg:col-span-3" />
          </div>
        </div>
      )}

      {/* Error State */}
      {isError && !isLoading && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <ShieldCheck className="h-12 w-12 text-muted-foreground" />
            <div className="text-center">
              <p className="font-medium">Unable to load compliance data</p>
              <p className="mt-1 text-sm text-muted-foreground">
                The compliance API may be unavailable. Check your connection and
                try again.
              </p>
            </div>
            <Button variant="outline" onClick={() => refetch()}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Data Loaded */}
      {data && !isLoading && (
        <>
          {/* Summary Cards */}
          <ComplianceSummary
            total={data.total}
            compliant={data.compliant}
            changed={data.changed}
            failed={data.failed}
            unresponsive={data.unresponsive}
            complianceRate={data.compliance_rate}
          />

          {/* Gauge + Table */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
            {/* Gauge */}
            <Card className="flex items-center justify-center lg:col-span-1">
              <CardContent className="py-8">
                <ComplianceGauge percentage={data.compliance_rate} />
              </CardContent>
            </Card>

            {/* Node Table */}
            <Card className="lg:col-span-3">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-4">
                <CardTitle className="text-base">Node Compliance</CardTitle>
                <Select value={statusFilter} onValueChange={setStatusFilter}>
                  <SelectTrigger className="w-[180px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {STATUS_FILTERS.map((filter) => (
                      <SelectItem key={filter.value} value={filter.value}>
                        {filter.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </CardHeader>
              <CardContent>
                <NodeComplianceTable
                  nodes={data.nodes}
                  statusFilter={statusFilter}
                />
              </CardContent>
            </Card>
          </div>

          {/* Generated At Footer */}
          <p className="text-center text-xs text-muted-foreground">
            Report generated at{' '}
            {new Date(data.generated_at).toLocaleString()}
          </p>
        </>
      )}
    </div>
  );
}
