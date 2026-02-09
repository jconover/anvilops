/**
 * Scheduled Builds API types, endpoint functions, and React Query hooks.
 *
 * Backend route reference:
 *   GET    /api/v1/schedules                    — list schedules
 *   GET    /api/v1/schedules/:id                — schedule detail with executions
 *   POST   /api/v1/schedules                    — create schedule
 *   PUT    /api/v1/schedules/:id                — update schedule
 *   DELETE /api/v1/schedules/:id                — delete schedule
 *   POST   /api/v1/schedules/:id/pause          — pause schedule
 *   POST   /api/v1/schedules/:id/resume         — resume schedule
 *   POST   /api/v1/schedules/:id/run-now        — trigger immediate execution
 *   GET    /api/v1/schedules/:id/executions     — execution history
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

/** Schedule status values. */
export type ScheduleStatus = 'active' | 'paused' | 'completed' | 'expired';

/** The type of schedule: one-time or recurring. */
export type ScheduleType = 'one_time' | 'recurring';

/** Execution status values. */
export type ExecutionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'skipped';

/** Server configuration embedded in a schedule. */
export interface ScheduleServerConfig {
  environment?: string;
  os_type?: string;
  instance_size?: string;
  region?: string;
  puppet_role?: string;
  template_id?: string;
  [key: string]: unknown;
}

/** A build schedule returned by the API. */
export interface BuildSchedule {
  id: string;
  name: string;
  description: string | null;
  status: ScheduleStatus;
  schedule_type: ScheduleType;
  scheduled_at: string | null;
  cron_expression: string | null;
  timezone: string;
  next_run_at: string | null;
  last_run_at: string | null;
  run_count: number;
  max_runs: number | null;
  server_config: ScheduleServerConfig | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

/** A single execution record for a schedule. */
export interface ScheduleExecution {
  id: string;
  schedule_id: string;
  server_request_id: string | null;
  status: ExecutionStatus;
  scheduled_for: string;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

/** Response from the list schedules endpoint. */
export interface ScheduleListResponse {
  schedules: BuildSchedule[];
  total: number;
}

/** Query parameters for listing schedules. */
export interface ScheduleListParams {
  status?: ScheduleStatus;
  schedule_type?: ScheduleType;
  skip?: number;
  limit?: number;
}

/** Request body for creating a schedule. */
export interface ScheduleCreateRequest {
  name: string;
  description?: string;
  schedule_type: ScheduleType;
  scheduled_at?: string;
  cron_expression?: string;
  timezone: string;
  max_runs?: number;
  server_config: ScheduleServerConfig;
}

/** Request body for updating a schedule. */
export interface ScheduleUpdateRequest {
  name?: string;
  description?: string;
  scheduled_at?: string;
  cron_expression?: string;
  timezone?: string;
  max_runs?: number;
  server_config?: ScheduleServerConfig;
}

/** Execution list response. */
export interface ExecutionListResponse {
  executions: ScheduleExecution[];
  total: number;
}

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

export const scheduleKeys = {
  all: ['schedules'] as const,
  list: (params?: ScheduleListParams) => ['schedules', 'list', params] as const,
  detail: (id: string) => ['schedules', id] as const,
  executions: (id: string) => ['schedules', id, 'executions'] as const,
} as const;

// ---------------------------------------------------------------------------
// Endpoint functions
// ---------------------------------------------------------------------------

/** List schedules with optional filtering and pagination. */
export async function listSchedules(
  params?: ScheduleListParams,
): Promise<ScheduleListResponse> {
  const response = await apiClient.get<ScheduleListResponse>(
    '/schedules',
    { params },
  );
  return response.data;
}

/** Get a single schedule by ID. */
export async function getSchedule(id: string): Promise<BuildSchedule> {
  const response = await apiClient.get<BuildSchedule>(`/schedules/${id}`);
  return response.data;
}

/** Create a new build schedule. */
export async function createSchedule(
  data: ScheduleCreateRequest,
): Promise<BuildSchedule> {
  const response = await apiClient.post<BuildSchedule>('/schedules', data);
  return response.data;
}

/** Update an existing build schedule. */
export async function updateSchedule(
  id: string,
  data: ScheduleUpdateRequest,
): Promise<BuildSchedule> {
  const response = await apiClient.put<BuildSchedule>(
    `/schedules/${id}`,
    data,
  );
  return response.data;
}

/** Delete a schedule. */
export async function deleteSchedule(id: string): Promise<void> {
  await apiClient.delete(`/schedules/${id}`);
}

/** Pause an active schedule. */
export async function pauseSchedule(id: string): Promise<BuildSchedule> {
  const response = await apiClient.post<BuildSchedule>(
    `/schedules/${id}/pause`,
  );
  return response.data;
}

/** Resume a paused schedule. */
export async function resumeSchedule(id: string): Promise<BuildSchedule> {
  const response = await apiClient.post<BuildSchedule>(
    `/schedules/${id}/resume`,
  );
  return response.data;
}

/** Trigger an immediate execution of a schedule. */
export async function runScheduleNow(id: string): Promise<ScheduleExecution> {
  const response = await apiClient.post<ScheduleExecution>(
    `/schedules/${id}/run-now`,
  );
  return response.data;
}

/** List execution history for a schedule. */
export async function listScheduleExecutions(
  id: string,
): Promise<ExecutionListResponse> {
  const response = await apiClient.get<ExecutionListResponse>(
    `/schedules/${id}/executions`,
  );
  return response.data;
}

// ---------------------------------------------------------------------------
// React Query hooks
// ---------------------------------------------------------------------------

/**
 * Fetch paginated schedule list.
 * Polls every 30 seconds for schedules with upcoming runs.
 */
export function useSchedules(params?: ScheduleListParams) {
  return useQuery<ScheduleListResponse>({
    queryKey: scheduleKeys.list(params),
    queryFn: () => listSchedules(params),
    refetchInterval: 30_000,
  });
}

/** Fetch a single schedule by ID. */
export function useSchedule(id: string | undefined) {
  return useQuery<BuildSchedule>({
    queryKey: scheduleKeys.detail(id!),
    queryFn: () => getSchedule(id!),
    enabled: !!id,
  });
}

/** Fetch execution history for a schedule. */
export function useScheduleExecutions(id: string | undefined) {
  return useQuery<ExecutionListResponse>({
    queryKey: scheduleKeys.executions(id!),
    queryFn: () => listScheduleExecutions(id!),
    enabled: !!id,
    refetchInterval: 15_000,
  });
}

/** Create a new build schedule. */
export function useCreateSchedule() {
  const queryClient = useQueryClient();

  return useMutation<BuildSchedule, Error, ScheduleCreateRequest>({
    mutationFn: createSchedule,
    onSuccess: (newSchedule) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
      queryClient.setQueryData(
        scheduleKeys.detail(newSchedule.id),
        newSchedule,
      );
    },
  });
}

/** Update an existing build schedule. */
export function useUpdateSchedule() {
  const queryClient = useQueryClient();

  return useMutation<
    BuildSchedule,
    Error,
    { id: string; data: ScheduleUpdateRequest }
  >({
    mutationFn: ({ id, data }) => updateSchedule(id, data),
    onSuccess: (updatedSchedule, { id }) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
      queryClient.setQueryData(
        scheduleKeys.detail(id),
        updatedSchedule,
      );
    },
  });
}

/** Delete a build schedule. */
export function useDeleteSchedule() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: deleteSchedule,
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
      queryClient.removeQueries({ queryKey: scheduleKeys.detail(id) });
    },
  });
}

/** Pause an active schedule. */
export function usePauseSchedule() {
  const queryClient = useQueryClient();

  return useMutation<BuildSchedule, Error, string>({
    mutationFn: pauseSchedule,
    onSuccess: (updatedSchedule, id) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
      queryClient.setQueryData(
        scheduleKeys.detail(id),
        updatedSchedule,
      );
    },
  });
}

/** Resume a paused schedule. */
export function useResumeSchedule() {
  const queryClient = useQueryClient();

  return useMutation<BuildSchedule, Error, string>({
    mutationFn: resumeSchedule,
    onSuccess: (updatedSchedule, id) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
      queryClient.setQueryData(
        scheduleKeys.detail(id),
        updatedSchedule,
      );
    },
  });
}

/** Trigger an immediate execution of a schedule. */
export function useRunNow() {
  const queryClient = useQueryClient();

  return useMutation<ScheduleExecution, Error, string>({
    mutationFn: runScheduleNow,
    onSuccess: (_execution, id) => {
      queryClient.invalidateQueries({ queryKey: scheduleKeys.all });
      queryClient.invalidateQueries({
        queryKey: scheduleKeys.executions(id),
      });
      queryClient.invalidateQueries({
        queryKey: scheduleKeys.detail(id),
      });
    },
  });
}
