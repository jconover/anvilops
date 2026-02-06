'use client';

/**
 * React Query hook that auto-estimates cost when wizard form values change.
 *
 * Uses debouncing (500 ms) to avoid excessive API calls while the user is
 * still adjusting the form. Only fires when `instance_size` and `os_type`
 * are both selected, since those are the minimum inputs required by the
 * backend pricing engine.
 *
 * Returns: { estimate, isLoading, error }
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useServerForm } from '@/hooks/use-server-form';
import {
  estimateCost,
  type CostEstimateRequest,
  type CostEstimateResponse,
} from '@/lib/api/costs';

// ---------------------------------------------------------------------------
// Query key factory
// ---------------------------------------------------------------------------

function costQueryKey(config: CostEstimateRequest | null) {
  return ['costs', 'estimate', config] as const;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCostEstimate() {
  // Read just the fields we need from the zustand store.
  const instanceSize = useServerForm((s) => s.instance_size);
  const osType = useServerForm((s) => s.os_type);
  const region = useServerForm((s) => s.region);
  const additionalStorage = useServerForm((s) => s.additional_storage);

  // Build the request config — only valid when minimum fields are present.
  const requestConfig: CostEstimateRequest | null = useMemo(() => {
    if (!instanceSize || !osType) return null;

    return {
      instance_size: instanceSize,
      os_type: osType,
      region: region || 'us-east-1',
      additional_storage: additionalStorage.map((vol) => ({
        size_gb: vol.size_gb,
        volume_type: vol.volume_type,
      })),
    };
  }, [instanceSize, osType, region, additionalStorage]);

  // Debounce: delay updating the query input by 500 ms so we don't
  // fire a request on every keystroke / slider drag.
  const [debouncedConfig, setDebouncedConfig] =
    useState<CostEstimateRequest | null>(requestConfig);

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }
    timerRef.current = setTimeout(() => {
      setDebouncedConfig(requestConfig);
    }, 500);

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, [requestConfig]);

  // The actual query — only enabled when we have a valid config.
  const {
    data: estimate,
    isLoading,
    error,
  } = useQuery<CostEstimateResponse>({
    queryKey: costQueryKey(debouncedConfig),
    queryFn: () => estimateCost(debouncedConfig!),
    enabled: debouncedConfig !== null,
    staleTime: 5 * 60 * 1000, // 5 minutes — pricing doesn't change often
    retry: 1,
  });

  return {
    estimate: estimate ?? null,
    isLoading: isLoading && debouncedConfig !== null,
    error: error as Error | null,
  };
}
