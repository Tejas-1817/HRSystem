---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – SDLC Phase 05: Architecture Review

## PURPOSE
Define the role, responsibilities, and deliverables for the **Architecture Review** phase. Evaluate the architecture produced in Phase 04 for risks, scalability, security, and reliability concerns, and provide mitigation recommendations.

## MODULE ARCHITECTURE
- **Folder:** `sdlc/05_architecture_review/`
- **File:** `Skills.md`
- **Naming:** PascalCase for folder, snake_case for file.
- **Dependencies:** Consumes the `Architecture` JSON output from Phase 04.

## ENGINEERING STANDARDS
- **Scalability:** Review must consider target 10 k RPS and 10 000 concurrent users.
- **Reusability:** Checklist and risk‑matrix are externalized in `review_checklist.yaml` for reuse across projects.
- **Maintainability:** Findings are stored as structured JSON for traceability.
- **Performance:** Review automation runs in < 30 s for typical architecture size.
- **Concurrency:** Single‑threaded deterministic analysis.

## SECURITY RULES
- Perform STRIDE threat modeling on each component.
- Verify that all services enforce JWT authentication and RBAC.
- Ensure TLS 1.3 everywhere, and that secret handling follows Vault paths.
- Flag any hard‑coded credentials or insecure defaults.

## DATABASE STANDARDS
- Validate that database replication, backup, and encryption meet enterprise policy.
- Ensure schema versioning strategy is defined.

## API CONTRACT STANDARDS
- **Input:** Architecture JSON (components, data flow, trade‑offs).
- **Output:** Review JSON containing `Risks`, `ScalabilityConcerns`, `SecurityConcerns`, `ReliabilityConcerns` (see **Output Specification**).
- **Versioning:** `v1.0` immutable.

## FRONTEND STANDARDS
- Ensure UI‑service separation and that front‑end contracts are versioned.

## DEVOPS STANDARDS
- Executed as CI step `phase-05-architecture-review` using Docker image `antigravity/sdlc-phase-05`.
- Stores artifact under `artifacts/review/phase05.json`.

## OBSERVABILITY RULES
- Log each identified risk with severity (Critical/High/Medium/Low).
- Emit OpenTelemetry span `sdlc.phase05.architecture_review`.
- Metrics: number of risks per category.

## TESTING REQUIREMENTS
- Unit tests for each checklist rule implementation.
- Integration test that feeds a sample Architecture JSON and verifies correct risk classification.
- Edge‑case test for missing component fields (should produce `UNKNOWN` entries).

## AI AGENT EXECUTION RULES
- AI agents may run the automated checklist and suggest mitigations, but must not modify the original Architecture JSON.
- All generated findings must include `Generated‑By‑AI` tag.
- Agents must not introduce new components; only comment on existing ones.

## REAL‑WORLD WORKFLOWS
1. **Ingestion** – Receive Architecture JSON from Phase 04.
2. **Checklist execution** – Apply security, scalability, reliability, and performance rules.
3. **Risk identification** – Populate `Risks` array with description, severity, impacted components, and mitigation suggestion.
4. **Assumption handling** – Record explicit assumptions (e.g., cloud region) and derived assumptions.
5. **Traceability** – Link each risk to the originating component definition.
6. **Confidence assessment** – Based on completeness of Architecture JSON, set confidence level.
7. **Output readiness** – Validate that Review JSON matches schema required by Phase 06.
8. **Publish** – Store JSON artifact for downstream phases.

---
### Output Specification (Ready for Phase 06)
```json
{
  "Review": {
    "Risks": [
      {
        "id": "R-001",
        "description": "<string|UNKNOWN>",
        "severity": "Critical|High|Medium|Low",
        "component": "<string|UNKNOWN>",
        "mitigation": "<string|UNKNOWN>"
      }
    ],
    "ScalabilityConcerns": ["<string|UNKNOWN>"],
    "SecurityConcerns": ["<string|UNKNOWN>"],
    "ReliabilityConcerns": ["<string|UNKNOWN>"]
  },
  "Assumptions": {"Explicit": [], "Derived": []},
  "Traceability": {"Risks": {"source":"<path>","section":"<heading>"}},
  "ConfidenceLevel": "High|Medium|Low",
  "ConfidenceJustification": "<text>",
  "OutputReadiness": true,
  "Gaps": []
}
```
*Missing data → `UNKNOWN` and listed under `Gaps`.*
