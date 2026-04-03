"""
MkDocs hook: hide language switcher on pages without a real translation.

With ``fallback_to_default: true`` the i18n plugin builds every page under
``/de/`` even when no ``.de.md`` file exists (using the English source as
fallback).  The Material theme then shows a language selector on *all* pages.

This hook removes the selector on pages that have no actual translation,
both on the English version and on the German fallback version.
"""

from __future__ import annotations

from pathlib import Path
import re

# Cache: set of .de.md source files that exist in docs/
_de_sources: set[str] | None = None


def _get_de_sources(docs_dir: str) -> set[str]:
    """Scan docs dir for .de.md files (cached)."""
    global _de_sources  # noqa: PLW0603
    if _de_sources is None:
        docs_path = Path(docs_dir)
        _de_sources = {
            str(p.relative_to(docs_path))
            for p in docs_path.rglob("*.de.md")
        }
    return _de_sources


def _has_translation(src_path: str, docs_dir: str) -> bool:
    """Check whether a real .de.md translation exists for this page."""
    de_sources = _get_de_sources(docs_dir)

    if src_path.endswith(".de.md"):
        # This IS a .de.md page — translation exists by definition
        return True

    # English page: check if a .de.md sibling exists
    return src_path.removesuffix(".md") + ".de.md" in de_sources


# Pattern: Material theme language selector (minified HTML, attributes without quotes)
_LANG_SELECTOR_RE = re.compile(
    r'<div class=md-header__option>\s*<div class=md-select>.*?</div>\s*</div>\s*</div>',
    re.DOTALL,
)

# Pattern: hreflang alternate links for non-English languages
_HREFLANG_RE = re.compile(
    r'<link rel=alternate href=[^ >]+ hreflang=(?!en)[a-z]{2}>'
)


def on_post_page(output: str, page, config) -> str:
    """Strip language selector from pages without a real translation."""
    src_path = page.file.src_path

    if not _has_translation(src_path, config.docs_dir):
        output = _LANG_SELECTOR_RE.sub("", output)
        output = _HREFLANG_RE.sub("", output)

    return output
