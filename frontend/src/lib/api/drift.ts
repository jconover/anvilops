/**
 * Drift Detection API types, endpoint functions, and React Query hooks.
 *
 * Backend route reference:
 *   GET  /api/v1/drift/summary                    — fleet-wide drift summary
 *   GET  /api/v1/drift/events                     — paginated drift events
 *   GET  /api/v1/drift/servers/:serverId/timeline  — server drift timeline
 *   GET  /api/v1/drift/alerts                     — active drift alerts
 *   POST /api/v1/drift/alerts/:id/acknowledge     — acknowledge an alert
 *   GET  /api/v1/drift/trends                     — trend data (30 days)
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

/** Fleet-wide drift detection summary. */
export interface DriftSummary {
  total_events: number;
  by_severity: {
    critical: number;
    high: number;
    medium: number;
    low: number;
  };
  by_category: {
    security: number;
    configuration: number;
    package: number;
    service: number;
    file: number;
  };
  active_alerts: number;
  trend_direction: 'up' | 'down' | 'stable';
}

/** A single drift event from the enhanced drift detection system. */
export interface EnhancedDriftEvent {
  id: string;
  server_request_id: string;
  certname: string;
  detected_at: string;
  resolved_at: string | null;
  resource_type: string;
  resource_title: string;
  property_name: string;
  old_value: string | null;
  new_value: string | null;
  severity: string;
  is_corrective: boolean;
  is_resolved: boolean;
  resolution_type: string | null;
  drift_category: string;
  cis_control_id: string | null;
}

/** Paginated drift events response. */
export interface DriftEventsResponse {
  events: EnhancedDriftEvent[];
  total: number;
}

/** Query parameters for the drift events endpoint. */
export interface DriftEventsParams {
  page?: number;
  page_size?: number;
  severity?: string;
  category?: string;
  is_resolved?: boolean;
  server_id?: string;
  date_from?: string;
  date_to?: string;
}

/** An active drift alert. */
export interface DriftAlert {
  id: string;
  alert_type: string;
  severity: string;
  title: string;
  message: string;
  is_acknowledged: boolean;
  acknowledged_by: string | null;
  server_request_id: string | null;
  created_at: string;
}

/** A single day's trend data point. */
export interface TrendDataPoint {
  date: string;
  count: number;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

/** Top drifting resource. */
export interface TopResource {
  resource: string;
  count: number;
}

/** Top drifting server. */
export interface TopServer {
  server_name: string;
  count: number;
}

/** Drift trend data over 30 days. */
export interface DriftTrends {
  events_per_day: TrendDataPoint[];
  top_resources: TopResource[];
  top_servers: TopServer[];
}

/** Timeline event for a specific server. */
export interface DriftTimelineEvent {
  id: string;
  detected_at: string;
  resolved_at: string | null;
  resource_type: string;
  resource_title: string;
  property_name: string;
  old_value: string | null;
  new_value: string | null;
  severity: string;
  is_corrective: boolean;
  is_resolved: boolean;
  drift_category: string;
  cis_control_id: string | null;
}

/** Server drift timeline response. */
export interface DriftTimelineResponse {
  server_id: string;
  certname: string;
  events: DriftTimelineEvent[];
  total: number;
  hours: number;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const driftKeys = {
  all: ['drift'] as const,
  summary: ['drift', 'summary'] as const,
  events: (params?: DriftEventsParams) => ['drift', 'events', params] as const,
  timeline: (serverId: string, hours?: number) =>
    ['drift', 'timeline', serverId, hours] as const,
  alerts: ['drift', 'alerts'] as const,
  trends: ['drift', 'trends'] as const,
} as const;

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** Fetch the fleet-wide drift detection summary. */
export async function getDriftSummary(): Promise<DriftSummary> {
  const response = await apiClient.get<DriftSummary>('/drift/summary');
  return response.data;
}

/** Fetch paginated drift events with optional filters. */
export async function getDriftEvents(
  params?: DriftEventsParams,
): Promise<DriftEventsResponse> {
  const response = await apiClient.get<DriftEventsResponse>('/drift/events', {
    params,
  });
  return response.data;
}

/** Fetch the drift timeline for a specific server. */
export async function getDriftTimeline(
  serverId: string,
  hours?: number,
): Promise<DriftTimelineResponse> {
  const response = await apiClient.get<DriftTimelineResponse>(
    `/drift/servers/${serverId}/timeline`,
    { params: hours !== undefined ? { hours } : undefined },
  );
  return response.data;
}

/** Fetch active drift alerts. */
export async function getDriftAlerts(): Promise<DriftAlert[]> {
  const response = await apiClient.get<DriftAlert[]>('/drift/alerts');
  return response.data;
}

/** Acknowledge a drift alert by ID. */
export async function acknowledgeDriftAlert(id: string): Promise<void> {
  await apiClient.post(`/drift/alerts/${id}/acknowledge`);
}

/** Fetch drift trend data (last 30 days). */
export async function getDriftTrends(): Promise<DriftTrends> {
  const response = await apiClient.get<DriftTrends>('/drift/trends');
  return response.data;
}

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch the fleet-wide drift detection summary.
 * Polls every 60 seconds for near-real-time updates.
 */
export function useDriftSummary() {
  return useQuery<DriftSummary>({
    queryKey: driftKeys.summary,
    queryFn: getDriftSummary,
    refetchInterval: 60_000,
  });
}

/**
 * Fetch paginated drift events with optional filters.
 * Polls every 60 seconds.
 */
export function useDriftEvents(params?: DriftEventsParams) {
  return useQuery<DriftEventsResponse>({
    queryKey: driftKeys.events(params),
    queryFn: () => getDriftEvents(params),
    refetchInterval: 60_000,
  });
}

/**
 * Fetch the drift timeline for a specific server.
 * Only fires when serverId is provided.
 */
export function useDriftTimeline(
  serverId: string | undefined,
  hours?: number,
) {
  return useQuery<DriftTimelineResponse>({
    queryKey: driftKeys.timeline(serverId!, hours),
    queryFn: () => getDriftTimeline(serverId!, hours),
    enabled: !!serverId,
  });
}

/**
 * Fetch active drift alerts.
 * Polls every 30 seconds for rapid alert awareness.
 */
export function useDriftAlerts() {
  return useQuery<DriftAlert[]>({
    queryKey: driftKeys.alerts,
    queryFn: getDriftAlerts,
    refetchInterval: 30_000,
  });
}

/**
 * Mutation: acknowledge a drift alert.
 * Optimistically removes the alert from the active list and
 * decrements the summary's active_alerts count.
 */
export function useAcknowledgeAlert() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: acknowledgeDriftAlert,
    onMutate: async (alertId) => {
      await queryClient.cancelQueries({ queryKey: driftKeys.alerts });
      await queryClient.cancelQueries({ queryKey: driftKeys.summary });

      const previousAlerts = queryClient.getQueryData<DriftAlert[]>(
        driftKeys.alerts,
      );

      // Optimistically filter out the acknowledged alert
      if (previousAlerts) {
        queryClient.setQueryData<DriftAlert[]>(
          driftKeys.alerts,
          previousAlerts.filter((a) => a.id !== alertId),
        );
      }

      // Optimistically decrement active_alerts in summary
      const previousSummary = queryClient.getQueryData<DriftSummary>(
        driftKeys.summary,
      );
      if (previousSummary) {
        queryClient.setQueryData<DriftSummary>(driftKeys.summary, {
          ...previousSummary,
          active_alerts: Math.max(0, previousSummary.active_alerts - 1),
        });
      }

      return { previousAlerts, previousSummary };
    },
    onError: (_err, _alertId, context: any) => {
      if (context?.previousAlerts) {
        queryClient.setQueryData(driftKeys.alerts, context.previousAlerts);
      }
      if (context?.previousSummary) {
        queryClient.setQueryData(driftKeys.summary, context.previousSummary);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: driftKeys.all });
    },
  });
}

/**
 * Fetch drift trend data (last 30 days).
 * Refreshes every 5 minutes since trend data changes slowly.
 */
export function useDriftTrends() {
  return useQuery<DriftTrends>({
    queryKey: driftKeys.trends,
    queryFn: getDriftTrends,
    refetchInterval: 300_000,
  });
}
