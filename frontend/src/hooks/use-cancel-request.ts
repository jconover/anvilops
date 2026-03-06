/**
 * React Query mutation hook for cancelling a pending server request.
 *
 * Wraps the cancelServer API call with cache invalidation and
 * toast notifications for success/error states.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { cancelServer } from '@/lib/api/endpoints';
import { queryKeys } from '@/lib/api/hooks';
import type { ServerResponse } from '@/lib/api/types';
import type { AxiosError } from 'axios';

interface ApiErrorResponse {
  detail?: string;
}

export function useCancelRequest() {
  const queryClient = useQueryClient();

  return useMutation<ServerResponse, AxiosError<ApiErrorResponse>, string>({
    mutationFn: cancelServer,
    onSuccess: (updatedServer, serverId) => {
      toast.success(
        `Request cancelled for ${updatedServer.server_name}`,
        {
          description:
            'The server request has been cancelled. No infrastructure was provisioned.',
        },
      );

      // Update the server detail cache with the new status
      queryClient.setQueryData(
        queryKeys.servers.detail(serverId),
        updatedServer,
      );

      // Invalidate all server queries so lists reflect the new status
      queryClient.invalidateQueries({ queryKey: queryKeys.servers.all });
    },
    onError: (error) => {
      const detail =
        error.response?.data?.detail ?? error.message ?? 'Unknown error';
      toast.error('Failed to cancel server request', {
        description: detail,
      });
    },
  });
}
