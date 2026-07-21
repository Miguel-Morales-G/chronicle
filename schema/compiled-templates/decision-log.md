# decision-log.md — Schema Template (Structural Contract)

Purpose: Chronological log of decisions, including rationale and consequences.

## Format rules
- Each decision entry MUST start with a level-2 heading:
  `## <Decision ID> — <Short Title>`
- Within an entry, metadata fields SHOULD appear as a bullet list immediately after the heading.
- Sections SHOULD appear in the order shown below.
- If information is unknown, fields may be omitted, left empty, or set to `[unavailable]`.

## Decision Entry Template

## DEC-YYYY-MM-DD-### — <Short Title>

- **Status:** <Accepted | Rejected | Proposed | Superseded | [unavailable]>
- **Superseded by:** <DEC-YYYY-MM-DD-### | [unavailable]>
- **Decision date:** <YYYY-MM-DD | [unavailable]>
- **Owner:** <Name | Team | [unavailable]>
- **Confidence:** <High | Medium | Low | [unavailable]>
- **Tags:** [tag] [tag] ...

### Context
<Why was this decision needed? What problem or situation triggered it?>

### Decision
<What was decided?>

### Rationale
- <Reason 1>
- <Reason 2>

### Alternatives considered
- <Alternative 1> — <why not>
- <Alternative 2> — <why not>

### Consequences / Impact
- <Consequence 1>
- <Consequence 2>

### References
- `raw/<path-to-source-file>`
- `raw/<path-to-source-file>#<anchor-if-applicable>`
