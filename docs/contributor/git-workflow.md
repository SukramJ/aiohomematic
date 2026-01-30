# Git Workflow

This guide covers the git workflow for contributing to aiohomematic.

## Branch Structure

| Branch      | Purpose                 | Protection |
| ----------- | ----------------------- | ---------- |
| `master`    | Stable releases         | Protected  |
| `devel`     | Development integration | Protected  |
| `feature/*` | New features            | -          |
| `fix/*`     | Bug fixes               | -          |

## Workflow Overview

```
1. Fork repository
2. Create feature branch from devel
3. Make changes with tests
4. Run pre-commit hooks
5. Commit with descriptive message
6. Push to your fork
7. Create Pull Request to devel
```

## Creating a Feature Branch

```bash
# Ensure you're on devel and up to date
git checkout devel
git pull origin devel

# Create feature branch
git checkout -b feature/my-feature

# Or for bug fixes
git checkout -b fix/issue-123
```

## Commit Messages

Follow conventional commit format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types

| Type       | Description             |
| ---------- | ----------------------- |
| `feat`     | New feature             |
| `fix`      | Bug fix                 |
| `docs`     | Documentation only      |
| `style`    | Code style (formatting) |
| `refactor` | Code refactoring        |
| `test`     | Adding tests            |
| `chore`    | Maintenance tasks       |

### Examples

```bash
# Feature
git commit -m "feat(model): add support for HmIP-NEW-DEVICE

Implements custom entity class for the new device with support
for parameter ABC and DEF.

Closes #123"

# Bug fix
git commit -m "fix(client): handle connection timeout gracefully

Added retry logic with exponential backoff for RPC calls."

# Documentation
git commit -m "docs(readme): update installation instructions"
```

## Before Committing

Always run checks before committing:

```bash
# Run all pre-commit hooks
pre-commit run --all-files

# Run tests
pytest tests/
```

## Creating a Pull Request

### 1. Push Your Branch

```bash
git push -u origin feature/my-feature
```

### 2. Create PR on GitHub

- **Target branch**: `devel`
- **Title**: Clear, concise description
- **Description**: Explain what and why

### PR Description Template

```markdown
## Summary

Brief description of changes.

## Changes

- List of changes made
- Another change

## Testing

How the changes were tested.

## Related Issues

Fixes #123
```

### 3. Wait for CI

All checks must pass:

- Tests (pytest)
- Linting (ruff, pylint)
- Type checking (mypy)
- Security (bandit)

### 4. Address Review Comments

```bash
# Make changes based on review
git add .
git commit -m "fix: address review comments"
git push
```

## Git Safety Rules

### Never Do

- Push directly to `master` or `devel`
- Force push to shared branches
- Use `git reset --hard` on shared branches
- Skip hooks with `--no-verify` without good reason
- Commit secrets or credentials

### Always Do

- Create feature branches for changes
- Run hooks before committing
- Write descriptive commit messages
- Keep commits focused and atomic
- Update documentation with code changes

## Common Scenarios

### Sync with Upstream

```bash
git fetch origin
git checkout devel
git merge origin/devel
git checkout feature/my-feature
git rebase devel
```

### Fix Last Commit Message

```bash
git commit --amend -m "new message"
```

### Squash Commits Before PR

```bash
# Squash last 3 commits interactively
git rebase -i HEAD~3
```

### Undo Last Commit (Keep Changes)

```bash
git reset --soft HEAD~1
```

### Stash Changes

```bash
git stash
# ... do other work ...
git stash pop
```

## Release Process

See [Release Process](release_process.md) for maintainer-specific release workflow.

## Related Documentation

- [Development Environment](dev-environment.md) - Setup guide
- [Contributing](contributing.md) - Contribution guidelines
- [Coding Standards](coding/naming.md) - Code style
