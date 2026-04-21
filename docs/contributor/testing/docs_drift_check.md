# Documentation drift checks

Two complementary checks help keep `docs/` in sync with the codebase.

## 1. `script/check_docs_references.py` (wired into prek)

Runs on every commit that touches `docs/*.md` or `aiohomematic/central/events/*.py` via the
`check-docs-references` prek hook. What it verifies:

1. **Broken relative links** — every `[text](path.md)` / `[text](path.md#anchor)` link in
   `docs/` must resolve to an existing file. Code fences are stripped before matching so
   Python type annotations like `Callable[P, R]` do not register as links.
2. **Stale identifiers** — known-renamed classes and paths (e.g. `XmlRpcProxy` →
   `AioXmlRpcProxy`, `aiohomematic/caches/` → `aiohomematic/store/`) must not appear in
   prose. Extend the `STALE_PATTERNS` table at the top of the script when the codebase is
   refactored.
3. **Event reference coverage** — every public `Event` subclass exported from
   `aiohomematic/central/events/__init__.py` (`__all__`) must appear at least once in
   `docs/architecture/events/event_reference.md`. Adding a new event without updating the
   reference fails the check.

### Running manually

```bash
python script/check_docs_references.py
```

Exit code is `0` when clean, `1` when drift is detected.

### When the check fires

- **Broken link**: update the link target, or delete the link if the target was removed
  intentionally.
- **Stale identifier**: update the prose. Extend `STALE_PATTERNS` only if the rename must be
  enforced project-wide.
- **Missing event class**: add at least a Quick Reference row and a per-event section to
  `docs/architecture/events/event_reference.md`. Follow the existing format (field table,
  `**Key:** …`, and a link to the relevant ADR where applicable).

## 2. `pytest-markdown-docs` (proposed, not yet enforced)

The Quick Start and Getting Started pages contain executable Python snippets. A natural
next step is to run them through [`pytest-markdown-docs`](https://pypi.org/project/pytest-markdown-docs/)
so that broken snippets fail CI like any other test. Suggested minimal wiring:

```toml
# pyproject.toml (excerpt — not yet committed)
[tool.pytest.ini_options]
markdown-docs-syntax = "superfences"
addopts = "--markdown-docs"
```

```bash
pip install pytest-markdown-docs
pytest --markdown-docs docs/quickstart.md docs/getting_started.md
```

This is **not** currently wired into CI. Tracking in the contributor guide so we can enable
it once the snippets are fully stable.

## 3. Version stamps in docs (policy)

Manual `**Last Updated**: YYYY-MM-DD` footers are **not** maintained in the documentation.
They drift silently after the next edit. Use git when you need the real mtime:

```bash
git log -1 --format=%cs -- docs/architecture.md
```
