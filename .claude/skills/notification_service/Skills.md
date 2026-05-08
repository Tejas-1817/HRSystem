---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – Notification Service

## Governance Rules
- **Domain Boundary:** Notification Service owns event fan‑out only.
- **Ownership:** No persistence of tickets, sprints, or CI/CD state; delivers messages to downstream consumers.

## Technical Standards
- **API Contracts:** Exposes subscription management endpoints under `/api/v1/notifications` (REST) and WebSocket endpoint `/ws/notifications`.
- **Performance Budgets:** WebSocket propagation < 500 ms; fan‑out processing latency < 50 ms.
- **Statelessness:** Service is stateless; fan‑out state stored in Redis streams.

## Execution Contracts
- **Published Events:** None (acts as consumer).
- **Consumed Events:** `TicketCreated`, `TicketAssigned`, `SprintStarted`, `BuildSucceeded`, `BuildFailed`, `DeploymentRolledBack` (via event bus).
- **Event Format:** JSON schema versioned, correlation IDs mandatory, retry‑safe processing.

## AI Constraints
- **Must Not:** Modify RBAC policies, alter migration history, change shared schemas, remove observability instrumentation, disable audit logging, modify security middleware.
- **Must:** Validate contracts before generation, preserve backward compatibility, run lint + type checks, maintain OpenAPI compliance.

## Distributed System Rules
- Service remains stateless.
- Prefers async event consumption; synchronous calls only for health checks.
- Correlation IDs required for every fan‑out message.
- Eventual consistency accepted for downstream UI updates.

## Production Requirements
- **Failure Handling:** Exponential backoff retries, dead‑letter queue for undeliverable notifications, circuit breaker for downstream webhook endpoints, graceful degradation when Redis stream is unavailable, idempotent processing of duplicate events.
- **Release Governance:** Semantic versioning, blue/green deployments, rollback strategy mandatory, feature flags for experimental notification channels, release approval gates.
- **Incident Management:** PagerDuty integration, severity levels (Sev1: total notification outage, Sev2: partial channel failure), incident timeline logging, post‑mortem generation, RCA tracking.

## Failure Policies
- Transient failures retried with exponential backoff (max 5 attempts).
- Messages failing after retries moved to DLQ with alert.
- Circuit breaker trips after 5 consecutive downstream failures (e.g., Slack webhook).
- During Redis outage, buffer events in in‑memory queue with size limit; drop oldest when full.

## Scalability Policies
- Horizontal scaling via Kubernetes HPA based on Kafka/Redis stream lag.
- Stateless design enables rapid pod scaling.
- Load tested for > 100 k notifications/sec.

## Security Boundaries
- JWT authentication enforced on subscription APIs.
- RBAC checks ensure only authorized clients can subscribe to specific topics.
- No direct DB access; all state in Redis.

## Observability Contracts
- Structured JSON logs with correlation ID, event type, delivery status.
- Prometheus metrics: `notifications_sent_total`, `notifications_failed_total`, `notification_latency_ms`.
- OpenTelemetry traces span from event receipt to fan‑out delivery.
- Grafana dashboards with SLO burn‑rate alerts for delivery latency.

## Release Governance
- Semantic version bump per breaking change.
- Blue/green deployment via Helm values `notification.enabled`.
- Feature flags via LaunchDarkly for new channels (e.g., SMS, Push).
- Release approval requires two senior engineers sign‑off.

## Incident Management
- **Sev1:** Complete loss of notification delivery – trigger immediate rollback and alert.
- **Sev2:** Failure of a major channel (e.g., email) – failover to backup channel.
- **Sev3:** Minor latency spikes – monitor and scale.
- Incident logs retained 365 days.

## Compliance Rules
- **PII Classification:** Notification payloads may contain user identifiers; encrypt at rest in Redis.
- **Retention Policies:** Notification events retained 30 days in DLQ, then purged.
- **Soft Delete:** Not applicable (ephemeral messages).
- **GDPR‑Ready Deletion:** Ability to purge user‑specific notifications on request.

## Runtime Expectations
- API gateway latency < 10 ms.
- Auth middleware latency < 5 ms.
- Service ready‑probe < 2 s.

## Event Contracts
- **TicketCreated (consumed):** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "payload": { "ticketId": "<uuid>", "projectId": "<uuid>", "title": "<string>" } }`
- **TicketAssigned (consumed):** Same schema version, includes assignee ID.
- All consumed events must be acknowledged only after successful fan‑out to all subscribed channels.
