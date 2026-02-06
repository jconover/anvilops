'use client';

import { Bell, CheckCheck } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useUnreadCount, useMarkAllAsRead } from '@/lib/api/notifications';
import { NotificationList } from '@/components/notifications/notification-list';

export default function NotificationsPage() {
  const { data: unreadCount = 0 } = useUnreadCount();
  const markAllAsRead = useMarkAllAsRead();

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2">
            <Bell className="h-6 w-6 text-primary" />
          </div>
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">
                Notifications
              </h1>
              <p className="text-sm text-muted-foreground">
                Stay informed about builds, approvals, compliance, and system events
              </p>
            </div>
            {unreadCount > 0 && (
              <Badge variant="destructive" className="text-sm px-2.5 py-0.5">
                {unreadCount} unread
              </Badge>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <Button
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => markAllAsRead.mutate()}
              disabled={markAllAsRead.isPending}
            >
              <CheckCheck className="h-3.5 w-3.5" />
              Mark all as read
            </Button>
          )}
        </div>
      </div>

      {/* Notification list with filters and pagination */}
      <NotificationList />
    </div>
  );
}
