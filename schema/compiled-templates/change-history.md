# change-history.md — Schema Template (Structural Contract)

Purpose: Timeline of meaningful project changes.

## Format rules
- Each change entry MUST start with a level-2 heading:
  `## CHG-YYYY-MM-DD-### — <Short Title>`
- Entries MUST be ordered chronologically (oldest → newest).
- Metadata fields SHOULD appear as a bullet list immediately after the heading.
- Sections SHOULD appear in the order shown below.
- If information is unknown, fields may be omitted, left empty, or set to `[unavailable]`.

## Change Entry Template

## CHG-YYYY-MM-DD-### — <Short Title>

- **Change date:** <YYYY-MM-DD>
- **Change type:** <Scope | Process | Architecture | Governance | Documentation | Other | [unavailable]>
- **Owner:** <Name | Team | [unavailable]>
- **Impact level:** <High | Medium | Low | [unavailable]>
- **Tags:** [tag] [tag] ...

### What changed
<Concise description of what changed. Focus on observable differences from the prior state.>

### Why it changed
<Trigger or rationale for the change. This may reference new information, decisions, risks, or external constraints.>

### Affected artifacts
<List canonical files, directories, or concepts impacted by this change.>
- `compiled
