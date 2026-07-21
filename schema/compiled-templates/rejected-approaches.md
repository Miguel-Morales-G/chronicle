# rejected-approaches.md — Schema Template (Structural Contract)

Purpose: Explicit record of considered and rejected options.

## Format rules
- Each rejected approach MUST start with a level-2 heading:
  `## <Approach ID> — <Short Title>`
- Metadata fields SHOULD appear as a bullet list immediately after the heading.
- Sections SHOULD appear in the order shown below.
- If information is unknown, fields may be omitted, left empty, or set to `[unavailable]`.

## Rejected Approach Entry Template

## REJ-YYYY-MM-DD-### — <Short Title>

- **Status:** Rejected | [unavailable]
- **Rejected date:** <YYYY-MM-DD | [unavailable]>
- **Owner:** <Name | Team | [unavailable]>
- **Confidence:** <High | Medium | Low | [unavailable]>
- **Tags:** [tag] [tag] ...

### Context
<What problem were we trying to solve? Why was this approach considered?>

### Proposal (What it was)
<Describe the approach that was considered. What would it have looked like?>

### Why rejected
- <Reason 1>
- <Reason 2>

### Tradeoffs / Risks identified
- <Tradeoff or risk 1>
- <Tradeoff or risk 2>

### What we chose instead
<If known, link to the decision or approach that replaced this. Otherwise [unavailable].>
- **Decision link:** <DEC-YYYY-MM-DD-### | [unavailable]>

### References
- `raw/<path-to-source-file>`
- `raw/<path-to-source-file>#<anchor-if-applicable>`
