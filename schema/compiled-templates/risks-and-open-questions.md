# risks-and-open-questions.md — Schema Template (Structural Contract)

Purpose: Known risks and unresolved questions.

## Format rules
- Each entry MUST start with a level-2 heading:
  `## <Risk or Question ID> — <Short Title>`
- Entries MAY represent either a Risk or an Open Question.
- Metadata fields SHOULD appear as a bullet list immediately after the heading.
- Sections SHOULD appear in the order shown below.
- If information is unknown, fields may be omitted, left empty, or set to `[unavailable]`.
- Closed items MUST remain in the file for historical traceability.

## Entry Template

## RSK-YYYY-MM-DD-### | QST-YYYY-MM-DD-### — <Short Title>

- **Type:** Risk | Open Question
- **Status:** Open | Mitigated | Closed | Escalated | [unavailable]
- **Identified date:** <YYYY-MM-DD | [unavailable]>
- **Owner:** <Name | Team | [unavailable]>
- **Impact level:** <High | Medium | Low | [unavailable]>
- **Likelihood:** <High | Medium | Low | [unavailable]>
- **Confidence:** <High | Medium | Low | [unavailable]>
- **Tags:** [tag] [tag] ...

### Description
<Clear description of the risk or the question. What could go wrong, or what is unknown?>

### Why it matters
<Explain potential impact to scope, schedule, quality, cost, safety, or decision-making.>

### Mitigation / Next steps
- <Mitigation action, experiment, or investigation>
- <Owner and/or timeline if known>

### Resolution (if closed)
<How the risk was mitigated, accepted, or the question answered. Use [unavailable] if still open.>

### Related decisions / changes
- **Decision:** <DEC-YYYY-MM-DD-### | [unavailable]>
- **Change:** <CHG-YYYY-MM-DD-### | [unavailable]>
- **Rejected approach:** <REJ-YYYY-MM-DD-### | [unavailable]>

### References
- `raw/<path-to-source-file>`
- `raw/<path-to-source-file>#<anchor-if-applicable>`
