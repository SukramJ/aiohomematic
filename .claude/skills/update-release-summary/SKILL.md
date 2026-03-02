---
name: update-release-summary
description: Update the release_summary.md file with a user-focused high-level summary of recent changes. Use when the user says "update release summary".
---

# Update Release Summary

The file `release_summary.md` provides a **user-focused, high-level summary** of changes across multiple versions. This is different from the detailed `changelog.md` - it consolidates many changes into meaningful user-facing improvements.

## Format

```markdown
# Version 2025.11.07 - 2025.12.43

## What's Changed

- **Feature Category**: Brief user-focused description
- **Another Category**: What users can now do differently
```

## Release States

| State  | Format                            | Meaning                                           |
| ------ | --------------------------------- | ------------------------------------------------- |
| Open   | `Version 2025.11.07 -`            | Collecting changes from 2025.11.07 onwards        |
| Closed | `Version 2025.11.07 - 2025.12.43` | Summary of versions 2025.11.07 through 2025.12.43 |

## Procedure

### 1. Read Current State

```bash
head -1 release_summary.md
git tag --list '2025.12.*' | sort -V | tail -1
```

### 2. If Release is Closed (has end version)

- Create new open release starting from the next version
- Example: `Version 2025.12.43 - 2025.12.50` -> add `Version 2025.12.50 -`

### 3. Analyze Git Commits (NOT the changelog)

```bash
# Get all commits in the date range
git log --oneline --since="2025-11-05" --until="2025-12-23" | head -100
```

- **IMPORTANT**: Base the summary on actual git commits, not changelog.md
- The changelog may be incomplete or inaccurate - git commits are the source of truth
- Look for PR titles and commit messages to understand what changed
- Group related commits into user-facing categories

### 4. Write the Summary

- Summarize from **user perspective** (not developer perspective)
- Group related changes into categories
- Consolidate and update existing points if they evolved
- Keep descriptions brief and action-oriented

### 5. Writing Style

- Focus on what users can **do** or **experience** differently
- Avoid implementation details (no class names, method names, etc.)
- Combine multiple related commits into one summary point
- Use categories like: New Features, Improvements, Bug Fixes, Breaking Changes

## Example Transformation

**Git commits** (developer-focused):

```
b4240776 Introduce `DpActionSelect` data point type (#2611)
74453f5f Make ACOUSTIC_ALARM_SELECTION and OPTICAL_ALARM_SELECTION visible (#2613)
5277bb5b Add tests for DpSelectAction and CustomDpIpSiren (#2614)
```

**Release summary** (user-focused):

```
### Siren Control

- **Visible Alarm Settings**: Acoustic and optical alarm selection now available as controllable entities
- **Flexible Turn-On**: Siren activation uses entity values as defaults when service parameters omitted
```
