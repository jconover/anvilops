import { useQuery } from '@tanstack/react-query';
import { getComplianceSummary } from '@/lib/api/endpoints';

export function useComplianceSummary() {
  return useQuery({
    queryKey: ['compliance-summary'],
    queryFn: () => getComplianceSummary(),
  });
}
