'use client';

import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  WifiOff,
  Server,
} from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';

interface ComplianceSummaryProps {
  total: number;
  compliant: number;
  changed: number;
  failed: number;
  unresponsive: number;
  complianceRate: number;
}

interface StatCardProps {
  label: string;
  count: number;
  icon: React.ReactNode;
  colorClass: string;
  bgClass: string;
}

function StatCard({ label, count, icon, colorClass, bgClass }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-muted-foreground">{label}</p>
            <p className={`mt-1 text-3xl font-bold ${colorClass}`}>{count}</p>
          </div>
          <div className={`rounded-full p-3 ${bgClass}`}>{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function getRateColor(rate: number): string {
  if (rate >= 90) return 'text-green-600 dark:text-green-400';
  if (rate >= 70) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
}

function getRateBg(rate: number): string {
  if (rate >= 90) return 'bg-green-50 dark:bg-green-950';
  if (rate >= 70) return 'bg-yellow-50 dark:bg-yellow-950';
  return 'bg-red-50 dark:bg-red-950';
}

export function ComplianceSummary({
  total,
  compliant,
  changed,
  failed,
  unresponsive,
  complianceRate,
}: ComplianceSummaryProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Total Nodes"
          count={total}
          icon={<Server className="h-5 w-5 text-slate-600 dark:text-slate-400" />}
          colorClass="text-foreground"
          bgClass="bg-slate-100 dark:bg-slate-800"
        />
        <StatCard
          label="Compliant"
          count={compliant}
          icon={<CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400" />}
          colorClass="text-green-600 dark:text-green-400"
          bgClass="bg-green-50 dark:bg-green-950"
        />
        <StatCard
          label="Changed"
          count={changed}
          icon={<AlertTriangle className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />}
          colorClass="text-yellow-600 dark:text-yellow-400"
          bgClass="bg-yellow-50 dark:bg-yellow-950"
        />
        <StatCard
          label="Failed"
          count={failed}
          icon={<XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />}
          colorClass="text-red-600 dark:text-red-400"
          bgClass="bg-red-50 dark:bg-red-950"
        />
        <StatCard
          label="Unresponsive"
          count={unresponsive}
          icon={<WifiOff className="h-5 w-5 text-gray-500 dark:text-gray-400" />}
          colorClass="text-gray-500 dark:text-gray-400"
          bgClass="bg-gray-100 dark:bg-gray-800"
        />
      </div>

      <Card>
        <CardContent className="flex items-center gap-3 p-4">
          <span className="text-sm font-medium text-muted-foreground">
            Fleet Compliance Rate:
          </span>
          <span className={`text-lg font-bold ${getRateColor(complianceRate)}`}>
            {complianceRate.toFixed(1)}%
          </span>
          <div className="ml-2 h-2 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className={`h-full rounded-full transition-all duration-700 ease-out ${
                complianceRate >= 90
                  ? 'bg-green-500'
                  : complianceRate >= 70
                    ? 'bg-yellow-500'
                    : 'bg-red-500'
              }`}
              style={{ width: `${Math.min(complianceRate, 100)}%` }}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
