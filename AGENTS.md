# Repository Guidelines

## Project Structure & Module Organization

- `aiohomematic/` hosts the async library (`central/`, `client/`, `model/`, `store/`) plus assets in `rega_scripts/` and `translations/`.
- `aiohomematic_test_support/` supplies fixtures, playback data, and factories; prefer these over bespoke mocks.
- `tests/` contains the pytest suite with `helpers/` and `fixtures/`; keep new tests adjacent to related code.
- `docs/` collects architecture, migration, and naming references; automation scripts live in `script/` for pre-commit use.

## Build, Test, and Development Commands

- `python -m pip install -r requirements.txt -r requirements_test.txt` installs runtime and tooling dependencies.
- `pre-commit run --all-files` mirrors CI hooks (`sort-class-members`, `check-i18n`, `ruff`, `mypy`, `pylint`, `codespell`, `bandit`, `yamllint`).
- `ruff format` then `ruff check --fix` applies the required formatting, import order, and alias rules.
- `mypy aiohomematic aiohomematic_test_support` runs strict type checks; justify any `# type: ignore[code]`.
- `pytest tests/` runs the suite; use `./cov.sh` for HTML coverage and `pytest -k pattern -vv` for focused runs.
- `pylint -j 0 aiohomematic` covers the remaining lint gate; reuse the project virtualenv or `script/run-in-env.sh`.

## Coding Style & Naming Conventions

- Start every Python module with `from __future__ import annotations`, use 4-space indentation, and maintain curated `__all__`.
- Let `ruff` manage import order and aliases; do not hand-sort or introduce new shortcuts.
- Public surfaces require docstrings consistent with `docs/docstring_standards.md`.
- Reuse helpers for device/channel naming (`docs/naming.md`) and shared enums or dataclasses from `aiohomematic.const`.
- Keep async APIs cancellable and prefer keyword-only signatures for multi-parameter functions.

## Testing Guidelines

- Use pytest with `@pytest.mark.asyncio`; lean on factories in `aiohomematic_test_support.factory` and fixtures from `tests/conftest.py`.
- Place new playback data in `aiohomematic_test_support/data` and document schema updates alongside the change.
- Sustain ≥90 % coverage on core logic and ≥85 % overall; inspect `htmlcov/index.html` after `./cov.sh`.
- Name new test modules `test_<feature>.py` and park shared utilities in `tests/helpers/`.

## Commit & Pull Request Guidelines

- Branch from `devel` using `feature/<slug>` or `fix/<slug>`; AI sessions use `codex/codex-md-<session-id>`.
- Adopt the conventional commit format `type(scope): subject`; supported types are `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- Describe intent in the body and reference issues when applicable (e.g., `Closes #123`).
- Target PRs at `devel`, include a brief summary plus test/type results, and supply evidence for behavioral changes.
- Update `changelog.md` for user-visible impact and call out configuration or migration notes in the PR description.
