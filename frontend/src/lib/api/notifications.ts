/**
 * Notification API types, endpoint functions, and React Query hooks.
 *
 * Backend route reference:
 *   GET    /api/v1/notifications              — list notifications
 *   GET    /api/v1/notifications/unread-count  — quick unread count
 *   POST   /api/v1/notifications/mark-read     — mark specific as read
 *   POST   /api/v1/notifications/mark-all-read — mark all as read
 *   DELETE /api/v1/notifications/:id           — delete notification
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single notification item returned by the API. */
export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  category: string; // "build", "approval", "compliance", "system"
  severity: string; // "info", "success", "warning", "error"
  is_read: boolean;
  read_at: string | null;
  resource_type: string | null;
  resource_id: string | null;
  action_url: string | null;
  icon: string | null;
  created_at: string;
}

/** Paginated notification list response. */
export interface NotificationListResponse {
  notifications: NotificationItem[];
  total: number;
  unread_count: number;
}

/** Query parameters for the notification list endpoint. */
export interface NotificationListParams {
  page?: number;
  page_size?: number;
  category?: string;
  is_read?: boolean;
  severity?: string;
}

/** Response shape for the unread count endpoint. */
interface UnreadCountResponse {
  unread_count: number;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const notificationKeys = {
  all: ['notifications'] as const,
  list: (params?: NotificationListParams) =>
    ['notifications', 'list', params] as const,
  unreadCount: ['notifications', 'unread-count'] as const,
} as const;

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** List notifications with optional filtering and pagination. */
export async function listNotifications(
  params?: NotificationListParams,
): Promise<NotificationListResponse> {
  const response = await apiClient.get<NotificationListResponse>(
    '/notifications',
    { params },
  );
  return response.data;
}

/** Get the quick unread notification count. */
export async function getUnreadCount(): Promise<number> {
  const response = await apiClient.get<UnreadCountResponse>(
    '/notifications/unread-count',
  );
  return response.data.unread_count;
}

/** Mark specific notifications as read by their IDs. */
export async function markAsRead(notificationIds: string[]): Promise<void> {
  await apiClient.post('/notifications/mark-read', {
    notification_ids: notificationIds,
  });
}

/** Mark all notifications as read. */
export async function markAllAsRead(): Promise<void> {
  await apiClient.post('/notifications/mark-all-read');
}

/** Delete a single notification by ID. */
export async function deleteNotification(id: string): Promise<void> {
  await apiClient.delete(`/notifications/${id}`);
}

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch paginated notification list.
 * Polls every 30 seconds to keep the list fresh.
 */
export function useNotifications(params?: NotificationListParams) {
  return useQuery<NotificationListResponse>({
    queryKey: notificationKeys.list(params),
    queryFn: () => listNotifications(params),
    refetchInterval: 30_000,
  });
}

/**
 * Fetch the unread notification count.
 * Polls every 15 seconds for near-real-time badge updates.
 */
export function useUnreadCount() {
  return useQuery<number>({
    queryKey: notificationKeys.unreadCount,
    queryFn: getUnreadCount,
    refetchInterval: 15_000,
  });
}

/**
 * Mutation: mark specific notifications as read.
 * Optimistically decrements the unread count and updates list cache.
 */
export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string[]>({
    mutationFn: markAsRead,
    onMutate: async (notificationIds) => {
      // Cancel outgoing refetches so they don't overwrite our optimistic update
      await queryClient.cancelQueries({
        queryKey: notificationKeys.all,
      });

      // Snapshot previous unread count
      const previousCount = queryClient.getQueryData<number>(
        notificationKeys.unreadCount,
      );

      // Optimistically decrement unread count
      if (previousCount !== undefined) {
        queryClient.setQueryData<number>(
          notificationKeys.unreadCount,
          Math.max(0, previousCount - notificationIds.length),
        );
      }

      return { previousCount };
    },
    onError: (_err, _ids, context: any) => {
      // Rollback on error
      if (context?.previousCount !== undefined) {
        queryClient.setQueryData(
          notificationKeys.unreadCount,
          context.previousCount,
        );
      }
    },
    onSettled: () => {
      // Refetch to ensure server state is in sync
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}

/**
 * Mutation: mark all notifications as read.
 * Optimistically sets the unread count to 0.
 */
export function useMarkAllAsRead() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, void>({
    mutationFn: markAllAsRead,
    onMutate: async () => {
      await queryClient.cancelQueries({
        queryKey: notificationKeys.all,
      });

      const previousCount = queryClient.getQueryData<number>(
        notificationKeys.unreadCount,
      );

      // Optimistically set count to 0
      queryClient.setQueryData<number>(notificationKeys.unreadCount, 0);

      return { previousCount };
    },
    onError: (_err, _vars, context: any) => {
      if (context?.previousCount !== undefined) {
        queryClient.setQueryData(
          notificationKeys.unreadCount,
          context.previousCount,
        );
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}

/**
 * Mutation: delete a single notification.
 * Invalidates all notification queries on success.
 */
export function useDeleteNotification() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteNotification,
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationKeys.all });
    },
  });
}
