/**
 * ServiceNow CMDB API types, endpoint functions, and React Query hooks.
 *
 * Backend routes:
 *   GET  /api/v1/cmdb/status/{server_id}  — CMDB sync status for a server
 *   POST /api/v1/cmdb/sync/{server_id}    — Trigger manual sync for a server
 *   POST /api/v1/cmdb/sync                — Trigger full reconciliation
 *   GET  /api/v1/cmdb/stats               — Aggregate CMDB sync statistics
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** CMDB sync status for a single server. */
export interface CMDBStatus {
  synced: boolean;
  sys_id: string | null;
  ci_number: string | null;
  last_sync: string | null;
  operational_status: string | null;
  install_status: string | null;
  servicenow_url: string | null;
}

/** Aggregate CMDB sync statistics. */
export interface CMDBStats {
  total_synced: number;
  total_servers: number;
  last_full_sync: string | null;
  pending_syncs: number;
  sync_rate: number;
}

/** Response from a sync operation. */
export interface CMDBSyncResponse {
  success: boolean;
  message: string;
  synced_count?: number;
}

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** Fetch CMDB sync status for a specific server. */
export async function getCMDBStatus(serverId: string): Promise<CMDBStatus> {
  const response = await apiClient.get<CMDBStatus>(`/cmdb/status/${serverId}`);
  return response.data;
}

/** Trigger a manual CMDB sync for a specific server. */
export async function syncServer(serverId: string): Promise<CMDBSyncResponse> {
  const response = await apiClient.post<CMDBSyncResponse>(
    `/cmdb/sync/${serverId}`,
  );
  return response.data;
}

/** Trigger a full CMDB reconciliation across all servers. */
export async function fullSync(): Promise<CMDBSyncResponse> {
  const response = await apiClient.post<CMDBSyncResponse>('/cmdb/sync');
  return response.data;
}

/** Fetch aggregate CMDB sync statistics. */
export async function getCMDBStats(): Promise<CMDBStats> {
  const response = await apiClient.get<CMDBStats>('/cmdb/stats');
  return response.data;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const cmdbQueryKeys = {
  all: ['cmdb'] as const,
  status: (serverId: string) => ['cmdb', 'status', serverId] as const,
  stats: ['cmdb', 'stats'] as const,
} as const;

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/** Fetch CMDB sync status for a server. Disabled when `serverId` is undefined. */
export function useCMDBStatus(serverId: string | undefined) {
  return useQuery<CMDBStatus>({
    queryKey: cmdbQueryKeys.status(serverId!),
    queryFn: () => getCMDBStatus(serverId!),
    enabled: !!serverId,
  });
}

/** Trigger a manual CMDB sync for a single server. */
export function useSyncServer() {
  const queryClient = useQueryClient();

  return useMutation<CMDBSyncResponse, Error, string>({
    mutationFn: syncServer,
    onSuccess: (_data, serverId) => {
      // Invalidate the CMDB status for this server so the UI refreshes.
      queryClient.invalidateQueries({
        queryKey: cmdbQueryKeys.status(serverId),
      });
      // Also refresh aggregate stats.
      queryClient.invalidateQueries({
        queryKey: cmdbQueryKeys.stats,
      });
    },
  });
}

/** Trigger a full CMDB reconciliation. */
export function useFullSync() {
  const queryClient = useQueryClient();

  return useMutation<CMDBSyncResponse, Error, void>({
    mutationFn: fullSync,
    onSuccess: () => {
      // Invalidate all CMDB queries so the entire view refreshes.
      queryClient.invalidateQueries({
        queryKey: cmdbQueryKeys.all,
      });
    },
  });
}

/** Fetch aggregate CMDB sync statistics. */
export function useCMDBStats() {
  return useQuery<CMDBStats>({
    queryKey: cmdbQueryKeys.stats,
    queryFn: getCMDBStats,
  });
}
