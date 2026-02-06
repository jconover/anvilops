'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Bell,
  CheckSquare,
  Hammer,
  Shield,
  CheckCheck,
  ExternalLink,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

import { cn } from '@/lib/utils';
import {
  useUnreadCount,
  useNotifications,
  useMarkAsRead,
  useMarkAllAsRead,
  type NotificationItem,
} from '@/lib/api/notifications';

import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getCategoryIcon(category: string): LucideIcon {
  return CATEGORY_ICONS[category] || Bell;
}

function formatRelativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;

  const seconds = Math.floor(diffMs / 1000);
  if (seconds < 60) return 'just now';

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return new Date(dateStr).toLocaleDateString();
}

// ---------------------------------------------------------------------------
// NotificationBell
// ---------------------------------------------------------------------------

export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);

  // Data hooks
  const { data: unreadCount = 0 } = useUnreadCount();
  const { data: notificationsData } = useNotifications({
    page: 1,
    page_size: 5,
  });

  // Mutations
  const markAsRead = useMarkAsRead();
  const markAllAsRead = useMarkAllAsRead();

  // Bounce animation when unread count increases
  const prevCountRef = useRef(unreadCount);
  const [bouncing, setBouncing] = useState(false);

  useEffect(() => {
    if (unreadCount > prevCountRef.current && unreadCount > 0) {
      setBouncing(true);
      const timer = setTimeout(() => setBouncing(false), 600);
      return () => clearTimeout(timer);
    }
    prevCountRef.current = unreadCount;
  }, [unreadCount]);

  const notifications = notificationsData?.notifications ?? [];

  function handleNotificationClick(notification: NotificationItem) {
    // Mark as read if unread
    if (!notification.is_read) {
      markAsRead.mutate([notification.id]);
    }

    setOpen(false);

    // Navigate to action URL or notifications page
    if (notification.action_url) {
      router.push(notification.action_url);
    } else {
      router.push('/dashboard/notifications');
    }
  }

  function handleMarkAllRead() {
    markAllAsRead.mutate();
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            'relative',
            bouncing && 'animate-bounce',
          )}
          style={bouncing ? { animationDuration: '0.6s', animationIterationCount: '2' } : undefined}
        >
          <Bell className="h-5 w-5" />
          {unreadCount > 0 && (
            <span className="absolute -right-0.5 -top-0.5 flex h-5 min-w-[20px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
              {unreadCount > 99 ? '99+' : unreadCount}
            </span>
          )}
          <span className="sr-only">
            Notifications{unreadCount > 0 ? ` (${unreadCount} unread)` : ''}
          </span>
        </Button>
      </PopoverTrigger>

      <PopoverContent
        align="end"
        className="w-96 p-0"
        sideOffset={8}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-sm font-semibold">Notifications</h3>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
              disabled={markAllAsRead.isPending}
            >
              <CheckCheck className="h-3.5 w-3.5" />
              Mark all as read
            </button>
          )}
        </div>

        {/* Notification list */}
        {notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-10 px-4">
            <Bell className="h-10 w-10 text-muted-foreground/40" />
            <p className="mt-2 text-sm text-muted-foreground">
              No notifications yet
            </p>
            <p className="text-xs text-muted-foreground/60">
              We will let you know when something happens
            </p>
          </div>
        ) : (
          <ScrollArea className="max-h-[380px]">
            <div className="divide-y">
              {notifications.map((notification) => {
                const Icon = getCategoryIcon(notification.category);
                const colorClass =
                  SEVERITY_COLORS[notification.severity] || SEVERITY_COLORS.info;
                const bgClass =
                  SEVERITY_BG[notification.severity] || SEVERITY_BG.info;

                return (
                  <button
                    key={notification.id}
                    onClick={() => handleNotificationClick(notification)}
                    className={cn(
                      'flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-accent/50',
                      !notification.is_read && 'bg-accent/20',
                    )}
                  >
                    {/* Category icon */}
                    <div
                      className={cn(
                        'mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                        bgClass,
                      )}
                    >
                      <Icon className={cn('h-4 w-4', colorClass)} />
                    </div>

                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p
                          className={cn(
                            'text-sm leading-tight',
                            !notification.is_read
                              ? 'font-semibold'
                              : 'font-medium text-muted-foreground',
                          )}
                        >
                          {notification.title}
                        </p>
                        {!notification.is_read && (
                          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-blue-500" />
                        )}
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                        {notification.message}
                      </p>
                      <p className="mt-1 text-[11px] text-muted-foreground/60">
                        {formatRelativeTime(notification.created_at)}
                      </p>
                    </div>
                  </button>
                );
              })}
            </div>
          </ScrollArea>
        )}

        {/* Footer */}
        <Separator />
        <div className="p-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-center gap-2 text-xs"
            onClick={() => {
              setOpen(false);
              router.push('/dashboard/notifications');
            }}
          >
            <ExternalLink className="h-3.5 w-3.5" />
            View all notifications
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
