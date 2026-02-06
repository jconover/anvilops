/**
 * Public API surface for the AnvilOps API client layer.
 *
 * Usage:
 *   import { useServers, createServer, type ServerResponse } from '@/lib/api';
 */

// Types
export type {
  ApiError,
  BuildStep,
  BuildStepStatus,
  ComplianceNode,
  ComplianceReport,
  ComplianceSummary,
  DriftEvent,
  InstanceSize,
  NodeDriftReport,
  OsType,
  PuppetComplianceSummary,
  PuppetFacts,
  PuppetNodeStatus,
  PuppetReport,
  SecurityProfile,
  ServerCreateRequest,
  ServerListParams,
  ServerListResponse,
  ServerResponse,
  ServerStatus,
  StorageConfig,
  User,
  UserRole,
  VolumeType,
} from './types';

// Axios client (for advanced / direct use)
export { default as apiClient } from './client';

// Endpoint functions
export {
  approveServer,
  createServer,
  deleteServer,
  getComplianceReport,
  getComplianceSummary,
  getNodeCompliance,
  getNodeDrift,
  getPuppetComplianceSummary,
  getPuppetFacts,
  getPuppetReport,
  getPuppetStatus,
  getServer,
  getServerBuildSteps,
  listServers,
} from './endpoints';

// React Query hooks
export {
  queryKeys,
  useApproveServer,
  useComplianceReport,
  useComplianceSummary,
  useCreateServer,
  useDeleteServer,
  useNodeCompliance,
  useNodeDrift,
  usePuppetComplianceSummary,
  usePuppetFacts,
  usePuppetReport,
  usePuppetStatus,
  useServer,
  useServerBuildSteps,
  useServers,
} from './hooks';
