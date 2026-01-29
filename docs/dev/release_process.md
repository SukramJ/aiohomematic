# Release Process

This guide documents the release workflow for aiohomematic, including version numbering, changelog format, and tag creation.

## Version Numbering

aiohomematic uses a **calendar-based versioning** scheme:

```
YYYY.MM.NN
```

| Component | Description                 | Example                       |
| --------- | --------------------------- | ----------------------------- |
| `YYYY`    | Year                        | 2025                          |
| `MM`      | Month                       | 12 (December)                 |
| `NN`      | Running number within month | 41 (41st release in December) |

**Example**: `2025.12.41` = 41st release in December 2025

## Version Locations

The version must be synchronized in two places:

| File                    | Location              |
| ----------------------- | --------------------- |
| `aiohomematic/const.py` | `VERSION` constant    |
| `changelog.md`          | Latest version header |

## Release Workflow

### 1. Check Existing Tags

**Before modifying the changelog**, check existing tags:

```bash
git tag --list '2025.12.*' | sort -V | tail -3
```

**Important**: Tagged versions are **immutable**. Never modify already-tagged versions.

### 2. Determine Next Version

Based on the latest tag, increment the running number:

- Latest tag: `2025.12.42` → Next version: `2025.12.43`
- New month starts at `.01`: `2026.01.01`

### 3. Update Changelog

Add a new version entry at the **top** of `changelog.md`:

```markdown
# Version 2025.12.43 (2025-12-21)

## What's Changed

### New Features

- Brief description of new features

### Improvements

- Brief description of improvements

### Bug Fixes

- Brief description of bug fixes

### Breaking Changes

- Any breaking changes (with migration notes)

---

# Version 2025.12.42 (2025-12-20) ← Previous version (DO NOT MODIFY)
```

### 4. Update VERSION Constant

In `aiohomematic/const.py`:

```python
VERSION: Final = "2025.12.43"
```

### 5. Verify Sync

```bash
# Check both are in sync
head -1 changelog.md
grep "^VERSION" aiohomematic/const.py
```

### 6. Commit and Tag

```bash
# Commit version changes
git add changelog.md aiohomematic/const.py
git commit -m "Release version 2025.12.43"

# Create annotated tag
git tag -a "2025.12.43" -m "Release 2025.12.43"

# Push with tags
git push origin devel --tags
```

## Changelog Format

### Section Headers

Use these standard section headers:

| Section              | Contents                          |
| -------------------- | --------------------------------- |
| **New Features**     | New functionality                 |
| **Improvements**     | Enhancements to existing features |
| **Bug Fixes**        | Bug corrections                   |
| **Breaking Changes** | API changes requiring migration   |
| **Documentation**    | Documentation updates             |
| **Internal**         | Refactoring, dependencies, CI/CD  |

### Entry Format

Each entry should be concise and action-oriented:

```markdown
### New Features

- Add support for HmIP-NEW-DEVICE thermostat (#123)
- Add `get_schedule_simple_profile` action for climate entities

### Bug Fixes

- Fix connection timeout handling for JSON-RPC interfaces (#456)
```

### Linking Issues/PRs

Reference GitHub issues and PRs:

```markdown
- Fix connection recovery loop (#123)
- Add CUxD troubleshooting guide (PR #456)
```

## Pre-Release Checklist

Before creating a release:

- [ ] All tests pass: `pytest tests/`
- [ ] All linters pass: `pre-commit run --all-files`
- [ ] No mypy errors
- [ ] Changelog entry is complete
- [ ] VERSION constant is updated
- [ ] Documentation is updated (if applicable)
- [ ] Migration guide exists (for breaking changes)

## Hotfix Releases

For urgent fixes to the current release:

1. Create from the latest tag:

   ```bash
   git checkout -b hotfix/issue-description 2025.12.43
   ```

2. Apply fix and increment version: `2025.12.43` → `2025.12.44`

3. Follow normal release process

## Release Notes

For significant releases, create release notes on GitHub:

1. Go to **Releases** → **Draft a new release**
2. Select the tag
3. Title: `Version YYYY.MM.NN`
4. Body: Copy relevant changelog sections
5. Attach any relevant assets

## Automation

GitHub Actions automatically:

- Runs tests on PR creation
- Validates version format
- Publishes to PyPI on tag push

## Common Mistakes

| Mistake                  | Solution                          |
| ------------------------ | --------------------------------- |
| Modifying tagged version | Create new version instead        |
| VERSION out of sync      | Always update both files together |
| Missing changelog entry  | Add entry before tagging          |
| Wrong version format     | Use `YYYY.MM.NN` exactly          |

## See Also

- [Contributing Guide](../contributing.md)
- [Testing Guidelines](testing_with_events.md)
