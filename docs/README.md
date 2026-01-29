# aiohomematic Documentation

This directory contains the documentation for aiohomematic, built with [MkDocs](https://www.mkdocs.org/) and the [Material theme](https://squidfunk.github.io/mkdocs-material/).

## Online Documentation

The documentation is automatically deployed to GitHub Pages:

**https://sukramj.github.io/aiohomematic/**

## Building Locally

### Install Dependencies

```bash
pip install -r requirements_docs.txt
```

### Serve Documentation (with live reload)

```bash
mkdocs serve
```

Open http://127.0.0.1:8000 in your browser.

### Build Static Site

```bash
mkdocs build
```

The built documentation will be in `site/`.

## Documentation Structure

```
docs/
├── index.md                    # Landing page
├── getting_started.md          # Installation and first steps
├── glossary.md                 # Terminology reference
├── architecture.md             # System design overview
├── data_flow.md                # Data flow diagrams
├── sequence_diagrams.md        # Sequence diagrams
├── event_bus.md                # Event system
├── event_reference.md          # Event types reference
├── extension_points.md         # How to extend the library
├── consumer_api.md             # API for integrations
├── homeassistant_lifecycle.md  # HA integration guide
├── adr/                        # Architecture Decision Records
├── migrations/                 # Migration guides
├── user/                       # User guides
│   ├── community_templates.md
│   └── devices/                # Device-specific guides
└── dev/                        # Developer documentation
    └── coverage.md
```

## Contributing to Documentation

1. Edit or create Markdown files in the `docs/` directory
2. Update `mkdocs.yml` navigation if adding new pages
3. Test locally with `mkdocs serve`
4. Submit a pull request

Documentation is automatically deployed when changes are pushed to `devel` or `master`.
