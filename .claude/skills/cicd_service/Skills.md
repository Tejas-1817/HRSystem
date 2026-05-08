---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – CI/CD Service

## Governance Rules
- **Domain Boundary:** CI/CD Service owns webhook ingestion only. It receives webhooks from external CI systems (e.g., Jenkins, GitHub Actions) and emits internal events.
- **Ownership:** No direct manipulation of tickets, sprints, or infrastructure state; all interactions are event‑driven.

## Technical Standards
- **API Contracts:** Exposes `/api/v1/webhooks` endpoint (POST) with HMAC signature verification and versioned payload schema.
- **Performance Budgets:** Webhook ingestion latency < 10 ms; event emission latency < 5 ms.
- **Statelessness:** Service is stateless; incoming webhook data is persisted only via emitted events.

## Execution Contracts
- **Published Events:** `BuildSucceeded`, `BuildFailed`, `DeploymentRolledBack`.
- **Consumed Events:** None (source of events only).
- **Event Format:** JSON schema versioned, correlation IDs mandatory, retry‑safe processing.

## AI Constraints
- **Must Not:** Modify RBAC policies, alter migration history, change shared schemas, remove observability instrumentation, disable audit logging, modify security middleware.
- **Must:** Validate webhook contracts before acceptance, preserve backward compatibility of emitted events, run lint + type checks on payload processors, maintain OpenAPI compliance for the webhook endpoint.

## Distributed System Rules
- Service remains stateless.
- Prefers async event emission to downstream consumers (Notification, Search, Audit, Analytics).
- Synchronous processing only for webhook receipt and immediate validation.
- Correlation IDs required for each webhook and propagated to emitted events.
- Eventual consistency accepted for downstream analytics.

## Production Requirements
- **Failure Handling:** Exponential backoff retries for transient validation failures, dead‑letter queue for malformed or repeatedly failing webhooks, circuit breaker for downstream event bus, graceful degradation (reject new webhooks with 503 when overloaded), idempotent processing of duplicate webhook IDs.
- **Release Governance:** Semantic versioning, blue/green deployments via Helm, mandatory rollback strategy, feature flags for experimental webhook parsers, release approval gates.
- **Incident Management:** PagerDuty integration, severity levels (Sev1: webhook ingestion outage, Sev2: partial event loss), incident timeline logging, post‑mortem generation, RCA tracking.

## Failure Policies
- Transient validation errors retried with exponential backoff (max 5 attempts).
- Unprocessable webhook payloads moved to DLQ after retries and trigger alert.
- Circuit breaker trips after 5 consecutive downstream event bus failures.
- During overload, return `429 Too Many Requests` with retry‑after header.

## Scalability Policies
- Horizontal scaling via Kubernetes HPA based on webhook request rate and event bus lag.
- Stateless design enables rapid pod scaling.
- Load tested for > 20 k webhook requests per second.

## Security Boundaries
- HMAC signature verification for all incoming webhooks.
- JWT authentication optional for internal webhook sources.
- RBAC checks restrict which external systems can post to which event types.
- No direct DB writes; persistence occurs only via emitted events.

## Observability Contracts
- Structured JSON logs with correlation ID, webhook source, validation status.
- Prometheus metrics: `webhook_requests_total`, `webhook_success_total`, `webhook_failure_total`, `webhook_processing_latency_ms`.
- OpenTelemetry traces from receipt to event emission.
- Grafana dashboards with SLO burn‑rate alerts for ingestion latency.

## Release Governance
- Semantic version bump per breaking change in payload schema.
- Blue/green deployment via Helm values `cicd.enabled`.
- Feature flags via LaunchDarkly for new source integrations.
- Release approval requires two senior engineers sign‑off.

## Incident Management
- **Sev1:** Complete loss of webhook ingestion – immediate rollback and alert.
- **Sev2:** High failure rate (> 5 %) of webhook validation – scale pods, investigate source.
- **Sev3:** Minor latency spikes – monitor and tune HPA thresholds.
- Incident logs retained 365 days.

## Compliance Rules
- **PII Classification:** Webhook payloads must not contain PII; if they do, they must be redacted before emission.
- **Retention Policies:** Webhook logs retained 90 days; emitted events retained according to system‑wide policies.
- **Soft Delete:** Not applicable.
- **GDPR‑Ready Deletion:** Ability to purge stored webhook identifiers on request.

## Runtime Expectations
- API gateway latency < 10 ms.
- Auth middleware latency < 5 ms.
- Service ready‑probe < 2 s.

## Event Contracts
- **BuildSucceeded:** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "payload": { "buildId": "<uuid>", "status": "SUCCESS", "timestamp": "<ISO8601>" } }`
- **BuildFailed:** Same schema, `status": "FAILURE"` with error details.
- **DeploymentRolledBack:** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "payload": { "deploymentId": "<uuid>", "rollbackReason": "<string>", "timestamp": "<ISO8601>" } }`
- All events are emitted idempotently; downstream consumers acknowledge after successful handling.
