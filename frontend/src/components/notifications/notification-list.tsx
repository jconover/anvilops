'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bell,
  CheckSquare,
  Hammer,
  Shield,
  Trash2,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Inbox,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import {
  useNotifications,
  useMarkAsRead,
  useDeleteNotification,
  type NotificationItem,
  type NotificationListParams,
} from '@/lib/api/notifications';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// ---------------------------------------------------------------------------
// Icon & color mappings
// ---------------------------------------------------------------------------

const CATEGORY_ICONS: Record<string, LucideIcon> = {
  build: Hammer,
  approval: CheckSquare,
  compliance: Shield,
  system: Bell,
};

const SEVERITY_COLORS: Record<string, string> = {
  success: 'text-emerald-500',
  warning: 'text-amber-500',
  error: 'text-red-500',
  info: 'text-blue-500',
};

const SEVERITY_BG: Record<string, string> = {
  success: 'bg-emerald-500/10',
  warning: 'bg-amber-500/10',
  error: 'bg-red-500/10',
  info: 'bg-blue-500/10',
};

const SEVERITY_BORDER: Record<string, string> = {
  success: 'border-l-emerald-500',
  warning: 'border-l-amber-500',
  error: 'border-l-red-500',
  info: 'border-l-blue-500',
};

const CATEGORY_BADGE_VARIANT: Record<string, string> = {
  build: 'bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400',
  approval: 'bg-sky-100 text-sky-700 dark:bg-sky-900/30 dark:text-sky-400',
  compliance: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  system: 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400',
};

// ---------------------------------------------------------------------------
// Filter tab definitions
// ---------------------------------------------------------------------------

interface FilterTab {
  value: string;
  label: string;
  icon?: LucideIcon;
  params: Partial<NotificationListParams>;
}

const FILTER_TABS: FilterTab[] = [
  { value: 'all', label: 'All', params: {} },
  { value: 'unread', label: 'Unread', params: { is_read: false } },
  {
    value: 'build',
    label: 'Build',
    icon: Hammer,
    params: { category: 'build' },
  },
  {
    value: 'approval',
    label: 'Approval',
    icon: CheckSquare,
    params: { category: 'approval' },
  },
  {
    value: 'compliance',
    label: 'Compliance',
    icon: Shield,
    params: { category: 'compliance' },
  },
  {
    value: 'system',
    label: 'System',
    icon: Bell,
    params: { category: 'system' },
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZE = 10;

function getCategoryIcon(category: string): LucideIcon {
  return CATEGORY_ICONS[category] || Bell;
}

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  const now = Date.now();
  const diffMs = now - date.getTime();

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  // Show full date for older notifications
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined,
    hour: '2-digit',
    minute: '2-digit',
  });
}

function capitalizeFirst(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

// ---------------------------------------------------------------------------
// Empty state component
// ---------------------------------------------------------------------------

function EmptyState({ activeFilter }: { activeFilter: string }) {
  const messages: Record<string, string> = {
    all: 'You have no notifications yet. Notifications will appear here when builds complete, approvals are needed, or system events occur.',
    unread: 'All caught up! You have no unread notifications.',
    build: 'No build notifications. You will be notified when server builds start, complete, or fail.',
    approval: 'No approval notifications. Approval requests and decisions will appear here.',
    compliance: 'No compliance notifications. Drift detection and compliance alerts will show here.',
    system: 'No system notifications. Platform announcements and maintenance alerts will appear here.',
  };

  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-16">
        <div className="rounded-full bg-muted p-4">
          <Inbox className="h-10 w-10 text-muted-foreground/50" />
        </div>
        <p className="mt-4 text-sm font-medium text-muted-foreground">
          {activeFilter === 'unread' ? 'All caught up!' : 'No notifications'}
        </p>
        <p className="mt-1 max-w-sm text-center text-xs text-muted-foreground/70">
          {messages[activeFilter] || messages.all}
        </p>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Single notification card
// ---------------------------------------------------------------------------

function NotificationCard({
  notification,
  onMarkRead,
  onDelete,
}: {
  notification: NotificationItem;
  onMarkRead: (id: string) => void;
  onDelete: (id: string) => void;
}) {
  const router = useRouter();
  const Icon = getCategoryIcon(notification.category);
  const colorClass = SEVERITY_COLORS[notification.severity] || SEVERITY_COLORS.info;
  const bgClass = SEVERITY_BG[notification.severity] || SEVERITY_BG.info;
  const borderClass = SEVERITY_BORDER[notification.severity] || SEVERITY_BORDER.info;
  const badgeClass = CATEGORY_BADGE_VARIANT[notification.category] || CATEGORY_BADGE_VARIANT.system;

  function handleClick() {
    if (!notification.is_read) {
      onMarkRead(notification.id);
    }
    if (notification.action_url) {
      router.push(notification.action_url);
    }
  }

  return (
    <Card
      className={cn(
        'overflow-hidden border-l-4 transition-all',
        notification.is_read
          ? 'border-l-transparent'
          : cn('border-l-blue-500', 'bg-blue-50/50 dark:bg-blue-950/10'),
        notification.action_url && 'cursor-pointer hover:shadow-md',
      )}
      onClick={notification.action_url ? handleClick : undefined}
    >
      <CardContent className="flex items-start gap-4 p-4">
        {/* Category icon */}
        <div
          className={cn(
            'mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full',
            bgClass,
          )}
        >
          <Icon className={cn('h-5 w-5', colorClass)} />
        </div>

        {/* Content */}
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p
                  className={cn(
                    'text-sm leading-tight',
                    !notification.is_read ? 'font-semibold' : 'font-medium',
                  )}
                >
                  {notification.title}
                </p>
                {!notification.is_read && (
                  <span className="h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                )}
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {notification.message}
              </p>
              <div className="mt-2 flex items-center gap-2">
                <Badge
                  variant="secondary"
                  className={cn('text-[10px] px-1.5 py-0 font-medium', badgeClass)}
                >
                  {capitalizeFirst(notification.category)}
                </Badge>
                <span className={cn('text-[10px] font-medium', colorClass)}>
                  {capitalizeFirst(notification.severity)}
                </span>
                <span className="text-[10px] text-muted-foreground/60">
                  {formatTimestamp(notification.created_at)}
                </span>
              </div>
            </div>

            {/* Actions */}
            <div className="flex shrink-0 items-center gap-1">
              {!notification.is_read && (
                <TooltipProvider delayDuration={300}>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        onClick={(e) => {
                          e.stopPropagation();
                          onMarkRead(notification.id);
                        }}
                      >
                        <CheckCheck className="h-4 w-4" />
                        <span className="sr-only">Mark as read</span>
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Mark as read</TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
              <TooltipProvider delayDuration={300}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-muted-foreground hover:text-destructive"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDelete(notification.id);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                      <span className="sr-only">Delete notification</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Delete</TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Loading skeleton
// ---------------------------------------------------------------------------

function NotificationSkeleton() {
  return (
    <Card className="overflow-hidden border-l-4 border-l-transparent">
      <CardContent className="flex items-start gap-4 p-4">
        <Skeleton className="h-10 w-10 shrink-0 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-3 w-full" />
          <div className="flex gap-2">
            <Skeleton className="h-4 w-14" />
            <Skeleton className="h-4 w-10" />
            <Skeleton className="h-4 w-16" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// NotificationList (main export)
// ---------------------------------------------------------------------------

export function NotificationList() {
  const [activeFilter, setActiveFilter] = useState('all');
  const [page, setPage] = useState(1);

  // Build query params from active filter
  const currentTab = FILTER_TABS.find((t) => t.value === activeFilter) ?? FILTER_TABS[0];
  const queryParams: NotificationListParams = {
    page,
    page_size: PAGE_SIZE,
    ...currentTab.params,
  };

  const { data, isLoading, isError, refetch } = useNotifications(queryParams);
  const markAsRead = useMarkAsRead();
  const deleteNotification = useDeleteNotification();

  const notifications = data?.notifications ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  function handleTabChange(value: string) {
    setActiveFilter(value);
    setPage(1);
  }

  function handleMarkRead(id: string) {
    markAsRead.mutate([id]);
  }

  function handleDelete(id: string) {
    deleteNotification.mutate(id);
  }

  return (
    <div className="space-y-4">
      {/* Filter tabs */}
      <Tabs value={activeFilter} onValueChange={handleTabChange}>
        <TabsList className="flex-wrap">
          {FILTER_TABS.map((tab) => {
            const TabIcon = tab.icon;
            return (
              <TabsTrigger
                key={tab.value}
                value={tab.value}
                className="gap-1.5"
              >
                {TabIcon && <TabIcon className="h-3.5 w-3.5" />}
                {tab.label}
              </TabsTrigger>
            );
          })}
        </TabsList>
      </Tabs>

      {/* Loading state */}
      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <NotificationSkeleton key={i} />
          ))}
        </div>
      )}

      {/* Error state */}
      {isError && !isLoading && (
        <Card>
          <CardContent className="flex flex-col items-center gap-4 py-12">
            <Bell className="h-12 w-12 text-muted-foreground" />
            <div className="text-center">
              <p className="font-medium">Unable to load notifications</p>
              <p className="mt-1 text-sm text-muted-foreground">
                The notifications service may be unavailable. Please try again.
              </p>
            </div>
            <Button variant="outline" onClick={() => refetch()}>
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Notification list */}
      {!isLoading && !isError && notifications.length === 0 && (
        <EmptyState activeFilter={activeFilter} />
      )}

      {!isLoading && !isError && notifications.length > 0 && (
        <>
          <div className="space-y-3">
            {notifications.map((notification) => (
              <NotificationCard
                key={notification.id}
                notification={notification}
                onMarkRead={handleMarkRead}
                onDelete={handleDelete}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t pt-4">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * PAGE_SIZE + 1}
                {' '}-{' '}
                {Math.min(page * PAGE_SIZE, total)} of {total} notifications
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="gap-1"
                >
                  <ChevronLeft className="h-4 w-4" />
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="gap-1"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
