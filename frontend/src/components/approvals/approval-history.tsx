'use client';

import {
  CheckCircle2,
  XCircle,
  Clock,
  User,
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { ServerResponse } from '@/lib/api/types';

interface ApprovalHistoryProps {
  servers: ServerResponse[];
}

/** Formats an ISO timestamp into a human-readable date/time string. */
function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Formats an ISO timestamp into a relative human-readable string. */
function formatRelativeTime(iso: string): string {
  const now = Date.now();
  const then = new Date(iso).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return formatTimestamp(iso);
}

/**
 * Determines whether a server was "approved" or "rejected" based on its
 * current status. In the real system the backend would provide explicit
 * approval / rejection records; for now we infer from status.
 */
function isApproved(server: ServerResponse): boolean {
  // Anything that made it past "pending" (and is not a direct rejection) is
  // considered approved.
  return server.status !== 'pending';
}

export function ApprovalHistory({ servers }: ApprovalHistoryProps) {
  if (servers.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No approval history yet.
        </CardContent>
      </Card>
    );
  }

  // Sort newest first by updated_at
  const sorted = [...servers].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Approval History</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-[15px] top-0 bottom-0 w-px bg-border" />

          <div className="flex flex-col gap-6">
            {sorted.map((server) => {
              const approved = isApproved(server);
              return (
                <div key={server.id} className="relative flex gap-4 pl-1">
                  {/* Timeline dot */}
                  <div
                    className={`relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 bg-background ${
                      approved
                        ? 'border-green-500 text-green-600'
                        : 'border-red-500 text-red-600'
                    }`}
                  >
                    {approved ? (
                      <CheckCircle2 className="h-4 w-4" />
                    ) : (
                      <XCircle className="h-4 w-4" />
                    )}
                  </div>

                  {/* Entry content */}
                  <div className="flex flex-col gap-1 min-w-0 pt-0.5">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm">
                        {server.server_name}
                      </span>
                      <span
                        className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          approved
                            ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300'
                            : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300'
                        }`}
                      >
                        {approved ? 'Approved' : 'Rejected'}
                      </span>
                    </div>

                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="inline-flex items-center gap-1">
                        <User className="h-3 w-3" />
                        Approver
                      </span>
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {formatRelativeTime(server.updated_at)}
                      </span>
                    </div>

                    {/* Show status message as reason if available */}
                    {server.status_message && (
                      <p className="mt-1 text-xs text-muted-foreground italic">
                        {server.status_message}
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
