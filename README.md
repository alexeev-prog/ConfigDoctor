# ConfigDoctor
<a id="readme-top"></a>

<div align="center">
  <p align="center">
    A universal, plugin-based linter for all your configuration files
    <br />
    <a href="https://alexeev-prog.github.io/configdoctor/"><strong>Explore the docs »</strong></a>
    <br />
    <br />
    <a href="#-getting-started">Getting Started</a>
    ·
    <a href="#-usage-examples">Basic Usage</a>
    ·
    <a href="https://alexeev-prog.github.io/configdoctor/">Documentation</a>
    ·
    <a href="https://github.com/alexeev-prog/configdoctor/blob/main/LICENSE">License</a>
  </p>
</div>
<br>
<p align="center">
    <img src="https://img.shields.io/github/languages/top/alexeev-prog/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/github/languages/count/alexeev-prog/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/github/license/alexeev-prog/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/github/stars/alexeev-prog/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/github/issues/alexeev-prog/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/github/last-commit/alexeev-prog/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/pypi/wheel/configdoctor?style=for-the-badge">
    <img src="https://img.shields.io/badge/coverage-100%25-100%25?style=for-the-badge" alt="Coverage">
    <img alt="PyPI - Downloads" src="https://img.shields.io/pypi/dm/configdoctor?style=for-the-badge">
    <img alt="PyPI - Version" src="https://img.shields.io/pypi/v/configdoctor?style=for-the-badge">
    <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/configdoctor?style=for-the-badge">
    <img alt="GitHub contributors" src="https://img.shields.io/github/contributors/alexeev-prog/configdoctor?style=for-the-badge">
</p>
<p align="center">
    <img src="https://raw.githubusercontent.com/alexeev-prog/configdoctor/refs/heads/main/docs/pallet-0.png">
</p>

ConfigDoctor is a powerful, unified linter for configuration files (YAML, TOML, Docker, etc.). It enforces best practices, security, and style guidelines across your projects. Its plugin-based architecture allows for deep customization and easy integration into any CI/CD pipeline. Replace a collection of disparate linters with a single, configurable tool that provides clear, actionable feedback to keep your configs clean, secure, and consistent.

> [!CAUTION]
> configdoctor is currently in active alpha development. While core functionality is stable, some advanced features are still evolving. Production use requires thorough testing.

## Config Specification
ConfigDoctor utilizes a TOML-based configuration file (typically named `.configdoctor.toml`) to control all aspects of the linter's behavior. This configuration enables granular control over file selection, rule configuration, output formatting, and plugin management.

### General Settings
```toml
[general]
# Output verbosity level: "quiet", "normal", or "verbose"
verbosity = "normal"

# Output format: "human" (colored console), "json", or "github" (GitHub Actions annotations)
output_format = "human"

# Enable/disable colored output (only applicable to "human" format)
color = true

# Attempt to automatically fix fixable issues where possible
apply_fixes = false
```

### File Selection
```toml
[files]
# Glob patterns to include in analysis
include = [
    "**/*.yaml",
    "**/*.yml",
    "**/*.toml",
    # ... additional patterns
]

# Glob patterns to exclude from analysis
exclude = [
    "**/node_modules/**",
    "**/.git/**",
    # ... additional patterns
]
```

### Parser Configuration
```toml
[parsers]
# Use safe YAML loading (recommended for security)
yaml_safe_load = true

# Allow duplicate keys in YAML (generally not recommended)
yaml_allow_duplicates = false

# Allow YAML anchors and aliases
yaml_allow_anchors = true
```

### Rules Configuration
```toml
[rules]
# List of rule IDs to disable globally
disable = [
    "yaml::format::line-length",
    # ... additional rule IDs
]

# List of rule IDs to enable globally (overrides disable for these rules)
enable = [
    "general::security::no-secrets",
    # ... additional rule IDs
]

# Rule-specific configuration options
[rules.options]
    # Configure line-length rule
    [rules.options."general::format::line-length"]
    max = 120
    ignore_comments = true
    
    # Configure Dockerfile rule
    [rules.options."dockerfile::security::avoid-latest-tag"]
    allowed_images = ["nginx", "alpine"]
    
    # Configure compose rule
    [rules.options."compose::best-practices::pin-version"]
    mode = "warning"
    ignore_services = ["local-dev-service"]
```

### Plugin Management
```toml
[plugins]
# Additional paths to search for custom plugins
custom_paths = ["./devops/configdoctor_plugins"]

# Plugin-specific configuration
[plugins.dockerfile]
allowed_run_commands = ["apt-get update && apt-get install -y my-package"]

[plugins.yaml]
require_explicit_version = false

[plugins.compose]
target_version = "3.8"
```

### Output Configuration
```toml
[output]
# Group results by "file" or by "rule"
group_by = "file"

# Human-readable output settings
[output.human]
show_documentation_link = true
show_suggestion = true

# JSON output settings
[output.json]
include_source_code = false
pretty = true

# GitHub Actions output settings
[output.github]
use_workflow_commands = true
```

### Profiles
```toml
[profiles]
# Define a strict profile
[profiles.strict]
description = "Maximum strictness for production environments"
enable = [
    "dockerfile::security::*",
    "compose::best-practices::*",
]
[profiles.strict.rules.options]
    [profiles.strict.rules.options."general::format::line-length"]
    max = 100

# Define a development profile
[profiles.dev]
description = "Relaxed rules for development"
disable = [
    "dockerfile::security::avoid-latest-tag",
    "compose::best-practices::pin-version",
]
```

### File-Specific Overrides
```toml
# Override rules for development environments
[[overrides]]
files = ["**/dev/**", "**/staging/**"]
[overrides.rules]
disable = ["yaml::security::no-ssh-urls"]
[overrides.rules.options]
    [overrides.rules.options."dockerfile::security::avoid-latest-tag"]
    mode = "warning"

# Override rules for production environments
[[overrides]]
files = ["**/production/**"]
[overrides.rules]
enable = ["*::security::*"]
[overrides.rules.options]
    [overrides.rules.options."dockerfile::security::avoid-latest-tag"]
    mode = "error"
```

### Rule ID Format

Rules follow a consistent naming convention:
```
<domain>::<category>::<rule-name>
```

Where:
- `domain`: The technology or format (e.g., `yaml`, `dockerfile`, `compose`)
- `category`: The rule category (e.g., `format`, `security`, `best-practices`)
- `rule-name`: A descriptive name for the specific rule

Examples:
- `yaml::format::line-length`
- `dockerfile::security::avoid-latest-tag`
- `compose::best-practices::pin-version`

### Configuration Precedence

ConfigDoctor applies configuration settings in the following order of precedence (from highest to lowest):

1. Command-line arguments
2. File-specific overrides (matching the current file path)
3. Active profile settings
4. Global rules configuration
5. Default rule settings

### Configuration Validation

The configuration file is validated against a strict schema. Invalid configuration keys or values will result in errors with detailed messages about what needs to be corrected.

### Environment Variables

Configuration values can be overridden using environment variables with the `CONFIGDOCTOR_` prefix following the structure of the configuration file:

Example:
```bash
export CONFIGDOCTOR_GENERAL_VERBOSITY=verbose
export CONFIGDOCTOR_RULES_OPTIONS_GENERAL__FORMAT__LINE_LENGTH_MAX=150
```

Environment variables take precedence over all other configuration sources.

### Multiple Configuration Files

ConfigDoctor will search for configuration files in the following locations (in order of precedence):

1. `.configdoctor.toml` in the current directory
2. `.configdoctor.toml` in the user's home directory
3. Default built-in configuration

Settings are merged with later files overriding earlier ones.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. Key areas for contribution include:
- Additional test cases for thread-local scenarios
- Performance optimization proposals
- Extended version format support
- IDE integration plugins

## License & Support

This project is licensed under **GNU LGPL 2.1 License** - see [LICENSE](https://github.com/alexeev-prog/configdoctor/blob/main/LICENSE). For commercial support and enterprise features, contact [alexeev.dev@mail.ru](mailto:alexeev.dev@mail.ru).

[Explore Documentation](https://alexeev-prog.github.io/configdoctor) |
[Report Issue](https://github.com/alexeev-prog/configdoctor/issues) |
[View Examples](./examples)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

---
A universal, plugin-based linter for all your configuration files

Copyright © 2025 Alexeev Bronislav. Distributed under GNU LGPL 2.1 license.

