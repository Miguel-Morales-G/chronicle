# Cross‑File Consistency Rules (System Invariants)

This file defines **system‑level consistency rules** that apply across
multiple canonical compiled files.

These rules express **expectations**, not rigid automation requirements.
They are evaluated **holistically** by quality control agents and may
require **human judgment** to interpret and resolve.

Normative keywords such as **MUST**, **SHOULD**, and **MAY** are used
intentionally to signal strength of expectation.

---

## Decision propagation

- Decisions recorded in `compiled/decision-log.md` that affect
  project direction, scope, or priorities **MUST** be reflected in
  `compiled/current-status.md` when relevant.

- If an approach is recorded as rejected and later used, this **MUST**
  be captured as a new decision that explicitly supersedes the rejection.

- Any decision that materially reduces, resolves, or accepts a known
  risk **SHOULD** reference the corresponding `RSK` entry.

---

## Rejected approaches

- Approaches recorded in `compiled/rejected-approaches.md` **MUST NOT**
  later appear as accepted decisions unless explicitly superseded
  by a new decision entry in `compiled/decision-log.md`.

---

## Change traceability

- Major changes in project direction, scope, or assumptions **MUST**
  be traceable through:

  ```
  compiled/decision-log.md → compiled/change-history.md
  ```

- Any change that alters project direction, scope, or architecture
  **SHOULD** reference one of the following:
  - a decision‑log entry
  - a rejected‑approaches entry

  If no such entry exists, the change **SHOULD** explicitly state why.

---

## Contradictions

- Conflicting statements across canonical compiled files are considered
  **quality issues** and **MUST** be flagged during pull‑request review
  or system‑level audits.

- Apparent contradictions do not imply fault by any single document,
  but indicate a need for reconciliation.

---

## Resolution and closure (recommended)

- When a risk or open question is resolved, mitigated, or accepted,
  that resolution **SHOULD** be traceable via a decision or change
  entry.

- Closed risks and questions **MAY** remain in the record, but their
  resolved status should be explicit and non‑ambiguous.

---

_End of cross‑file consistency rules._
