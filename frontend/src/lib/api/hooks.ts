/**
 * React Query hooks wrapping every AnvilOps API endpoint.
 *
 * Conventions:
 *   - Query keys follow the pattern: ['resource', id?, 'sub-resource?']
 *   - Hooks that accept an optional `id` parameter use `enabled: !!id` so
 *     they don't fire when the id is undefined.
 *   - In-progress builds are polled at short intervals (5-10 s) so the UI
 *     stays up to date without manual refresh.
 */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query';

import {
  approveServer,
  createServer,
  deleteServer,
  getComplianceReport,
  getComplianceSummary,
  getNodeCompliance,
  getNodeDrift,
  getPuppetComplianceSummary,
  getPuppetFacts,
  getPuppetReport,
  getPuppetStatus,
  getServer,
  getServerBuildSteps,
  listServers,
} from './endpoints';

import type {
  BuildStep,
  ComplianceNode,
  ComplianceReport,
  ComplianceSummary,
  NodeDriftReport,
  PuppetComplianceSummary,
  PuppetFacts,
  PuppetNodeStatus,
  PuppetReport,
  ServerCreateRequest,
  ServerListParams,
  ServerListResponse,
  ServerResponse,
  ServerStatus,
} from './types';

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const queryKeys = {
  servers: {
    all: ['servers'] as const,
    list: (params?: ServerListParams) => ['servers', 'list', params] as const,
    detail: (id: string) => ['servers', id] as const,
    steps: (id: string) => ['servers', id, 'steps'] as const,
  },
  puppet: {
    status: (serverId: string) => ['puppet', 'status', serverId] as const,
    report: (serverId: string) => ['puppet', 'report', serverId] as const,
    facts: (serverId: string) => ['puppet', 'facts', serverId] as const,
    compliance: ['puppet', 'compliance'] as const,
  },
  compliance: {
    summary: ['compliance', 'summary'] as const,
    node: (serverId: string) => ['compliance', 'node', serverId] as const,
    drift: (serverId: string, hours?: number) =>
      ['compliance', 'drift', serverId, hours] as const,
    report: ['compliance', 'report'] as const,
  },
} as const;

// ---------------------------------------------------------------------------
// Helper: statuses that indicate an active build
// ---------------------------------------------------------------------------

const IN_PROGRESS_STATUSES: ServerStatus[] = [
  'pending',
  'approved',
  'provisioning',
  'configuring',
  'validating',
];

function isInProgress(status: ServerStatus): boolean {
  return IN_PROGRESS_STATUSES.includes(status);
}

// ---------------------------------------------------------------------------
// Server hooks
// ---------------------------------------------------------------------------

/**
 * Fetch the paginated / filtered server list.
 * Polls every 10 seconds when any server in the current result set is
 * still building.
 */
export function useServers(params?: ServerListParams) {
  return useQuery<ServerListResponse>({
    queryKey: queryKeys.servers.list(params),
    queryFn: () => listServers(params),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const anyActive = data.servers.some((s) => isInProgress(s.status));
      return anyActive ? 10_000 : false;
    },
  });
}

/**
 * Fetch a single server by ID.
 * Polls every 5 seconds while the server is in an active build state.
 */
export function useServer(id: string | undefined) {
  return useQuery<ServerResponse>({
    queryKey: queryKeys.servers.detail(id!),
    queryFn: () => getServer(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      return isInProgress(data.status) ? 5_000 : false;
    },
  });
}

/**
 * Fetch build pipeline steps for a server.
 * Polls every 5 seconds while any step is still pending or in-progress.
 */
export function useServerBuildSteps(id: string | undefined) {
  return useQuery<BuildStep[]>({
    queryKey: queryKeys.servers.steps(id!),
    queryFn: () => getServerBuildSteps(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const anyActive = data.some(
        (step) => step.status === 'pending' || step.status === 'in_progress',
      );
      return anyActive ? 5_000 : false;
    },
  });
}

// ---------------------------------------------------------------------------
// Server mutations
// ---------------------------------------------------------------------------

/** Create a new server request with optimistic list invalidation. */
export function useCreateServer() {
  const queryClient = useQueryClient();

  return useMutation<ServerResponse, Error, ServerCreateRequest>({
    mutationFn: createServer,
    onSuccess: (newServer) => {
      // Invalidate the server list so it picks up the new entry.
      queryClient.invalidateQueries({ queryKey: queryKeys.servers.all });

      // Seed the cache for the new server's detail query.
      queryClient.setQueryData(
        queryKeys.servers.detail(newServer.id),
        newServer,
      );
    },
  });
}

/** Delete (decommission) a server. */
export function useDeleteServer() {
  const queryClient = useQueryClient();

  return useMutation<ServerResponse, Error, string>({
    mutationFn: deleteServer,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.servers.all });
      queryClient.invalidateQueries({
        queryKey: queryKeys.servers.detail(id),
      });
    },
  });
}

/** Approve a pending server request. */
export function useApproveServer() {
  const queryClient = useQueryClient();

  return useMutation<ServerResponse, Error, string>({
    mutationFn: approveServer,
    onSuccess: (updatedServer, id) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.servers.all });
      queryClient.setQueryData(
        queryKeys.servers.detail(id),
        updatedServer,
      );
    },
  });
}

// ---------------------------------------------------------------------------
// Puppet hooks
// ---------------------------------------------------------------------------

/** Fetch PuppetDB node status for a server. */
export function usePuppetStatus(serverId: string | undefined) {
  return useQuery<PuppetNodeStatus>({
    queryKey: queryKeys.puppet.status(serverId!),
    queryFn: () => getPuppetStatus(serverId!),
    enabled: !!serverId,
  });
}

/** Fetch the latest Puppet report for a server. */
export function usePuppetReport(serverId: string | undefined) {
  return useQuery<PuppetReport>({
    queryKey: queryKeys.puppet.report(serverId!),
    queryFn: () => getPuppetReport(serverId!),
    enabled: !!serverId,
  });
}

/** Fetch Puppet facts for a server. */
export function usePuppetFacts(serverId: string | undefined) {
  return useQuery<PuppetFacts>({
    queryKey: queryKeys.puppet.facts(serverId!),
    queryFn: () => getPuppetFacts(serverId!),
    enabled: !!serverId,
  });
}

/** Fetch aggregate Puppet compliance summary. */
export function usePuppetComplianceSummary() {
  return useQuery<PuppetComplianceSummary>({
    queryKey: queryKeys.puppet.compliance,
    queryFn: getPuppetComplianceSummary,
  });
}

// ---------------------------------------------------------------------------
// Compliance hooks
// ---------------------------------------------------------------------------

/** Fetch fleet-wide compliance summary. */
export function useComplianceSummary() {
  return useQuery<ComplianceSummary>({
    queryKey: queryKeys.compliance.summary,
    queryFn: getComplianceSummary,
  });
}

/** Fetch compliance detail for a single node. */
export function useNodeCompliance(serverId: string | undefined) {
  return useQuery<ComplianceNode>({
    queryKey: queryKeys.compliance.node(serverId!),
    queryFn: () => getNodeCompliance(serverId!),
    enabled: !!serverId,
  });
}

/** Fetch drift report for a single node. */
export function useNodeDrift(serverId: string | undefined, hours?: number) {
  return useQuery<NodeDriftReport>({
    queryKey: queryKeys.compliance.drift(serverId!, hours),
    queryFn: () => getNodeDrift(serverId!, hours),
    enabled: !!serverId,
  });
}

/** Fetch full compliance report (audit export). */
export function useComplianceReport() {
  return useQuery<ComplianceReport>({
    queryKey: queryKeys.compliance.report,
    queryFn: getComplianceReport,
  });
}
