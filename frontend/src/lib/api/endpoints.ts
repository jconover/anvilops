/**
 * Typed endpoint functions for every AnvilOps API route.
 *
 * Each function calls the FastAPI backend through the shared Axios client
 * and returns a strongly-typed promise.
 *
 * Backend route reference:
 *   /api/v1/servers/**        — backend/app/api/v1/servers.py
 *   /api/v1/puppet/**         — backend/app/api/v1/puppet.py
 *   /api/v1/compliance/**     — backend/app/api/v1/compliance.py
 */

import apiClient from './client';
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
} from './types';

// ---------------------------------------------------------------------------
// Servers
// ---------------------------------------------------------------------------

/** Create a new server build request. */
export async function createServer(data: ServerCreateRequest): Promise<ServerResponse> {
  const response = await apiClient.post<ServerResponse>('/servers', data);
  return response.data;
}

/** List servers with optional filtering and pagination. */
export async function listServers(params?: ServerListParams): Promise<ServerListResponse> {
  const response = await apiClient.get<ServerListResponse>('/servers', { params });
  return response.data;
}

/** Get a single server by ID. */
export async function getServer(id: string): Promise<ServerResponse> {
  const response = await apiClient.get<ServerResponse>(`/servers/${id}`);
  return response.data;
}

/** Request server decommission. */
export async function deleteServer(id: string): Promise<ServerResponse> {
  const response = await apiClient.delete<ServerResponse>(`/servers/${id}`);
  return response.data;
}

/** Approve a pending server request. */
export async function approveServer(id: string): Promise<ServerResponse> {
  const response = await apiClient.post<ServerResponse>(`/servers/${id}/approve`);
  return response.data;
}

// ---------------------------------------------------------------------------
// Build steps
// ---------------------------------------------------------------------------

/** Get the build pipeline steps for a server. */
export async function getServerBuildSteps(id: string): Promise<BuildStep[]> {
  const response = await apiClient.get<BuildStep[]>(`/servers/${id}/steps`);
  return response.data;
}

// ---------------------------------------------------------------------------
// Puppet
// ---------------------------------------------------------------------------

/** Get the PuppetDB node status for a server. */
export async function getPuppetStatus(serverId: string): Promise<PuppetNodeStatus> {
  const response = await apiClient.get<PuppetNodeStatus>(
    `/puppet/nodes/${serverId}/status`,
  );
  return response.data;
}

/** Get the latest Puppet report for a server. */
export async function getPuppetReport(serverId: string): Promise<PuppetReport> {
  const response = await apiClient.get<PuppetReport>(
    `/puppet/nodes/${serverId}/report`,
  );
  return response.data;
}

/** Get Puppet facts for a server. */
export async function getPuppetFacts(serverId: string): Promise<PuppetFacts> {
  const response = await apiClient.get<PuppetFacts>(
    `/puppet/nodes/${serverId}/facts`,
  );
  return response.data;
}

/** Get aggregate Puppet compliance summary. */
export async function getPuppetComplianceSummary(): Promise<PuppetComplianceSummary> {
  const response = await apiClient.get<PuppetComplianceSummary>('/puppet/compliance');
  return response.data;
}

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------

/** Get fleet-wide compliance summary. */
export async function getComplianceSummary(): Promise<ComplianceSummary> {
  const response = await apiClient.get<ComplianceSummary>('/compliance/summary');
  return response.data;
}

/** Get compliance detail for a single node. */
export async function getNodeCompliance(serverId: string): Promise<ComplianceNode> {
  const response = await apiClient.get<ComplianceNode>(
    `/compliance/nodes/${serverId}`,
  );
  return response.data;
}

/** Get drift report for a single node. */
export async function getNodeDrift(
  serverId: string,
  hours?: number,
): Promise<NodeDriftReport> {
  const response = await apiClient.get<NodeDriftReport>(
    `/compliance/nodes/${serverId}/drift`,
    { params: hours !== undefined ? { hours } : undefined },
  );
  return response.data;
}

/** Get full compliance report for audit purposes. */
export async function getComplianceReport(): Promise<ComplianceReport> {
  const response = await apiClient.get<ComplianceReport>('/compliance/report');
  return response.data;
}
