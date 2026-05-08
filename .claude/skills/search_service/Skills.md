---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – Search Service

## Governance Rules
- **Domain Boundary:** Search Service owns indexing and query capabilities only.
- **Ownership:** No direct modification of tickets, sprints, or CI/CD state; interacts strictly via event consumption and query APIs.

## Technical Standards
- **API Contracts:** REST search endpoint `/api/v1/search` with versioning (`/v1`). Supports full‑text, filters, pagination.
- **Performance Budgets:** Search indexing is async (no latency SLA); query latency < 50 ms for typical response sets.
- **Statelessness:** Service is stateless; index stored in Meilisearch/Elasticsearch cluster.

## Execution Contracts
- **Published Events:** None (consumer).
- **Consumed Events:** `TicketCreated`, `TicketUpdated`, `TicketDeleted`, `SprintStarted`, `BuildSucceeded`, `BuildFailed` – all processed to keep the index up‑to‑date.
- **Event Format:** JSON schema versioned, correlation IDs mandatory, retry‑safe processing.

## AI Constraints
- **Must Not:** Modify RBAC policies, alter migration history, change shared schemas, remove observability instrumentation, disable audit logging, modify security middleware.
- **Must:** Validate contracts before generating indexing pipelines, preserve backward compatibility of search API, run lint + type checks, maintain OpenAPI compliance.

## Distributed System Rules
- Service remains stateless.
- Prefers async event consumption for index updates; synchronous calls only for health checks.
- Correlation IDs required for each indexing request.
- Eventual consistency accepted for search results.

## Production Requirements
- **Failure Handling:** Exponential backoff retries for failed event processing, dead‑letter queue for events that cannot be indexed, circuit breaker for downstream Meilisearch/Elasticsearch cluster, graceful degradation (serve stale results) during index outage, idempotent indexing operations.
- **Release Governance:** Semantic versioning, blue/green deployments via Helm, rollback strategy mandatory, feature flags for experimental ranking algorithms, release approval gates.
- **Incident Management:** PagerDuty integration, severity levels (Sev1: total search outage, Sev2: degraded relevance), incident timeline logging, post‑mortem generation, RCA tracking.

## Failure Policies
- Transient failures retried with exponential backoff (max 5 attempts).
- Unprocessable events moved to DLQ after retries and trigger alert.
- Circuit breaker trips after 5 consecutive Meilisearch failures.
- During index outage, serve cached stale results with a `Stale‑While‑Revalidate` header.

## Scalability Policies
- Horizontal scaling via Kubernetes HPA based on query latency and indexing lag.
- Stateless design enables rapid pod scaling.
- Load tested for > 200 k queries per second.

## Security Boundaries
- JWT authentication enforced on search API.
- RBAC checks restrict access to privileged query features (e.g., admin analytics).
- No direct DB access; all reads go through the search cluster.

## Observability Contracts
- Structured JSON logs with correlation ID, request ID, and query metrics.
- Prometheus metrics: `search_queries_total`, `search_query_latency_ms`, `indexing_errors_total`.
- OpenTelemetry traces propagate from event receipt to index update and from API request to response.
- Grafana dashboards with SLO burn‑rate alerts for query latency and indexing lag.

## Release Governance
- Semantic version bump per breaking change.
- Blue/green deployment via Helm values `search.enabled`.
- Feature flags via LaunchDarkly for new ranking models.
- Release approval requires two senior engineers sign‑off.

## Incident Management
- **Sev1:** Complete search service outage – immediate rollback and alert.
- **Sev2:** Significant degradation of query latency – scale pods, investigate index health.
- **Sev3:** Minor relevance issues – monitor and tune ranking.
- Incident logs retained 365 days.

## Compliance Rules
- **PII Classification:** Search index may contain user‑generated content; PII must be redacted at ingestion.
- **Retention Policies:** Index data retained for 2 years; soft‑delete for removed tickets/sprints.
- **Soft Delete:** Documents marked deleted are removed from index after a grace period.
- **GDPR‑Ready Deletion:** `DELETE /search/documents/{id}` triggers immediate removal from index and logs for audit.

## Runtime Expectations
- API gateway latency < 10 ms.
- Auth middleware latency < 5 ms.
- Service ready‑probe < 2 s.

## Event Contracts
- **TicketCreated (consumed):** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "payload": { "ticketId": "<uuid>", "title": "<string>", "content": "<string>", "metadata": { ... } } }`
- **TicketUpdated (consumed):** Same schema, includes changed fields.
- **TicketDeleted (consumed):** `{ "schemaVersion": "1.0", "correlationId": "<uuid>", "payload": { "ticketId": "<uuid>" } }`
- All events processed idempotently; consumer acknowledges after successful indexing.
