import { useQuery } from '@tanstack/react-query';
import { listServers } from '@/lib/api/endpoints';
import type { ServerListParams } from '@/lib/api/types';

export function useServers(params?: ServerListParams) {
  return useQuery({
    queryKey: ['servers', params],
    queryFn: () => listServers(params),
  });
}
