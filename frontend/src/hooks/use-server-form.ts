'use client';

import { create } from 'zustand';
import type { ServerTemplate } from '@/lib/templates';
import type {
  ServerCreateRequest,
  OsType,
  InstanceSize,
  SecurityProfile,
  VolumeType,
} from '@/lib/api/types';

// ---------------------------------------------------------------------------
// Storage volume shape used in the form
// ---------------------------------------------------------------------------

export interface StorageVolume {
  drive_letter?: string;
  mount_point?: string;
  size_gb: number;
  volume_type: VolumeType;
}

// ---------------------------------------------------------------------------
// Form state
// ---------------------------------------------------------------------------

interface ServerFormState {
  // Step 1 -- Environment & OS
  environment: 'dev' | 'staging' | 'production';
  os_type: OsType;
  region: string;

  // Step 2 -- Instance Configuration
  instance_size: InstanceSize;
  vpc_id: string;
  subnet_id: string;
  server_name: string;

  // Step 3 -- Security & Networking
  security_profile: SecurityProfile;
  domain_join: boolean;
  tags: Record<string, string>;

  // Step 4 -- Software & Configuration
  puppet_role: string;
  software_packages: string[];
  additional_storage: StorageVolume[];

  // Template tracking
  template_id: string | undefined;

  // ------- Actions -------
  setField: <K extends keyof ServerFormState>(
    field: K,
    value: ServerFormState[K],
  ) => void;
  applyTemplate: (template: ServerTemplate) => void;
  reset: () => void;
  toCreateRequest: () => ServerCreateRequest;
}

// ---------------------------------------------------------------------------
// Defaults
// ---------------------------------------------------------------------------

const INITIAL_STATE = {
  environment: 'dev' as const,
  os_type: 'amazon_linux_2023' as OsType,
  region: 'us-east-1',
  instance_size: 'small' as InstanceSize,
  vpc_id: '',
  subnet_id: '',
  server_name: '',
  security_profile: 'internal_only' as SecurityProfile,
  domain_join: false,
  tags: {} as Record<string, string>,
  puppet_role: 'base',
  software_packages: [] as string[],
  additional_storage: [] as StorageVolume[],
  template_id: undefined as string | undefined,
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useServerForm = create<ServerFormState>((set, get) => ({
  ...INITIAL_STATE,

  setField: (field, value) => {
    set({ [field]: value } as Partial<ServerFormState>);
  },

  applyTemplate: (template) => {
    set({
      template_id: template.id,
      os_type: template.defaults.os_type as OsType,
      instance_size: template.defaults.instance_size as InstanceSize,
      security_profile: template.defaults.security_profile as SecurityProfile,
      puppet_role: template.defaults.puppet_role,
      domain_join: template.defaults.domain_join,
      software_packages: [...template.defaults.software_packages],
      additional_storage: template.defaults.additional_storage.map((s) => ({ ...s })),
    });
  },

  reset: () => {
    set({ ...INITIAL_STATE });
  },

  toCreateRequest: (): ServerCreateRequest => {
    const s = get();
    return {
      ...(s.server_name ? { server_name: s.server_name } : {}),
      environment: s.environment,
      os_type: s.os_type,
      instance_size: s.instance_size,
      region: s.region,
      vpc_id: s.vpc_id,
      subnet_id: s.subnet_id,
      security_profile: s.security_profile,
      domain_join: s.domain_join,
      software_packages: s.software_packages,
      puppet_role: s.puppet_role,
      additional_storage: s.additional_storage.map((vol) => ({
        drive_letter: vol.drive_letter ?? null,
        mount_point: vol.mount_point ?? null,
        size_gb: vol.size_gb,
        volume_type: vol.volume_type,
      })),
      tags: s.tags,
      ...(s.template_id ? { template_id: s.template_id } : {}),
    };
  },
}));
