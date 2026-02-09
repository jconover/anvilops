'use client';

import { useState } from 'react';
import {
  AlertTriangle,
  Bell,
  BellOff,
  Check,
  Clock,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import type { DriftAlert } from '@/lib/api/drift';

// ---------------------------------------------------------------------------
// Severity styling
// ---------------------------------------------------------------------------

const SEVERITY_STYLE: Record<
  string,
  { border: string; icon: string; bg: string }
> = {
  critical: {
    border: 'border-l-red-500',
    icon: 'text-red-500',
    bg: 'bg-red-50 dark:bg-red-950/20',
  },
  high: {
    border: 'border-l-orange-500',
    icon: 'text-orange-500',
    bg: 'bg-orange-50 dark:bg-orange-950/20',
  },
  medium: {
    border: 'border-l-yellow-500',
    icon: 'text-yellow-500',
    bg: 'bg-yellow-50 dark:bg-yellow-950/20',
  },
  low: {
    border: 'border-l-slate-400',
    icon: 'text-slate-400',
    bg: 'bg-slate-50 dark:bg-slate-900/20',
  },
};

function getSeverityStyle(severity: string) {
  return (
    SEVERITY_STYLE[severity.toLowerCase()] || SEVERITY_STYLE.low
  );
}

function SeverityIcon({ severity }: { severity: string }) {
  const style = getSeverityStyle(severity);
  const s = severity.toLowerCase();

  if (s === 'critical') return <ShieldAlert className={`h-5 w-5 ${style.icon}`} />;
  if (s === 'high') return <AlertTriangle className={`h-5 w-5 ${style.icon}`} />;
  return <Bell className={`h-5 w-5 ${style.icon}`} />;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;

  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;

  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DriftAlertsPanelProps {
  alerts: DriftAlert[];
  onAcknowledge: (alertId: string) => void;
  isAcknowledging?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DriftAlertsPanel({
  alerts,
  onAcknowledge,
  isAcknowledging = false,
}: DriftAlertsPanelProps) {
  const [confirmAlertId, setConfirmAlertId] = useState<string | null>(null);

  const unacknowledged = alerts.filter((a) => !a.is_acknowledged);

  function handleConfirmAcknowledge() {
    if (confirmAlertId) {
      onAcknowledge(confirmAlertId);
      setConfirmAlertId(null);
    }
  }

  return (
    <>
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2 text-base">
              Active Alerts
              {unacknowledged.length > 0 && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1.5 text-[11px] font-bold text-white">
                  {unacknowledged.length}
                </span>
              )}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {unacknowledged.length === 0 ? (
            <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
              <ShieldCheck className="h-8 w-8 text-green-500" />
              <p className="text-sm font-medium text-green-700 dark:text-green-400">
                No active alerts
              </p>
              <p className="text-xs text-muted-foreground">
                All drift alerts have been acknowledged or resolved.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {unacknowledged.map((alert) => {
                const style = getSeverityStyle(alert.severity);
                return (
                  <div
                    key={alert.id}
                    className={`rounded-lg border border-l-4 ${style.border} ${style.bg} p-3 transition-colors`}
                  >
                    <div className="flex items-start gap-3">
                      <SeverityIcon severity={alert.severity} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold leading-tight">
                              {alert.title}
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                              {alert.message}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-2">
                            <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                              <Clock className="h-3 w-3" />
                              {formatTimestamp(alert.created_at)}
                            </span>
                          </div>
                        </div>
                        <div className="mt-2 flex items-center gap-2">
                          <span className="rounded-md bg-background/80 px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            {alert.alert_type}
                          </span>
                          <span className={`rounded-md px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider ${
                            alert.severity === 'critical'
                              ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400'
                              : alert.severity === 'high'
                                ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-400'
                                : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400'
                          }`}>
                            {alert.severity}
                          </span>
                          {alert.server_request_id && (
                            <a
                              href={`/dashboard/requests/${alert.server_request_id}`}
                              className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                            >
                              View Server
                              <ExternalLink className="h-3 w-3" />
                            </a>
                          )}
                          <div className="flex-1" />
                          <Button
                            variant="outline"
                            size="sm"
                            className="h-7 gap-1 px-2 text-xs"
                            onClick={() => setConfirmAlertId(alert.id)}
                            disabled={isAcknowledging}
                          >
                            <Check className="h-3 w-3" />
                            Acknowledge
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Acknowledge confirmation dialog */}
      <AlertDialog
        open={confirmAlertId !== null}
        onOpenChange={(open) => {
          if (!open) setConfirmAlertId(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Acknowledge Alert</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to acknowledge this alert? This will remove
              it from the active alerts list. The underlying drift event will
              still be tracked.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmAcknowledge}>
              Acknowledge
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
