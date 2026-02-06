/**
 * API functions for the server decommission workflow.
 *
 * The decommission endpoint triggers the full reverse pipeline:
 *   Puppet Purge -> AWX Decommission -> Terraform Destroy -> DNS Cleanup
 */

import apiClient from './client';
import type { ServerResponse } from './types';

/** Trigger the decommission workflow for a server. */
export async function decommissionServer(serverId: string): Promise<ServerResponse> {
  const response = await apiClient.post<ServerResponse>(
    `/servers/${serverId}/decommission`,
  );
  return response.data;
}
