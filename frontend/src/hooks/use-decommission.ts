/**
 * React Query mutation hook for the server decommission workflow.
 *
 * Wraps the decommissionServer API call with cache invalidation and
 * toast notifications for success/error states.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { decommissionServer } from '@/lib/api/decommission';
import { queryKeys } from '@/lib/api/hooks';
import type { ServerResponse } from '@/lib/api/types';
import type { AxiosError } from 'axios';

interface ApiErrorResponse {
  detail?: string;
}

export function useDecommission() {
  const queryClient = useQueryClient();

  return useMutation<ServerResponse, AxiosError<ApiErrorResponse>, string>({
    mutationFn: decommissionServer,
    onSuccess: (updatedServer, serverId) => {
      toast.success(
        `Decommission initiated for ${updatedServer.server_name}`,
        {
          description:
            'The server is being decommissioned. You can track progress on the server detail page.',
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
      toast.error('Failed to initiate decommission', {
        description: detail,
      });
    },
  });
}
