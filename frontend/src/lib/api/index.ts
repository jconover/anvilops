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

// Notification types
export type {
  NotificationItem,
  NotificationListResponse,
  NotificationListParams,
} from './notifications';

// Notification endpoint functions
export {
  listNotifications,
  getUnreadCount,
  markAsRead,
  markAllAsRead,
  deleteNotification as deleteNotificationApi,
} from './notifications';

// Notification React Query hooks
export {
  notificationKeys,
  useNotifications,
  useUnreadCount,
  useMarkAsRead,
  useMarkAllAsRead,
  useDeleteNotification,
} from './notifications';

// Region / VPC / Subnet types
export type { Region, VPC, Subnet } from './regions';

// Region endpoint functions
export { listRegions, listVPCs, listSubnets } from './regions';

// Region React Query hooks
export {
  regionKeys,
  useRegions,
  useVPCs,
  useSubnets,
} from './regions';

// Drift Detection types
export type {
  DriftSummary,
  EnhancedDriftEvent,
  DriftEventsResponse,
  DriftEventsParams,
  DriftAlert,
  TrendDataPoint,
  TopResource,
  TopServer,
  DriftTrends,
  DriftTimelineEvent,
  DriftTimelineResponse,
} from './drift';

// Drift Detection endpoint functions
export {
  getDriftSummary,
  getDriftEvents,
  getDriftTimeline,
  getDriftAlerts,
  acknowledgeDriftAlert,
  getDriftTrends,
} from './drift';

// Drift Detection React Query hooks
export {
  driftKeys,
  useDriftSummary,
  useDriftEvents,
  useDriftTimeline,
  useDriftAlerts,
  useAcknowledgeAlert,
  useDriftTrends,
} from './drift';
