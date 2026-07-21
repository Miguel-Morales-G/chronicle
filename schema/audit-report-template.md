# Chronicle Audit Report — YYYY-MM-DD-###

- **Date:** YYYY-MM-DD
- **Compiled dir:** compiled/
- **Files audited:** decision-log.md (N entries), glossary.md (M terms)
- **Run trigger:** every-N | end-of-run | manual
- **Overall status:** OK | WARN | FAIL

---

## Summary

| Severity | Count |
|----------|-------|
| Errors   | N     |
| Warnings | N     |
| Notices  | N     |

---

## Findings

<!-- One block per finding. Severity label in heading: ERROR | WARN | NOTICE -->

### [ERROR | WARN | NOTICE] <Check Title>

- **Check:** `<check-name>`
- **Location:** `<compiled/file.md>` — `<context (DEC ID, term name, etc.)>`
- **Detail:** <Explanation of the issue>
- **Recommendation:** <Suggested remediation>

---

## Metrics

- Decision entries: N
- Glossary terms: N
- Deterministic checks executed: 5
- LLM calls: 1 (tokens: prompt=N, completion=N)

---

## Report Meta

- Auditor version: v1
- Generated: YYYY-MM-DDTHH:MM:SSZ

---

<!--
SEVERITY LEVELS
  ERROR   — structurally broken (duplicate IDs, malformed IDs)
  WARN    — schema-required field missing (### References, **Introduced in:**)
  NOTICE  — advisory finding from LLM semantic check (near-duplicate terms)

CHECK NAMES (V1)
  duplicate-dec-id              — same DEC-YYYY-MM-DD-### appears more than once
  malformed-dec-id              — DEC-like token does not match DEC-YYYY-MM-DD-### format
  decision-missing-references   — decision entry lacks a ### References section
  glossary-missing-introduced-in — glossary entry lacks **Introduced in:** bullet
  duplicate-glossary-heading    — two glossary entries share the same term (case-insensitive)
  glossary-semantic-duplicates  — LLM detected near-duplicate terms (NOTICE only)
-->
