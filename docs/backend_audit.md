# AnvilOps Backend Audit

> Generated 2026-03-12. Read-only audit of `backend/` for Port IDP integration planning.

---

## Table of Contents

1. [API Endpoints](#1-api-endpoints)
2. [Data Models](#2-data-models)
3. [Celery Tasks](#3-celery-tasks)
4. [Integration Points](#4-integration-points)

---

## 1. API Endpoints

**73 total endpoints** across 13 domain routers + 1 root health check. All versioned routes live under `/api/v1`.

### Health (root)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service liveness check (status + service name) |

### Servers (`/api/v1/servers`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create server build request (returns 202, dispatches Celery task) |
| GET | `/` | List server requests (optional status filter, pagination) |
| GET | `/{server_id}` | Get single server request |
| GET | `/{server_id}/steps` | Get build pipeline steps for a server |
| POST | `/{server_id}/cancel` | Cancel pending server request (revokes Celery task) |
| POST | `/{server_id}/decommission` | Trigger full decommission workflow |
| DELETE | `/{server_id}` | Delete a decommissioned server record |

### Puppet (`/api/v1/puppet`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/nodes/{server_id}/status` | Puppet node status from PuppetDB |
| GET | `/nodes/{server_id}/report` | Latest Puppet report (resource events + metrics) |
| GET | `/nodes/{server_id}/facts` | Selected Puppet facts for a node |
| GET | `/compliance` | Aggregate Puppet compliance summary for all managed nodes |

### Compliance (`/api/v1/compliance`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary` | Fleet-wide compliance summary with compliance rate |
| GET | `/nodes/{server_id}` | Single node compliance detail with resource counts |
| GET | `/nodes/{server_id}/drift` | Node drift report (default 24h lookback) |
| GET | `/report` | Full downloadable compliance report (audit-ready) |

### Templates (`/api/v1/templates`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List server templates (active by default) |
| GET | `/{template_id}` | Get single template |
| POST | `/` | Create new template (201) |
| PUT | `/{template_id}` | Partial update of existing template |
| DELETE | `/{template_id}` | Soft-delete template (sets is_active=false) |

### Costs (`/api/v1/costs`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/estimate` | Estimate server cost (monthly/annual breakdown, line items) |
| GET | `/pricing` | Static pricing table for frontend display |

### Slack (`/api/v1/slack`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/interactions` | Slack interactive message callbacks (HMAC-SHA256 verified) |

### Notifications (`/api/v1/notifications`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List notifications for current user (newest first + unread count) |
| GET | `/unread-count` | Count of unread notifications |
| POST | `/mark-read` | Mark specific notifications as read |
| POST | `/mark-all-read` | Mark all unread as read |
| DELETE | `/{notification_id}` | Delete a single notification |

### Audit (`/api/v1/audit`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/actions` | List distinct action types (for filter dropdowns) |
| GET | `/summary` | Aggregate audit statistics (daily counts, top actions/actors) |
| GET | `/` | List audit logs (paginated, filterable, newest first) |
| GET | `/{audit_id}` | Get single audit entry |

### Regions (`/api/v1/regions`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List supported AWS regions (with default flagged) |
| GET | `/{region}/vpcs` | List VPCs in region (live discovery or static dev data) |
| GET | `/{region}/vpcs/{vpc_id}/subnets` | List subnets (AZ, CIDR, IP count, public/private) |
| GET | `/{region}/availability-zones` | List AZs in region |

### Scaling (`/api/v1/scaling`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | List all scaling groups (optional status filter) |
| GET | `/{group_id}` | Get scaling group with members |
| POST | `/` | Create scaling group + trigger initial provisioning (202) |
| PUT | `/{group_id}` | Update scaling group config (partial, with reconciliation) |
| DELETE | `/{group_id}` | Delete group + decommission all members |
| POST | `/{group_id}/scale` | Manually scale to specific desired count |
| POST | `/{group_id}/pause` | Pause auto-scaling (members stay running) |
| POST | `/{group_id}/resume` | Resume auto-scaling |
| GET | `/{group_id}/members` | List group members (optional status filter) |

### CMDB (`/api/v1/cmdb`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status/{server_id}` | CMDB sync status + current CI record from ServiceNow |
| POST | `/sync/{server_id}` | Trigger manual CMDB sync for one server |
| POST | `/sync` | Trigger full CMDB reconciliation across all servers |
| GET | `/stats` | CMDB sync statistics (synced vs unsynced, by status) |

### Schedules (`/api/v1/schedules`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/` | Create build schedule (validates cron/future time) |
| GET | `/` | List schedules (optional status/type filter) |
| GET | `/{schedule_id}` | Get schedule with execution history |
| PUT | `/{schedule_id}` | Update schedule (partial, recomputes next_run_at) |
| DELETE | `/{schedule_id}` | Cancel + soft-delete schedule |
| POST | `/{schedule_id}/pause` | Pause active schedule (clears next_run_at) |
| POST | `/{schedule_id}/resume` | Resume paused schedule (recomputes next_run_at) |
| POST | `/{schedule_id}/run-now` | Trigger immediate execution (202) |
| GET | `/{schedule_id}/executions` | List execution history (optional status filter) |

### Drift (`/api/v1/drift`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/summary` | Fleet-wide drift summary (by severity/category, active alerts) |
| GET | `/events` | List drift events (filterable by server, severity, category, dates) |
| GET | `/events/{event_id}` | Get single drift event |
| GET | `/servers/{server_id}/timeline` | Drift timeline for server (default 7-day lookback) |
| GET | `/alerts` | List drift alerts (paginated, filterable) |
| POST | `/alerts/{alert_id}/acknowledge` | Acknowledge a drift alert |
| GET | `/trends` | Drift trending data over time (daily counts by category) |

---

## 2. Data Models

### SQLAlchemy ORM Models

All models inherit from `Base` providing: `id` (UUID PK), `created_at` (DateTime tz), `updated_at` (DateTime tz).

#### ServerRequest (`server_requests`)

Core entity tracking a server provisioning request through its lifecycle.

| Column | Type | Notes |
|--------|------|-------|
| `server_name` | String(128) | unique, indexed, NOT NULL |
| `environment` | String(32) | indexed, NOT NULL |
| `os_type` | String(64) | NOT NULL |
| `instance_size` | String(32) | NOT NULL |
| `region` | String(32) | default 'us-east-1' |
| `vpc_id` | String(64) | NOT NULL |
| `subnet_id` | String(64) | NOT NULL |
| `security_profile` | String(64) | default 'internal_only' |
| `domain_join` | Boolean | default false |
| `software_packages` | JSON | default '[]' |
| `additional_storage` | JSON | default '[]' |
| `tags` | JSON | default '{}' |
| `puppet_role` | String(64) | default 'base' |
| `template_id` | String(64) | nullable |
| `status` | String(32) | indexed, default 'pending' |
| `status_message` | String(512) | nullable |
| `aws_instance_id` | String(64) | nullable, set after TF apply |
| `private_ip` | String(45) | nullable, set after TF apply |
| `public_ip` | String(45) | nullable, set after TF apply |
| `dns_name` | String(256) | nullable, set after TF apply |
| `terraform_workspace` | String(128) | nullable |
| `terraform_state_key` | String(256) | nullable |
| `awx_host_id` | Integer | nullable, set after AWX config |
| `awx_inventory_id` | Integer | nullable |
| `awx_job_ids` | JSON | nullable |
| `puppet_certname` | String(256) | nullable, set after enrollment |
| `puppet_node_group_id` | String(64) | nullable |
| `puppet_last_report_status` | String(32) | nullable |
| `puppet_enrolled_at` | DateTime(tz) | nullable |
| `cmdb_sys_id` | String(64) | nullable, set after CMDB sync |

Relationships: `build_steps` -> list of BuildStep (cascade delete)
Composite index: `ix_server_requests_env_status` (environment, status)

#### BuildStep (`build_steps`)

Tracks individual pipeline steps within a server build.

| Column | Type | Notes |
|--------|------|-------|
| `server_request_id` | UUID FK | -> server_requests, indexed |
| `step_name` | String(64) | NOT NULL |
| `step_order` | Integer | NOT NULL |
| `status` | String(32) | default 'pending' |
| `started_at` | DateTime(tz) | nullable |
| `completed_at` | DateTime(tz) | nullable |
| `output_log` | Text | nullable |
| `error_message` | String(1024) | nullable |

Unique index: `ix_build_steps_request_order` (server_request_id, step_order)

#### ServerTemplate (`server_templates`)

Pre-built server configurations users can select from.

| Column | Type | Notes |
|--------|------|-------|
| `name` | String(100) | unique, indexed |
| `description` | Text | nullable |
| `icon` | String(50) | default 'server' |
| `is_active` | Boolean | default true |
| `sort_order` | Integer | default 0 |
| `os_type` | String(50) | NOT NULL |
| `instance_size` | String(20) | NOT NULL |
| `region` | String(20) | default 'us-east-1' |
| `security_profile` | String(20) | default 'internal_only' |
| `puppet_role` | String(50) | default 'base' |
| `domain_join` | Boolean | default false |
| `software_packages` | JSON | default '[]' |
| `additional_storage` | JSON | default '[]' |
| `default_tags` | JSON | default '{}' |

#### AuditLog (`audit_logs`)

Immutable audit trail for all platform actions.

| Column | Type | Notes |
|--------|------|-------|
| `timestamp` | DateTime(tz) | indexed, default now() |
| `action` | String(50) | indexed |
| `category` | String(30) | indexed |
| `actor_email` | String(255) | indexed, nullable |
| `actor_role` | String(30) | nullable |
| `resource_type` | String(50) | nullable |
| `resource_id` | String(36) | indexed, nullable |
| `resource_name` | String(255) | nullable |
| `details` | JSON | nullable |
| `ip_address` | String(45) | nullable |
| `user_agent` | String(500) | nullable |
| `status` | String(20) | default 'success' |
| `error_message` | Text | nullable |

Composite indexes: `(category, action)`, `(resource_type, resource_id)`, `(timestamp DESC)`

#### Notification (`notifications`)

In-app notifications per user.

| Column | Type | Notes |
|--------|------|-------|
| `user_email` | String(255) | indexed |
| `title` | String(200) | NOT NULL |
| `message` | Text | NOT NULL |
| `category` | String(30) | default 'system' |
| `severity` | String(20) | default 'info' |
| `is_read` | Boolean | indexed, default false |
| `read_at` | DateTime(tz) | nullable |
| `resource_type` | String(50) | nullable |
| `resource_id` | String(36) | nullable |
| `action_url` | String(500) | nullable |
| `icon` | String(50) | nullable |
| `details` | JSON | nullable |

#### DriftEvent (`drift_events`)

Individual drift events detected by Puppet compliance polling.

| Column | Type | Notes |
|--------|------|-------|
| `server_request_id` | UUID FK | -> server_requests, indexed |
| `certname` | String(255) | indexed |
| `detected_at` | DateTime(tz) | indexed |
| `resolved_at` | DateTime(tz) | nullable |
| `resource_type` | String(100) | NOT NULL |
| `resource_title` | String(500) | NOT NULL |
| `property_name` | String(100) | NOT NULL |
| `old_value` | Text | nullable |
| `new_value` | Text | nullable |
| `severity` | String(20) | default 'medium' |
| `is_corrective` | Boolean | default false |
| `is_resolved` | Boolean | default false |
| `resolution_type` | String(30) | nullable |
| `drift_category` | String(50) | default 'configuration' |
| `cis_control_id` | String(20) | nullable |
| `report_hash` | String(64) | indexed, nullable |

Relationships: `alerts` -> list of DriftAlert (cascade delete)

#### DriftAlert (`drift_alerts`)

Alerts generated from drift patterns (repeated, simultaneous, compliance drop).

| Column | Type | Notes |
|--------|------|-------|
| `drift_event_id` | UUID FK | -> drift_events, nullable, SET NULL on delete |
| `server_request_id` | UUID FK | -> server_requests, nullable, SET NULL on delete |
| `alert_type` | String(30) | NOT NULL |
| `severity` | String(20) | default 'medium' |
| `title` | String(200) | NOT NULL |
| `message` | Text | NOT NULL |
| `is_acknowledged` | Boolean | default false |
| `acknowledged_by` | String(255) | nullable |
| `acknowledged_at` | DateTime(tz) | nullable |

#### ScalingGroup (`scaling_groups`)

Auto-scaling group definitions with policies.

| Column | Type | Notes |
|--------|------|-------|
| `name` | String(100) | unique, indexed |
| `description` | Text | nullable |
| `status` | String(30) | indexed, default 'active' |
| `environment` | String(20) | NOT NULL |
| `os_type` | String(50) | NOT NULL |
| `instance_size` | String(20) | NOT NULL |
| `region` | String(20) | NOT NULL |
| `vpc_id` | String(50) | NOT NULL |
| `subnet_id` | String(50) | NOT NULL |
| `security_profile` | String(20) | default 'internal_only' |
| `puppet_role` | String(50) | default 'base' |
| `min_instances` | Integer | default 1 |
| `max_instances` | Integer | default 5 |
| `desired_count` | Integer | default 1 |
| `current_count` | Integer | default 0 |
| `scale_up_threshold` | Integer | default 80 |
| `scale_down_threshold` | Integer | default 20 |
| `cooldown_seconds` | Integer | default 300 |
| `last_scaled_at` | DateTime(tz) | nullable |

Relationships: `members` -> list of ScalingGroupMember (cascade delete)

#### ScalingGroupMember (`scaling_group_members`)

| Column | Type | Notes |
|--------|------|-------|
| `scaling_group_id` | UUID FK | -> scaling_groups, indexed |
| `server_request_id` | UUID FK | -> server_requests, nullable, SET NULL on delete |
| `member_index` | Integer | NOT NULL |
| `status` | String(30) | default 'active' |

#### BuildSchedule (`build_schedules`)

Scheduled (one-time or recurring) server builds.

| Column | Type | Notes |
|--------|------|-------|
| `name` | String(100) | NOT NULL |
| `description` | Text | nullable |
| `status` | String(30) | indexed, default 'active' |
| `schedule_type` | String(20) | 'one_time' or 'recurring' |
| `scheduled_at` | DateTime(tz) | nullable (one_time) |
| `cron_expression` | String(100) | nullable (recurring) |
| `timezone` | String(50) | default 'UTC' |
| `next_run_at` | DateTime(tz) | nullable |
| `last_run_at` | DateTime(tz) | nullable |
| `server_config` | JSON | full ServerCreateRequest payload |
| `max_runs` | Integer | nullable (null = unlimited) |
| `run_count` | Integer | default 0 |
| `created_by` | String(255) | nullable |

Relationships: `executions` -> list of ScheduleExecution (cascade delete)

#### ScheduleExecution (`schedule_executions`)

| Column | Type | Notes |
|--------|------|-------|
| `schedule_id` | UUID FK | -> build_schedules, indexed |
| `server_request_id` | UUID FK | -> server_requests, nullable, SET NULL on delete |
| `status` | String(30) | indexed, default 'pending' |
| `scheduled_for` | DateTime(tz) | NOT NULL |
| `started_at` | DateTime(tz) | nullable |
| `completed_at` | DateTime(tz) | nullable |
| `error_message` | Text | nullable |

### Pydantic Schemas (Request/Response)

Organized by domain. All response schemas use `model_config = {"from_attributes": True}`.

| Schema | File | Purpose |
|--------|------|---------|
| `StorageConfig` | `schemas/server.py` | Nested EBS volume config (drive_letter/mount_point, size_gb, volume_type) |
| `ServerCreateRequest` | `schemas/server.py` | Server build request input (environment, os_type, instance_size, vpc_id, subnet_id, etc.) |
| `ServerResponse` | `schemas/server.py` | Full server record output (all fields + AWS/AWX/Puppet/CMDB metadata) |
| `BuildStepResponse` | `schemas/server.py` | Build step output (step_name, status, output_log, timestamps) |
| `ServerListResponse` | `schemas/server.py` | Paginated server list (servers[], total) |
| `TemplateCreate` | `schemas/template.py` | Template creation input |
| `TemplateUpdate` | `schemas/template.py` | Partial template update (all fields optional) |
| `TemplateResponse` | `schemas/template.py` | Template output |
| `TemplateListResponse` | `schemas/template.py` | Paginated template list |
| `AuditLogResponse` | `schemas/audit.py` | Single audit entry output |
| `AuditLogListResponse` | `schemas/audit.py` | Paginated audit list (logs[], total, page, page_size) |
| `AuditQueryParams` | `schemas/audit.py` | Audit filter params (action, category, actor, resource, dates, status) |
| `AuditSummaryResponse` | `schemas/audit.py` | Dashboard stats (daily_counts, top_actions, top_actors, total) |
| `CMDBSyncStatusResponse` | `schemas/cmdb.py` | Single server CMDB status (cmdb_sys_id, cmdb_ci record, relationships) |
| `CMDBSyncTriggerResponse` | `schemas/cmdb.py` | Manual sync trigger result (task_id) |
| `CMDBFullSyncResponse` | `schemas/cmdb.py` | Full reconciliation trigger result (task_id) |
| `CMDBSyncStatsResponse` | `schemas/cmdb.py` | Fleet CMDB stats (synced/unsynced counts, by_status) |
| `NotificationResponse` | `schemas/notification.py` | Single notification output |
| `NotificationListResponse` | `schemas/notification.py` | Paginated notifications (notifications[], total, unread_count) |
| `NotificationMarkReadRequest` | `schemas/notification.py` | Mark-read input (notification_ids[]) |
| `ScalingGroupCreate` | `schemas/scaling.py` | Scaling group creation (with cross-field validators for min/max/desired) |
| `ScalingGroupUpdate` | `schemas/scaling.py` | Partial scaling group update |
| `ScaleAction` | `schemas/scaling.py` | Manual scale input (desired_count) |
| `ScalingGroupResponse` | `schemas/scaling.py` | Full scaling group output (includes members[]) |
| `ScalingGroupMemberResponse` | `schemas/scaling.py` | Single member output |
| `DriftEventResponse` | `schemas/drift.py` | Single drift event output |
| `DriftEventListResponse` | `schemas/drift.py` | Paginated drift events |
| `DriftAlertResponse` | `schemas/drift.py` | Single drift alert output |
| `DriftAlertListResponse` | `schemas/drift.py` | Paginated drift alerts |
| `AcknowledgeAlertRequest` | `schemas/drift.py` | Acknowledge input (acknowledged_by) |
| `DriftSummaryResponse` | `schemas/drift.py` | Fleet drift summary (by severity/category, active alerts, affected servers) |
| `DriftTimelineResponse` | `schemas/drift.py` | Per-server drift timeline |
| `DriftTrendsResponse` | `schemas/drift.py` | Trending data (daily counts by category for charting) |
| `ScheduleCreate` | `schemas/schedule.py` | Schedule creation (with validators for one_time vs recurring) |
| `ScheduleUpdate` | `schemas/schedule.py` | Partial schedule update |
| `ScheduleResponse` | `schemas/schedule.py` | Schedule output |
| `ScheduleDetailResponse` | `schemas/schedule.py` | Schedule + execution history |
| `ExecutionResponse` | `schemas/schedule.py` | Single execution record |

---

## 3. Celery Tasks

### Configuration (`app/worker/celery_app.py`)

- **Broker/Backend**: Redis (`REDIS_URL`)
- **Serialization**: JSON
- **Task time limits**: 40 min soft / 50 min hard
- **Worker memory**: 400 MB per child, recycle after 50 tasks
- **Prefetch**: 1 (one task per worker at a time)
- **Late ack**: enabled (task not ack'd until complete)
- **Result TTL**: 24 hours

### Build Pipeline Tasks

```
run_server_build (orchestrator)
  |-- terraform_plan
  |-- terraform_apply        -> captures instance_id, IPs, dns_name
  |-- awx_configure          -> runs 4 sequential Ansible job templates
  |-- puppet_enroll           -> signs cert, classifies node, waits for agent run
  |-- run_validation          -> advisory checks (EC2 status, SSM, Puppet enrollment)
  |-- [on success] mark "ready"
  |-- [on TF/AWX failure] terraform_destroy (rollback), mark "failed"
  |-- [on Puppet failure] mark "failed" but NO rollback (infra stays)
```

#### `run_server_build` (orchestrator)
- **Task name**: `tasks.run_server_build`
- **Params**: `server_request_id` (str)
- **Retries**: 0 (no retries)
- **Services**: TerraformService, AWXServiceSync, PuppetEnterpriseServiceSync

#### `terraform_plan`
- **Task name**: `tasks.terraform_plan`
- **Params**: `server_request_id`, `build_step_id` (optional)
- **Operations**: Init workspace, generate tfvars, run `terraform plan`

#### `terraform_apply`
- **Task name**: `tasks.terraform_apply`
- **Params**: `server_request_id`, `build_step_id` (optional)
- **Operations**: Setup workspace, run `terraform apply -auto-approve`, extract outputs

#### `terraform_destroy`
- **Task name**: `tasks.terraform_destroy`
- **Params**: `server_request_id`
- **Operations**: Init, setup workspace, run `terraform destroy -auto-approve`
- **Used by**: Orchestrator rollback + decommission pipeline

#### `awx_configure`
- **Task name**: `tasks.awx_configure`
- **Params**: `server_request_id`, `build_step_id` (optional)
- **Operations**: Calls `AWXServiceSync.run_configuration_pipeline()` (4 sequential job templates: base, domain-join, software, agents)

#### `awx_decommission`
- **Task name**: `tasks.awx_decommission`
- **Params**: `server_request_id`
- **Operations**: Removes host from AWX inventory (best-effort)

#### `puppet_enroll`
- **Task name**: `tasks.puppet_enroll`
- **Params**: `server_request_id`, `build_step_id` (optional)
- **Operations**: Signs certificate, creates node group, classifies node by environment/role, waits for agent run

#### `puppet_decommission`
- **Task name**: `tasks.puppet_decommission`
- **Params**: `server_request_id`
- **Operations**: PuppetDB deactivation, classifier unpin, cert revoke/delete (best-effort)

#### `run_validation`
- **Task name**: `tasks.run_validation`
- **Params**: `server_request_id`, `build_step_id` (optional)
- **Checks**: EC2 instance status (boto3), SSM agent connectivity (boto3), Puppet enrollment (PuppetDB)
- **Impact**: Advisory only -- never blocks build, always marked "completed"

### Decommission Pipeline

```
run_server_decommission
  |-- puppet_decommission    (best-effort)
  |-- awx_decommission       (best-effort)
  |-- terraform_destroy      (HARD FAILURE if this fails)
  |-- dns_cleanup            (best-effort, stub)
  |-- [on TF success] clear metadata, mark "decommissioned"
  |-- [on TF failure] mark "failed", metadata preserved
```

#### `run_server_decommission`
- **Task name**: `tasks.run_server_decommission`
- **Params**: `server_request_id`
- **Retries**: 0

### Async / Best-Effort Tasks

#### `cmdb_sync_server`
- **Task name**: `tasks.cmdb_sync_server`
- **Params**: `server_request_id`, `event_type` (server_created | server_updated | server_decommissioned)
- **Retries**: 3 (30s delay)
- **Soft time limit**: 120s
- **Operations**: Syncs server state to ServiceNow CMDB, persists `cmdb_sys_id` back

#### `cmdb_full_sync`
- **Task name**: `tasks.cmdb_full_sync`
- **Retries**: 1 (60s delay)
- **Soft time limit**: 600s
- **Operations**: Full CMDB reconciliation across all servers

#### `send_slack_notification`
- **Task name**: `tasks.send_slack_notification`
- **Operations**: Posts build status messages to Slack via webhook (best-effort)

### Periodic Tasks (Celery Beat)

| Task | Interval | Description |
|------|----------|-------------|
| `process_scheduled_builds` | Every 60s | Checks for due schedules, dispatches `run_server_build` |
| `check_scaling_triggers` | Every 60s | Evaluates scaling thresholds, dispatches `scale_group` |
| `poll_drift_events` | Every 5 min | Polls PuppetDB for corrective changes, creates DriftEvents |
| `generate_drift_report` | Daily 6 AM UTC | Generates daily drift summary report |

### Scaling Tasks

#### `scale_group`
- **Params**: `group_id`, `desired_count`
- **Operations**: Provisions or decommissions members to reach desired count, respects cooldown

#### `check_scaling_triggers`
- **Operations**: Queries CloudWatch metrics, evaluates thresholds, dispatches `scale_group` if needed

---

## 4. Integration Points

AnvilOps integrates with **7 external systems**. All configured via env vars in `app/core/config.py`.

### Integration Architecture

```
                        +--------------+
                        |  AnvilOps    |
                        |  Backend     |
                        +------+-------+
                               |
          +--------------------+--------------------+
          |          |         |         |           |
    +-----v--+ +----v---+ +--v----+ +--v-----+ +--v--------+
    |Terraform| |  AWX   | |Puppet | |Service | |  Slack    |
    | (CLI)   | | (REST) | | (REST)| |Now     | | (Webhook) |
    +---------+ +--------+ +-------+ |(REST)  | +-----------+
                                      +--------+
          +-----v-----+   +----v----+
          | AWS boto3  |   |PuppetDB |
          | (SDK)      |   |(PQL)    |
          +------------+   +---------+
```

### 1. Terraform -- Infrastructure Provisioning

| Property | Value |
|----------|-------|
| **Service class** | `TerraformService` |
| **Client** | `subprocess.run()` with 600s timeout |
| **Auth** | AWS credentials via env/IAM (inherited) |
| **Operations** | `init`, `plan`, `apply -auto-approve`, `destroy`, `get_outputs` |
| **Data flow** | Generates tfvars from ServerRequest -> runs TF -> captures outputs (instance_id, IPs, dns_name) |
| **Criticality** | **Critical** -- failure blocks/rolls back build |

### 2. AWX (Ansible Tower) -- Day-1 Configuration

| Property | Value |
|----------|-------|
| **Service classes** | `AWXService` (async), `AWXServiceSync` (sync) |
| **Client** | httpx (AsyncClient for FastAPI, Client for Celery) |
| **Auth** | HTTP Basic Auth (`AWX_USERNAME`, `AWX_PASSWORD`) |
| **Base URL** | `AWX_BASE_URL` |
| **Endpoints** | `/api/v2/{hosts,groups,inventories,job_templates,jobs}/` |
| **Flow** | Adds server to inventory by IP -> launches 4 sequential job templates (base -> domain-join -> software -> agents) -> polls each job every 10s |
| **Timeout** | 10s polling interval, 600s job timeout |
| **Criticality** | **Critical** -- failure triggers TF rollback |

### 3. Puppet Enterprise -- Day-2+ Compliance

| Property | Value |
|----------|-------|
| **Service classes** | `PuppetEnterpriseService` (async), `PuppetEnterpriseServiceSync` (sync) |
| **Client** | httpx |
| **Auth** | Token header `X-Authentication: {PUPPET_API_TOKEN}` |
| **Base URL** | `PUPPET_BASE_URL` |
| **API Ports** | 8140 (CA: cert signing/revocation), 4433 (Classifier: node groups), 8081 (PuppetDB: queries), 8143 (Orchestrator: on-demand runs) |
| **Flow** | Signs cert -> creates node group -> pins node by environment/role -> polls agent run |
| **Timeout** | 30s polling interval, 600s node checkin timeout |
| **Criticality** | **Critical** for enrollment (marks failed but NO rollback), **Best-effort** for decommission |

### 4. ServiceNow CMDB -- Configuration Item Lifecycle

| Property | Value |
|----------|-------|
| **Service classes** | `ServiceNowClient`, `CMDBSyncService` |
| **Client** | httpx |
| **Auth** | HTTP Basic Auth (`SERVICENOW_USERNAME`, `SERVICENOW_PASSWORD`) |
| **Base URL** | `SERVICENOW_INSTANCE_URL` |
| **Endpoints** | `/api/now/table/{cmdb_ci_server,cmdb_rel_ci}` |
| **Flow** | Creates CI on build success -> updates with IP/DNS/Puppet info -> retires on decommission |
| **Feature flag** | `SERVICENOW_ENABLED` (can be disabled) |
| **Timeout** | 30s request timeout |
| **Criticality** | **Best-effort** -- retries 3x, never blocks pipeline |

### 5. Slack -- Notifications & Interactive Approvals

| Property | Value |
|----------|-------|
| **Service classes** | `SlackNotifier` (outbound), `SlackInteractiveHandler` (inbound) |
| **Auth** | Outbound: webhook URL; Inbound: HMAC-SHA256 signature verification (`SLACK_SIGNING_SECRET`) |
| **Notifications** | Build started/completed/failed, approval requested/granted/rejected, decommission events |
| **Interactive** | Approve/Reject buttons via `/api/v1/slack/interactions` callback |
| **Feature flag** | `SLACK_ENABLED` |
| **Timeout** | 10s webhook timeout |
| **Criticality** | **Best-effort** -- never blocks pipeline |

### 6. PuppetDB Drift Monitoring -- Compliance Alerting

| Property | Value |
|----------|-------|
| **Service classes** | `DriftMonitor` (sync, periodic), `AsyncDriftMonitor` (async, queries) |
| **Auth** | Same Puppet token |
| **Endpoints** | `/pdb/query/v4/{reports,events}` (PQL queries) |
| **Flow** | Polls every 5 min -> extracts corrective changes -> categorizes by resource type/severity -> maps to CIS controls -> detects patterns (repeated drift, simultaneous drift, compliance drop) |
| **Timeout** | 30s request timeout |
| **Criticality** | **Best-effort** -- monitoring only |

### 7. AWS (boto3) -- Regional Discovery

| Property | Value |
|----------|-------|
| **Service class** | `RegionService` |
| **Auth** | AWS credential chain (env vars -> IAM role -> ~/.aws/credentials) |
| **Operations** | `describe_vpcs`, `describe_subnets`, `describe_availability_zones` |
| **Flow** | On-demand for server builder wizard -> discovers VPCs/subnets/AZs -> falls back to static dev data if boto3 unavailable |
| **Criticality** | **Optional** -- gracefully degrades to hardcoded data |

### Configuration Variables Summary

```
# Database & Cache
DATABASE_URL          # PostgreSQL (asyncpg for FastAPI, psycopg2 for Celery)
REDIS_URL             # Celery broker + result backend

# Terraform
# (inherits AWS credentials from environment/IAM)

# AWX
AWX_BASE_URL, AWX_USERNAME, AWX_PASSWORD, AWX_VERIFY_SSL

# Puppet Enterprise
PUPPET_BASE_URL, PUPPET_API_TOKEN, PUPPET_VERIFY_SSL

# ServiceNow
SERVICENOW_INSTANCE_URL, SERVICENOW_USERNAME, SERVICENOW_PASSWORD, SERVICENOW_ENABLED

# Slack
SLACK_WEBHOOK_URL, SLACK_SIGNING_SECRET, SLACK_ENABLED, SLACK_CHANNEL

# AWS
AWS_DEFAULT_REGION, ALLOWED_REGIONS
```

### Error Handling Pattern

| Category | Services | Behavior |
|----------|----------|----------|
| **Critical** | Terraform, AWX | Failure triggers TF destroy rollback, marks build "failed" |
| **Critical (no rollback)** | Puppet enrollment | Failure marks "failed" but infrastructure stays provisioned |
| **Best-effort** | ServiceNow, Slack, drift monitoring | Log errors, retry where configured, never raise to pipeline |
| **Optional** | boto3 region discovery | Graceful fallback to static data |

### Exception Hierarchy

- **AWX**: `AWXConnectionError`, `AWXAuthError`, `AWXError`, `AWXTimeoutError`
- **Puppet**: `PuppetConnectionError`, `PuppetAuthError`, `PuppetError`, `PuppetTimeoutError`
- Both use httpx exceptions underneath

### Async/Sync Dual Pattern

AWX and Puppet both implement two wrappers sharing the same logic:
- **Async** (`AWXService`, `PuppetEnterpriseService`) -- used by FastAPI endpoints (httpx AsyncClient)
- **Sync** (`AWXServiceSync`, `PuppetEnterpriseServiceSync`) -- used by Celery workers (httpx Client)

---

## Port IDP Integration Surface Area

Based on this audit, likely touch points for a Port IDP integration:

1. **New service**: `app/services/port.py` -- Port API client (async/sync dual pattern, matching AWX/Puppet)
2. **New schemas**: `app/schemas/port.py` -- Port entity/webhook request/response models
3. **New endpoint(s)**: `app/api/v1/port.py` -- Webhook receiver for Port actions, entity sync status
4. **New task(s)**: `app/tasks/port.py` -- Async entity sync (similar to `cmdb_sync_server`)
5. **Model changes**: Potentially add `port_entity_id` to `ServerRequest` (like `cmdb_sys_id`)
6. **Config**: Add `PORT_*` env vars to `app/core/config.py`
7. **Router registration**: Add to `app/api/v1/router.py`
8. **Existing hooks**: Potentially dispatch Port sync from `run_server_build` and `run_server_decommission` (like CMDB sync)
