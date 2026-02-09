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
├── architecture.md             # System design overview
│
├── user/                       # User documentation
│   ├── homeassistant_integration.md  # Main integration guide
│   ├── device_support.md       # Device support overview
│   ├── features/               # Feature guides
│   │   ├── homeassistant_actions.md
│   │   ├── week_profile.md
│   │   └── calculated_climate_sensors.md
│   ├── troubleshooting/        # Troubleshooting guides
│   │   ├── homeassistant_troubleshooting.md
│   │   └── troubleshooting_flowchart.md
│   ├── advanced/               # Advanced topics
│   │   ├── cuxd_ccu_jack.md
│   │   ├── optional_settings.md
│   │   └── unignore.md
│   └── devices/                # Device-specific guides
│
├── developer/                  # Library consumer documentation
│   ├── consumer_api.md
│   ├── extension_points.md
│   ├── homeassistant_lifecycle.md
│   └── error_handling.md
│
├── contributor/                # Contributor documentation
│   ├── contributing.md
│   ├── release_process.md
│   ├── coding/                 # Coding standards
│   │   ├── naming.md
│   │   └── docstring_standards.md
│   └── testing/                # Testing guides
│       └── testing_with_events.md
│
├── architecture/               # Technical deep-dives
│   ├── protocol_selection_guide.md
│   ├── data_flow.md
│   ├── sequence_diagrams.md
│   ├── caching.md
│   └── events/                 # Event system
│       ├── event_bus.md
│       └── event_reference.md
│
├── reference/                  # Reference material
│   ├── glossary.md
│   └── common_operations.md
│
├── adr/                        # Architecture Decision Records
└── migrations/                 # Migration guides
```

## Contributing to Documentation

1. Edit or create Markdown files in the `docs/` directory
2. Update `mkdocs.yml` navigation if adding new pages
3. Test locally with `mkdocs serve`
4. Submit a pull request

Documentation is automatically deployed when changes are pushed to `devel` or `master`.
