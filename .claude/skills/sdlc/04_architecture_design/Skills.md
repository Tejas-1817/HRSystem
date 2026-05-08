---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – SDLC Phase 04: Architecture Design

## PURPOSE
Define the role, responsibilities, and deliverables for the **Architecture Design** phase. Produce a scalable system architecture, component diagram, data‑flow diagram, and document trade‑offs.

## MODULE ARCHITECTURE
- **Folder:** `sdlc/04_architecture_design/`
- **File:** `Skills.md`
- **Naming:** PascalCase for folder, snake_case for file.
- **Dependencies:** Consumes the backlog JSON from Phase 03.

## ENGINEERING STANDARDS
- **Scalability:** Architecture must support 10 k RPS and 10 000 concurrent users.
- **Reusability:** Component definitions are expressed as Helm‑chart‑ready Kubernetes manifests.
- **Maintainability:** All diagrams stored as Mermaid files; version controlled.
- **Performance:** Target system‑wide latency < 100 ms; component sizing guidelines included.
- **Concurrency:** Document thread‑safe design patterns (stateless services, message queues).

## SECURITY RULES
- Threat modeling (STRIDE) must be performed; all components must enforce JWT authentication and RBAC.
- Data in‑transit encrypted via TLS 1.3; data at rest encrypted using KMS.
- No hard‑coded secrets; reference Vault secret paths.

## DATABASE STANDARDS
- Define database choice per component (PostgreSQL, Redis, Elasticsearch) and replication strategy.
- Indicate schema ownership and migration responsibilities.

## API CONTRACT STANDARDS
- **Input:** Backlog JSON (epics, features, user stories).
- **Output:** `Architecture` JSON containing `Components`, `DataFlow`, `TradeOffs` (see **Output Specification**).
- **Versioning:** `v1.0` immutable.

## FRONTEND STANDARDS
- UI layer must be decoupled via GraphQL/REST gateway; front‑end components referenced as separate services.

## DEVOPS STANDARDS
- Executed as CI step `phase-04-architecture-design` using Docker image `antigravity/sdlc-phase-04`.
- Stores artifacts under `artifacts/architecture/phase04.json` and `diagrams/` directory.

## OBSERVABILITY RULES
- Log component selection decisions, capacity estimates.
- Emit OpenTelemetry span `sdlc.phase04.architecture_design`.
- Metrics: estimated CPU/memory per service.

## TESTING REQUIREMENTS
- Unit tests for architecture validation script.
- Integration test that synthesises a minimal deployable manifest from the output JSON.
- Edge‑case test for missing feature definitions (should produce `UNKNOWN` fields).

## AI AGENT EXECUTION RULES
- AI agents may generate component skeletons and Mermaid diagrams from the backlog.
- Must not alter the original backlog JSON.
- All generated artifacts must include a `Generated‑By‑AI` comment header.

## REAL‑WORLD WORKFLOWS
1. **Ingestion** – Receive backlog JSON from Phase 03.
2. **Component mapping** – Align each epic/feature to a microservice boundary.
3. **Data‑flow design** – Create Mermaid diagram of event streams, API calls, and DB interactions.
4. **Trade‑off analysis** – Document latency vs. consistency, cost vs. scalability.
5. **Assumption handling** – Record explicit assumptions (e.g., 3‑zone AWS deployment) and derived assumptions.
6. **Traceability** – Link each component back to originating backlog items.
7. **Confidence assessment** – Based on completeness of backlog and known constraints.
8. **Output readiness** – Validate `Architecture` JSON conforms to schema required by Phase 05.
9. **Publish** – Store JSON and diagrams for downstream phases.

---
### Output Specification (Ready for Phase 05)
```json
{
  "Architecture": {
    "Components": [
      {
        "name": "<string|UNKNOWN>",
        "type": "service|database|cache|queue",
        "description": "<string|UNKNOWN>",
        "kubernetes": {"helmChart": "<string|UNKNOWN>", "replicas": "<int|UNKNOWN>"}
      }
    ],
    "DataFlow": "<mermaid_diagram_string|UNKNOWN>",
    "TradeOffs": ["<string|UNKNOWN>"]
  },
  "Assumptions": {"Explicit": [], "Derived": []},
  "Traceability": {"Components": {"source":"<path>","section":"<heading>"}},
  "ConfidenceLevel": "High|Medium|Low",
  "ConfidenceJustification": "<text>",
  "OutputReadiness": true,
  "Gaps": []
}
```
*Missing data → `UNKNOWN` and listed under `Gaps`.*
