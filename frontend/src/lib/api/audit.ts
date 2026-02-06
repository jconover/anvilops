/**
 * Audit log API types, endpoint functions, and React Query hooks.
 *
 * Backend routes:
 *   GET /api/v1/audit          — List audit logs (paginated, filterable)
 *   GET /api/v1/audit/{id}     — Single audit log entry
 *   GET /api/v1/audit/actions  — Distinct action types
 *   GET /api/v1/audit/summary  — Aggregate stats (events/day, top actions, top actors)
 */

import { useQuery } from '@tanstack/react-query';
import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A single audit log entry. */
export interface AuditLog {
  id: string;
  timestamp: string;
  action: string;
  category: string;
  actor_email: string | null;
  actor_role: string | null;
  resource_type: string | null;
  resource_id: string | null;
  resource_name: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  status: string;
  error_message: string | null;
  created_at: string;
}

/** Paginated audit log list response. */
export interface AuditLogListResponse {
  logs: AuditLog[];
  total: number;
  page: number;
  page_size: number;
}

/** Aggregate audit stats returned by the summary endpoint. */
export interface AuditSummary {
  events_per_day: { date: string; count: number }[];
  top_actions: { action: string; count: number }[];
  top_actors: { email: string; count: number }[];
  total_events: number;
}

/** Query parameters accepted by the list endpoint. */
export interface AuditQueryParams {
  page?: number;
  page_size?: number;
  action?: string;
  category?: string;
  actor_email?: string;
  resource_id?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
}

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** Fetch a paginated, filtered list of audit log entries. */
export async function listAuditLogs(
  params?: AuditQueryParams,
): Promise<AuditLogListResponse> {
  const response = await apiClient.get<AuditLogListResponse>('/audit', {
    params,
  });
  return response.data;
}

/** Fetch a single audit log entry by ID. */
export async function getAuditLog(id: string): Promise<AuditLog> {
  const response = await apiClient.get<AuditLog>(`/audit/${id}`);
  return response.data;
}

/** Fetch the list of distinct action types recorded in the audit log. */
export async function getAuditActions(): Promise<string[]> {
  const response = await apiClient.get<string[]>('/audit/actions');
  return response.data;
}

/** Fetch aggregate audit summary (events/day, top actions, top actors). */
export async function getAuditSummary(): Promise<AuditSummary> {
  const response = await apiClient.get<AuditSummary>('/audit/summary');
  return response.data;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const auditQueryKeys = {
  all: ['audit'] as const,
  list: (params?: AuditQueryParams) => ['audit', 'list', params] as const,
  detail: (id: string) => ['audit', id] as const,
  actions: ['audit', 'actions'] as const,
  summary: ['audit', 'summary'] as const,
} as const;

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch a paginated, filtered audit log list.
 *
 * Accepts an optional `refetchInterval` so callers can enable auto-refresh.
 */
export function useAuditLogs(
  params?: AuditQueryParams,
  options?: { refetchInterval?: number | false },
) {
  return useQuery<AuditLogListResponse>({
    queryKey: auditQueryKeys.list(params),
    queryFn: () => listAuditLogs(params),
    refetchInterval: options?.refetchInterval,
  });
}

/** Fetch a single audit log entry. Disabled when `id` is undefined. */
export function useAuditLog(id: string | undefined) {
  return useQuery<AuditLog>({
    queryKey: auditQueryKeys.detail(id!),
    queryFn: () => getAuditLog(id!),
    enabled: !!id,
  });
}

/** Fetch the distinct action types. Cached aggressively since these change rarely. */
export function useAuditActions() {
  return useQuery<string[]>({
    queryKey: auditQueryKeys.actions,
    queryFn: getAuditActions,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/** Fetch the aggregate audit summary. */
export function useAuditSummary() {
  return useQuery<AuditSummary>({
    queryKey: auditQueryKeys.summary,
    queryFn: getAuditSummary,
  });
}
