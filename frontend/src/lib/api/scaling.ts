/**
 * Scaling Groups API types, endpoint functions, and React Query hooks.
 *
 * Backend route reference:
 *   GET    /api/v1/scaling              — list scaling groups
 *   GET    /api/v1/scaling/:id          — get scaling group detail with members
 *   POST   /api/v1/scaling              — create scaling group
 *   PUT    /api/v1/scaling/:id          — update scaling group
 *   DELETE /api/v1/scaling/:id          — delete scaling group
 *   POST   /api/v1/scaling/:id/scale    — manual scale (desired_count)
 *   POST   /api/v1/scaling/:id/pause    — pause scaling group
 *   POST   /api/v1/scaling/:id/resume   — resume scaling group
 *   GET    /api/v1/scaling/:id/members  — list members
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

/** A member server within a scaling group. */
export interface ScalingGroupMember {
  id: string;
  server_request_id: string;
  member_index: number;
  status: string;
  server_name?: string;
  private_ip?: string;
  server_status?: string;
}

/** A scaling group returned by the API. */
export interface ScalingGroup {
  id: string;
  name: string;
  description: string | null;
  status: string;
  environment: string;
  os_type: string;
  instance_size: string;
  region: string;
  min_instances: number;
  max_instances: number;
  desired_count: number;
  current_count: number;
  scale_up_threshold: number;
  scale_down_threshold: number;
  cooldown_seconds: number;
  last_scaled_at: string | null;
  created_at: string;
  updated_at: string;
  members: ScalingGroupMember[];
}

/** POST body for creating a new scaling group. */
export interface ScalingGroupCreateRequest {
  name: string;
  description?: string;
  environment: string;
  os_type: string;
  instance_size: string;
  region: string;
  vpc_id: string;
  subnet_id: string;
  puppet_role: string;
  min_instances: number;
  max_instances: number;
  desired_count: number;
  scale_up_threshold: number;
  scale_down_threshold: number;
  cooldown_seconds: number;
}

/** PUT body for updating a scaling group. */
export interface ScalingGroupUpdateRequest {
  name?: string;
  description?: string;
  min_instances?: number;
  max_instances?: number;
  desired_count?: number;
  scale_up_threshold?: number;
  scale_down_threshold?: number;
  cooldown_seconds?: number;
}

/** POST body for manual scale action. */
export interface ScaleRequest {
  desired_count: number;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const scalingKeys = {
  all: ['scaling'] as const,
  list: () => ['scaling', 'list'] as const,
  detail: (id: string) => ['scaling', id] as const,
  members: (id: string) => ['scaling', id, 'members'] as const,
} as const;

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** List all scaling groups. */
export async function listScalingGroups(): Promise<ScalingGroup[]> {
  const response = await apiClient.get<ScalingGroup[]>('/scaling');
  return response.data;
}

/** Get a single scaling group by ID. */
export async function getScalingGroup(id: string): Promise<ScalingGroup> {
  const response = await apiClient.get<ScalingGroup>(`/scaling/${id}`);
  return response.data;
}

/** Create a new scaling group. */
export async function createScalingGroup(
  data: ScalingGroupCreateRequest,
): Promise<ScalingGroup> {
  const response = await apiClient.post<ScalingGroup>('/scaling', data);
  return response.data;
}

/** Update an existing scaling group. */
export async function updateScalingGroup(
  id: string,
  data: ScalingGroupUpdateRequest,
): Promise<ScalingGroup> {
  const response = await apiClient.put<ScalingGroup>(`/scaling/${id}`, data);
  return response.data;
}

/** Delete a scaling group. */
export async function deleteScalingGroup(id: string): Promise<void> {
  await apiClient.delete(`/scaling/${id}`);
}

/** Trigger a manual scale operation. */
export async function scaleGroup(
  id: string,
  desiredCount: number,
): Promise<ScalingGroup> {
  const response = await apiClient.post<ScalingGroup>(`/scaling/${id}/scale`, {
    desired_count: desiredCount,
  });
  return response.data;
}

/** Pause a scaling group. */
export async function pauseGroup(id: string): Promise<ScalingGroup> {
  const response = await apiClient.post<ScalingGroup>(`/scaling/${id}/pause`);
  return response.data;
}

/** Resume a paused scaling group. */
export async function resumeGroup(id: string): Promise<ScalingGroup> {
  const response = await apiClient.post<ScalingGroup>(`/scaling/${id}/resume`);
  return response.data;
}

/** List members of a scaling group. */
export async function listScalingGroupMembers(
  id: string,
): Promise<ScalingGroupMember[]> {
  const response = await apiClient.get<ScalingGroupMember[]>(
    `/scaling/${id}/members`,
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch all scaling groups.
 * Polls every 15 seconds when any group is in an active scaling state.
 */
export function useScalingGroups() {
  return useQuery<ScalingGroup[]>({
    queryKey: scalingKeys.list(),
    queryFn: listScalingGroups,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const anyActive = data.some((g) =>
        ['scaling_up', 'scaling_down', 'provisioning'].includes(g.status),
      );
      return anyActive ? 15_000 : false;
    },
  });
}

/**
 * Fetch a single scaling group by ID.
 * Polls every 10 seconds while the group is actively scaling.
 */
export function useScalingGroup(id: string | undefined) {
  return useQuery<ScalingGroup>({
    queryKey: scalingKeys.detail(id!),
    queryFn: () => getScalingGroup(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const isActive = ['scaling_up', 'scaling_down', 'provisioning'].includes(
        data.status,
      );
      return isActive ? 10_000 : false;
    },
  });
}

/** Create a new scaling group with cache invalidation. */
export function useCreateScalingGroup() {
  const queryClient = useQueryClient();

  return useMutation<ScalingGroup, Error, ScalingGroupCreateRequest>({
    mutationFn: createScalingGroup,
    onSuccess: (newGroup) => {
      queryClient.invalidateQueries({ queryKey: scalingKeys.all });
      queryClient.setQueryData(scalingKeys.detail(newGroup.id), newGroup);
    },
  });
}

/** Update an existing scaling group. */
export function useUpdateScalingGroup() {
  const queryClient = useQueryClient();

  return useMutation<
    ScalingGroup,
    Error,
    { id: string; data: ScalingGroupUpdateRequest }
  >({
    mutationFn: ({ id, data }) => updateScalingGroup(id, data),
    onSuccess: (updatedGroup, { id }) => {
      queryClient.invalidateQueries({ queryKey: scalingKeys.all });
      queryClient.setQueryData(scalingKeys.detail(id), updatedGroup);
    },
  });
}

/** Delete a scaling group. */
export function useDeleteScalingGroup() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteScalingGroup,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: scalingKeys.all });
      queryClient.removeQueries({ queryKey: scalingKeys.detail(id) });
    },
  });
}

/** Trigger a manual scale operation. */
export function useScaleGroup() {
  const queryClient = useQueryClient();

  return useMutation<ScalingGroup, Error, { id: string; desiredCount: number }>(
    {
      mutationFn: ({ id, desiredCount }) => scaleGroup(id, desiredCount),
      onSuccess: (updatedGroup, { id }) => {
        queryClient.invalidateQueries({ queryKey: scalingKeys.all });
        queryClient.setQueryData(scalingKeys.detail(id), updatedGroup);
      },
    },
  );
}

/** Pause a scaling group. */
export function usePauseGroup() {
  const queryClient = useQueryClient();

  return useMutation<ScalingGroup, Error, string>({
    mutationFn: pauseGroup,
    onSuccess: (updatedGroup, id) => {
      queryClient.invalidateQueries({ queryKey: scalingKeys.all });
      queryClient.setQueryData(scalingKeys.detail(id), updatedGroup);
    },
  });
}

/** Resume a paused scaling group. */
export function useResumeGroup() {
  const queryClient = useQueryClient();

  return useMutation<ScalingGroup, Error, string>({
    mutationFn: resumeGroup,
    onSuccess: (updatedGroup, id) => {
      queryClient.invalidateQueries({ queryKey: scalingKeys.all });
      queryClient.setQueryData(scalingKeys.detail(id), updatedGroup);
    },
  });
}
