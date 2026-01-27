# Community Templates for Home Assistant

This page provides an overview of community-contributed templates and guides for integrating Homematic devices with Home Assistant.

## Device-Specific Guides

Detailed guides for specific Homematic devices:

| Device | Description |
|--------|-------------|
| [HmIP-SWSD Smoke Detector](devices/hmip_swsd_smoke_detector.md) | Binary sensors for multi-state smoke detector |
| [HmIP-SRH Window Handle](devices/hmip_srh_window_handle.md) | Three-state window handle sensor (closed/tilted/open) |

---

## Contributing

We welcome community contributions! If you have a useful template, device guide, or CCU script, here's how to share it:

### How to Contribute

1. **Fork** the [aiohomematic repository](https://github.com/SukramJ/aiohomematic)
2. **Create** your guide as a Markdown file in the appropriate folder:
   - `docs/user/devices/` — Device-specific guides (naming: `device_model.md`)
   - `docs/user/ccu_scripts/` — CCU maintenance scripts
3. **Submit** a Pull Request with a brief description

### Content Guidelines

Your contribution should include:

- **Problem description** — What challenge does this solve?
- **Complete configuration** — Tested YAML/code that users can copy
- **Customization notes** — Which entity IDs or values need adjustment
- **Your credit** — Add yourself as contributor (optional)

### Questions?

Open a [Discussion](https://github.com/SukramJ/aiohomematic/discussions) if you're unsure whether your idea fits or need help with formatting.
