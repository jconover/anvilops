/**
 * TypeScript types matching the FastAPI Pydantic schemas.
 *
 * These types mirror the backend schemas defined in:
 *   backend/app/schemas/server.py
 *   backend/app/api/v1/puppet.py
 *   backend/app/api/v1/compliance.py
 */

// ---------------------------------------------------------------------------
// Enums / union types
// ---------------------------------------------------------------------------

export type ServerStatus =
  | 'pending'
  | 'approved'
  | 'provisioning'
  | 'configuring'
  | 'validating'
  | 'ready'
  | 'failed'
  | 'decommissioning'
  | 'decommissioned';

export type OsType =
  | 'windows_2022'
  | 'windows_2019'
  | 'amazon_linux_2023'
  | 'ubuntu_2204'
  | 'rhel_9';

export type InstanceSize = 'small' | 'medium' | 'large' | 'xl';

export type SecurityProfile = 'web_facing' | 'internal_only' | 'database' | 'custom';

export type VolumeType = 'gp3' | 'io2';

export type BuildStepStatus = 'pending' | 'in_progress' | 'completed' | 'failed';

export type UserRole = 'viewer' | 'builder' | 'builder_prod' | 'approver' | 'admin';

// ---------------------------------------------------------------------------
// Server schemas
// ---------------------------------------------------------------------------

/** Storage configuration for additional EBS volumes. */
export interface StorageConfig {
  drive_letter: string | null;
  mount_point: string | null;
  size_gb: number;
  volume_type: VolumeType;
}

/** POST body for creating a new server request. */
export interface ServerCreateRequest {
  server_name?: string;
  environment: 'dev' | 'staging' | 'production';
  os_type: OsType;
  instance_size: InstanceSize;
  region: string;
  vpc_id: string;
  subnet_id: string;
  security_profile: SecurityProfile;
  domain_join: boolean;
  software_packages: string[];
  puppet_role: string;
  additional_storage: StorageConfig[];
  tags: Record<string, string>;
  template_id?: string;
}

/** Server response returned by the API. */
export interface ServerResponse {
  id: string;
  server_name: string;
  environment: string;
  os_type: string;
  instance_size: string;
  region: string;
  status: ServerStatus;
  status_message: string | null;
  aws_instance_id: string | null;
  private_ip: string | null;
  public_ip: string | null;
  dns_name: string | null;
  awx_host_id: number | null;
  awx_job_ids: number[] | null;
  puppet_certname: string | null;
  puppet_node_group_id: string | null;
  puppet_last_report_status: string | null;
  puppet_enrolled_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Paginated server list response. */
export interface ServerListResponse {
  servers: ServerResponse[];
  total: number;
}

/** Query parameters for the server list endpoint. */
export interface ServerListParams {
  skip?: number;
  limit?: number;
  status?: ServerStatus;
  environment?: string;
  search?: string;
}

// ---------------------------------------------------------------------------
// Build step schemas
// ---------------------------------------------------------------------------

/** An individual step within a server build pipeline. */
export interface BuildStep {
  id: string;
  server_request_id: string;
  step_name: string;
  step_order: number;
  status: BuildStepStatus;
  output_log: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Puppet schemas (from backend/app/api/v1/puppet.py)
// ---------------------------------------------------------------------------

/** PuppetDB node status for a managed server. */
export interface PuppetNodeStatus {
  certname: string;
  server_id: string;
  server_name: string;
  deactivated: boolean;
  latest_report_status: string | null;
  latest_report_hash: string | null;
  report_timestamp: string | null;
  catalog_timestamp: string | null;
  facts_timestamp: string | null;
  report_environment: string | null;
}

/** Most recent Puppet report for a node. */
export interface PuppetReport {
  certname: string;
  server_id: string;
  hash: string | null;
  status: string | null;
  environment: string | null;
  configuration_version: string | null;
  start_time: string | null;
  end_time: string | null;
  report_format: number | null;
  resource_events: Record<string, number>;
  metrics: Record<string, Record<string, number>>;
}

/** Key Puppet facts for a node. */
export interface PuppetFacts {
  certname: string;
  server_id: string;
  facts: Record<string, unknown>;
}

/** Aggregate compliance summary from the puppet router. */
export interface PuppetComplianceSummary {
  total_nodes: number;
  compliant: number;
  changed: number;
  failed: number;
  unresponsive: number;
}

// ---------------------------------------------------------------------------
// Compliance schemas (from backend/app/api/v1/compliance.py)
// ---------------------------------------------------------------------------

/** Fleet-wide compliance summary from the compliance router. */
export interface ComplianceSummary {
  total: number;
  compliant: number;
  changed: number;
  failed: number;
  unresponsive: number;
  compliance_rate: number;
  nodes: ComplianceNode[];
  generated_at: string;
}

/** A single node entry in the compliance summary. */
export interface ComplianceNode {
  certname: string;
  status: string;
  report_timestamp: string | null;
  server_id?: string;
  server_name?: string;
  os_type?: string;
  puppet_role?: string;
}

/** Drift report for a single node. */
export interface NodeDriftReport {
  certname: string;
  server_id: string;
  server_name: string;
  drift_events: DriftEvent[];
  total_events: number;
  hours: number;
}

/** A single drift event within a drift report. */
export interface DriftEvent {
  resource_type: string;
  resource_title: string;
  property: string;
  old_value: string;
  new_value: string;
  timestamp: string;
  corrective_change: boolean;
}

/** Full compliance report for audit purposes. */
export interface ComplianceReport {
  report_generated_at: string;
  total_nodes: number;
  summary: {
    compliant: number;
    changed: number;
    failed: number;
    unresponsive: number;
    compliance_rate: number;
  };
  nodes: ComplianceNode[];
}

// ---------------------------------------------------------------------------
// User / Auth types
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}

// ---------------------------------------------------------------------------
// Generic API error shape
// ---------------------------------------------------------------------------

export interface ApiError {
  detail: string;
  status_code?: number;
}
