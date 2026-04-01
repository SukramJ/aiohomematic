"""
MkDocs hook: hide language switcher on pages without a translation.

The mkdocs-static-i18n plugin with reconfigure_material sets the Material
theme's language selector on every page, even those without a .de.md file.
This hook removes the selector HTML from pages that have no translation.
"""

from __future__ import annotations

import re
from pathlib import Path

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
    """Strip language selector from pages without a translation."""
    src_path = page.file.src_path

    # DE pages always keep the switcher (to switch back to EN)
    if src_path.endswith(".de.md"):
        return output

    de_src = src_path.removesuffix(".md") + ".de.md"
    de_sources = _get_de_sources(config.docs_dir)

    if de_src not in de_sources:
        # No translation — remove language selector and hreflang links
        output = _LANG_SELECTOR_RE.sub("", output)
        output = _HREFLANG_RE.sub("", output)

    return output
