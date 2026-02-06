/**
 * Cost estimation API types and endpoint functions.
 *
 * Integrates with the backend cost estimation endpoints:
 *   POST /api/v1/costs/estimate  — compute cost estimate for a server config
 *   GET  /api/v1/costs/pricing   — retrieve the full pricing table
 */

import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Request body for the cost estimation endpoint. */
export interface CostEstimateRequest {
  instance_size: string;
  os_type: string;
  region: string;
  additional_storage: { size_gb: number; volume_type: string }[];
}

/** A single line item in the cost breakdown. */
export interface CostLineItem {
  category: string;
  description: string;
  monthly_cost: number;
}

/** Response from the cost estimation endpoint. */
export interface CostEstimateResponse {
  instance_cost: number;
  storage_cost: number;
  os_license_cost: number;
  total_monthly: number;
  total_annual: number;
  currency: string;
  instance_type: string;
  breakdown: CostLineItem[];
}

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/**
 * Estimate the monthly and annual cost for a server configuration.
 *
 * Sends instance size, OS type, region, and any additional storage volumes
 * to the backend, which queries the AWS Pricing API and returns a detailed
 * cost breakdown.
 */
export async function estimateCost(
  config: CostEstimateRequest,
): Promise<CostEstimateResponse> {
  const response = await apiClient.post<CostEstimateResponse>(
    '/costs/estimate',
    config,
  );
  return response.data;
}

/**
 * Retrieve the full pricing table from the backend.
 *
 * Returns a mapping of instance sizes, regions, and OS types to their
 * respective pricing data. Useful for client-side price previews or
 * building comparison tables.
 */
export async function getPricingTable(): Promise<Record<string, unknown>> {
  const response = await apiClient.get<Record<string, unknown>>(
    '/costs/pricing',
  );
  return response.data;
}
