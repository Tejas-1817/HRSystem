---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – Ticket Service

## Governance Rules
- **Domain Boundary:** Ticket Service owns ticket lifecycle only.
- **Ownership:** No cross‑domain data manipulation; interacts via events.

## Technical Standards
- **API Contracts:** CRUD endpoints versioned under `/api/v1/tickets`.
- **Performance Budgets:** Ticket query API < 40 ms, Redis cache lookup < 2 ms.
- **Statelessness:** Services are horizontally scalable; state persisted in PostgreSQL.

## Execution Contracts
- **Published Events:** `TicketCreated`, `TicketAssigned`.
- **Consumed Events:** Notification fanout, Search indexing, Audit logging, Analytics aggregation.
- **Event Format:** JSON schema versioned, correlation IDs mandatory, retry‑safe processing.

## AI Constraints
- **Must Not:** Modify RBAC policies, alter migration history, change shared schemas, remove observability instrumentation, disable audit logging, modify security middleware.
- **Must:** Validate contracts before generation, preserve backward compatibility, run lint + type checks, maintain OpenAPI compliance.

## Distributed System Rules
- Services remain stateless.
- Prefer async events for inter‑service communication.
- Synchronous calls only for critical workflows (e.g., authentication).
- Correlation IDs required across all calls.
- Eventual consistency accepted for analytics.

## Production Requirements
- **Failure Handling:** Exponential backoff retries, dead‑letter queue, circuit breaker for downstream services, graceful degradation during Redis outages, idempotent webhook processing.
- **Release Governance:** Semantic versioning, blue/green deployments, rollback strategy mandatory, feature flags for incomplete functionality, release approval gates.
- **Incident Management:** PagerDuty integration, severity levels defined, incident timeline logging, post‑mortem generation, RCA tracking.

## Failure Policies
- Transient failures retried with exponential backoff.
- Unprocessable messages moved to DLQ after 5 attempts.
- Circuit breaker trips after 5 consecutive downstream failures.
- During Redis outage, serve stale cache with stale‑while‑revalidate header.

## Scalability Policies
- Horizontal scaling via Kubernetes HPA.
- Stateless design enables pod autoscaling.
- Load tested to 10 k RPS for ticket creation.

## Security Boundaries
- JWT authentication enforced on all endpoints.
- RBAC checks enforced at service layer.
- No direct DB access from other services.

## Observability Contracts
- Structured JSON logging with correlation ID.
- Prometheus metrics: `tickets_created_total`, `tickets_query_latency`.
- OpenTelemetry traces propagated across event flow.
- Grafana dashboards with SLO burn‑rate alerts.

## Release Governance
- Semantic version bump per breaking change.
- Blue/green deployment via Helm values.
- Feature flags via LaunchDarkly for beta features.
- Release approval requires two senior engineers sign‑off.

## Incident Management
- Sev1: Full ticket service outage → immediate rollback.
- Sev2: Degraded query performance → scale pods, investigate DB.
- Sev3: Minor latency spikes → monitor and tune cache.
- Incident logs stored for 365 days.

## Compliance Rules
- PII classification: ticket comments may contain PII; encrypt at rest.
- Retention: tickets retained 7 years, soft‑delete enabled.
- GDPR deletion workflow via `DELETE /tickets/{id}` marks `deleted_at`.

## Runtime Expectations
- API gateway latency < 10 ms.
- Auth middleware latency < 5 ms.
- Service ready‑probe < 2 s.

## Event Contracts
- **TicketCreated:** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "ticketId": "<uuid>", "payload": {...} }`
- **TicketAssigned:** Same versioning, includes assignee ID.
- All events processed idempotently; consumer acknowledges after successful handling.
