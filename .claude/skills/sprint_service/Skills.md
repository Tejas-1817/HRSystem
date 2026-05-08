---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – Sprint Service

## Governance Rules
- **Domain Boundary:** Sprint Service owns sprint state only.
- **Ownership:** No manipulation of tickets, notifications, or CI/CD pipelines; interactions are event‑driven.

## Technical Standards
- **API Contracts:** CRUD endpoints under `/api/v1/sprints` with versioning.
- **Performance Budgets:** Sprint query API < 40 ms, Redis cache lookup < 2 ms (if used for sprint caching).
- **Statelessness:** Service is stateless; state persisted in PostgreSQL.

## Execution Contracts
- **Published Events:** `SprintStarted`.
- **Consumed Events:** Notification fanout, Search indexing, Audit logging, Analytics aggregation.
- **Event Format:** JSON schema versioned, correlation IDs mandatory, retry‑safe processing.

## AI Constraints
- **Must Not:** Modify RBAC policies, alter migration history, change shared schemas, remove observability instrumentation, disable audit logging, modify security middleware.
- **Must:** Validate contracts before generation, preserve backward compatibility, run lint + type checks, maintain OpenAPI compliance.

## Distributed System Rules
- Services remain stateless.
- Prefer async events for inter‑service communication.
- Synchronous calls limited to critical workflows (e.g., authentication).
- Correlation IDs required across all calls.
- Eventual consistency accepted for analytics.

## Production Requirements
- **Failure Handling:** Exponential backoff retries, dead‑letter queue, circuit breaker for downstream services, graceful degradation during Redis outages, idempotent webhook processing.
- **Release Governance:** Semantic versioning, blue/green deployments, rollback strategy mandatory, feature flags for incomplete functionality, release approval gates.
- **Incident Management:** PagerDuty integration, severity levels, incident timeline logging, post‑mortem generation, RCA tracking.

## Failure Policies
- Transient failures retried with exponential backoff.
- Unprocessable messages moved to DLQ after 5 attempts.
- Circuit breaker trips after 5 consecutive downstream failures.
- During Redis outage, serve stale cache with stale‑while‑revalidate header.

## Scalability Policies
- Horizontal scaling via Kubernetes HPA.
- Stateless design enables pod autoscaling.
- Load tested to support 10 k RPS for sprint state updates.

## Security Boundaries
- JWT authentication enforced on all endpoints.
- RBAC checks enforced at service layer.
- No direct DB access from other services.

## Observability Contracts
- Structured JSON logging with correlation ID.
- Prometheus metrics: `sprints_created_total`, `sprints_query_latency`.
- OpenTelemetry traces propagated across event flow.
- Grafana dashboards with SLO burn‑rate alerts.

## Release Governance
- Semantic version bump per breaking change.
- Blue/green deployment via Helm values.
- Feature flags via LaunchDarkly for beta functionality.
- Release approval requires two senior engineers sign‑off.

## Incident Management
- **Sev1:** Full sprint service outage → immediate rollback.
- **Sev2:** Degraded sprint query performance → scale pods, investigate DB.
- **Sev3:** Minor latency spikes → monitor and tune cache.
- Incident logs retained 365 days.

## Compliance Rules
- **PII Classification:** Sprint metadata does not contain PII, but related user IDs are encrypted at rest.
- **Retention Policies:** Sprint records retained for 5 years.
- **Soft Delete:** Supported for sprint cancellation, retained for audit.
- **GDPR‑Ready Deletion:** Deleting a sprint removes identifiers while preserving audit trail.

## Runtime Expectations
- API Gateway latency < 10 ms.
- Auth middleware latency < 5 ms.
- Service ready‑probe < 2 s.

## Event Contracts
- **SprintStarted:** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "sprintId": "<uuid>", "payload": { "projectId": "<uuid>", "startDate": "<ISO8601>", "endDate": "<ISO8601>" } }`
- All events processed idempotently; consumer acknowledges after successful handling.
