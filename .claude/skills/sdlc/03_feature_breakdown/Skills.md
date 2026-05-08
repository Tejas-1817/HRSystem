---
logo: https://internal.company.com/assets/logo.svg
primary_color: "#1A73E8"
secondary_color: "#34A853"
---

# Skills.md – SDLC Phase 03: Feature Breakdown

## PURPOSE
Define the role, responsibilities, and deliverables for the **Feature Breakdown** phase. Transform the PRD into a structured backlog of epics, features, user stories, and acceptance criteria.

## MODULE ARCHITECTURE
- **Folder:** `sdlc/03_feature_breakdown/`
- **File:** `Skills.md`
- **Naming:** PascalCase for the folder, snake_case for files.
- **Dependencies:** Consumes the PRD JSON produced by Phase 02.

## ENGINEERING STANDARDS
- **Scalability:** Able to handle up to 5 000 backlog items with < 2 s processing time.
- **Reusability:** Uses a configurable markdown‑to‑JSON transformer that can be reused for any product.
- **Maintainability:** All mapping rules are externalized in `mapping.yaml`.
- **Performance:** Linear O(N) conversion; memory ≤ 100 MB.
- **Concurrency:** Single‑threaded deterministic output to preserve ordering.

## SECURITY RULES
- No secret handling; read‑only consumption of PRD data.
- Ensure no PII is unintentionally exposed when extracting stakeholder names.

## DATABASE STANDARDS
- N/A – this phase generates JSON artifacts, not persisting to a DB.

## API CONTRACT STANDARDS
- **Input:** PRD JSON (see Phase 02 output spec).
- **Output:** Structured backlog JSON (see **Output Specification**).
- **Versioning:** `v1.0` immutable.

## FRONTEND STANDARDS
- N/A – backend generation only.

## DEVOPS STANDARDS
- Executed as CI step `phase-03-feature-breakdown` using Docker image `antigravity/sdlc-phase-03`.
- Stores artifact under `artifacts/backlog/phase03.json`.

## OBSERVABILITY RULES
- Log number of epics, features, user stories created.
- Emit OpenTelemetry span `sdlc.phase03.feature_breakdown`.

## TESTING REQUIREMENTS
- Unit tests for each mapping rule.
- Integration test feeding a sample PRD and asserting correct JSON hierarchy.
- Edge‑case test for missing PRD fields (should produce `UNKNOWN` and list gaps).

## AI AGENT EXECUTION RULES
- AI agents may generate epics, features, and user stories using the template, but must not alter the original PRD.
- All generated items must be traceable to a PRD source element; otherwise mark `UNKNOWN`.
- Tag commits with `AI‑Generated‑Backlog`.

## REAL‑WORLD WORKFLOWS
1. **Input ingestion** – Receive PRD JSON from Phase 02.
2. **Mapping** – Apply deterministic rules to translate PRD sections (Vision, Scope, Requirements) into epics and features.
3. **User Story creation** – Break each feature into granular user stories with clear `Given/When/Then` format.
4. **Acceptance criteria** – Auto‑populate from PRD success metrics where possible; otherwise mark `UNKNOWN`.
5. **Assumption handling** – Record explicit assumptions from PRD and derived assumptions made during decomposition.
6. **Traceability** – Map each backlog item back to the originating PRD field and source file.
7. **Confidence assessment** – Assign confidence based on completeness of PRD data.
8. **Output readiness** – Verify that the generated JSON complies with the schema expected by Phase 04.
9. **Publish** – Store JSON artifact for downstream phases.

---
### Output Specification (Ready for Phase 04)
```json
{
  "Backlog": {
    "Epics": [
      {
        "id": "E-001",
        "title": "<string|UNKNOWN>",
        "description": "<string|UNKNOWN>",
        "features": [
          {
            "id": "F-001",
            "title": "<string|UNKNOWN>",
            "description": "<string|UNKNOWN>",
            "userStories": [
              {
                "id": "US-001",
                "title": "<string|UNKNOWN>",
                "description": "<string|UNKNOWN>",
                "acceptanceCriteria": ["<string|UNKNOWN>"],
                "traceability": {"source":"<path>","section":"<heading>"}
              }
            ]
          }
        ]
      }
    ]
  },
  "Assumptions": {"Explicit": [], "Derived": []},
  "Traceability": {"Epics": {"source":"<path>","section":"<heading>"}},
  "ConfidenceLevel": "High|Medium|Low",
  "ConfidenceJustification": "<text>",
  "OutputReadiness": true,
  "Gaps": []
}
```
*All fields must be populated; missing information is represented as `UNKNOWN` and recorded in `Gaps`.***
