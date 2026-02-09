/**
 * Types, endpoint functions, and React Query hooks for the multi-region
 * infrastructure selectors (Region / VPC / Subnet).
 *
 * Backend routes:
 *   GET /api/v1/regions
 *   GET /api/v1/regions/{region}/vpcs
 *   GET /api/v1/regions/{region}/vpcs/{vpc_id}/subnets
 */

import { useQuery } from '@tanstack/react-query';
import apiClient from './client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Region {
  id: string;
  name: string;
  short_name: string;
  enabled: boolean;
}

export interface VPC {
  vpc_id: string;
  name: string;
  cidr_block: string;
  is_default: boolean;
  state: string;
}

export interface Subnet {
  subnet_id: string;
  name: string;
  cidr_block: string;
  availability_zone: string;
  available_ips: number;
  is_public: boolean;
  state: string;
}

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** Fetch all supported AWS regions. */
export async function listRegions(): Promise<Region[]> {
  const response = await apiClient.get<Region[]>('/regions');
  return response.data;
}

/** Fetch VPCs available in a given region. */
export async function listVPCs(region: string): Promise<VPC[]> {
  const response = await apiClient.get<VPC[]>(`/regions/${region}/vpcs`);
  return response.data;
}

/** Fetch subnets for a specific VPC in a region. */
export async function listSubnets(
  region: string,
  vpcId: string,
): Promise<Subnet[]> {
  const response = await apiClient.get<Subnet[]>(
    `/regions/${region}/vpcs/${vpcId}/subnets`,
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const regionKeys = {
  all: ['regions'] as const,
  vpcs: (region: string) => ['regions', region, 'vpcs'] as const,
  subnets: (region: string, vpcId: string) =>
    ['regions', region, 'vpcs', vpcId, 'subnets'] as const,
} as const;

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch all supported AWS regions.
 * Always enabled — regions are loaded once on mount.
 */
export function useRegions() {
  return useQuery<Region[]>({
    queryKey: regionKeys.all,
    queryFn: listRegions,
    staleTime: 5 * 60 * 1000, // regions rarely change
  });
}

/**
 * Fetch VPCs for the selected region.
 * Only fires when `region` is a non-empty string.
 */
export function useVPCs(region: string | undefined) {
  return useQuery<VPC[]>({
    queryKey: regionKeys.vpcs(region!),
    queryFn: () => listVPCs(region!),
    enabled: !!region,
    staleTime: 2 * 60 * 1000,
  });
}

/**
 * Fetch subnets for the selected VPC within a region.
 * Only fires when both `region` and `vpcId` are non-empty strings.
 */
export function useSubnets(
  region: string | undefined,
  vpcId: string | undefined,
) {
  return useQuery<Subnet[]>({
    queryKey: regionKeys.subnets(region!, vpcId!),
    queryFn: () => listSubnets(region!, vpcId!),
    enabled: !!region && !!vpcId,
    staleTime: 2 * 60 * 1000,
  });
}
