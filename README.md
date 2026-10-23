# semver-doctor

[![CI](https://github.com/slopggobblercobbler81/semver-doctor/actions/workflows/ci.yml/badge.svg)](https://github.com/slopggobblercobbler81/semver-doctor/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![SemVer 2.0.0](https://img.shields.io/badge/SemVer-2.0.0-blue.svg)](https://semver.org)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

Production-grade **Semantic Versioning (SemVer 2.0.0)** linter, git tag auditor, release bump calculator, and multi-ecosystem manifest synchronizer.

---

## Features

- **Strict SemVer 2.0.0 Specification Compliance**: Fully implements SemVer 2.0.0 rules, including Precedence Rule 11 (lexicographical vs numeric prerelease comparisons) and Rule 10 (ignoring build metadata in precedence).
- **SemVer Range Expressions**: Supports npm/cargo-style range evaluators: Caret (`^`), Tilde (`~`), wildcards (`*`, `x`, `1.x`), comparison operators (`>`, `>=`, `<`, `<=`, `!=`, `==`), hyphen ranges (`1.0.0 - 2.0.0`), and boolean unions (`||`).
- **Conventional Commits Release Bumper**: Analyzes git commit messages (`feat:`, `fix:`, `feat!:`, `BREAKING CHANGE:`) since the last release tag to determine the next major, minor, or patch bump.
- **Git Tag Doctor**: Audits git repository tags for SemVer violations, format drift, chronological tag inversions, and version gaps.
- **Manifest Synchronizer**: Automatically audits and syncs version strings across `package.json`, `pyproject.toml`, `Cargo.toml`, `setup.cfg`, `pom.xml`, `composer.json`, and `VERSION` files.
- **All-In-One Health Check (`semver-doctor doctor`)**: Single command to audit manifests, validate git tags, inspect unreleased commits, and verify release readiness.
- **Machine-Readable Output**: Full `--json` support across all subcommands for seamless CI/CD integration.

---

## Installation

```bash
pip install semver-doctor
```

Or install in editable mode for development:

```bash
git clone https://github.com/slopggobblercobbler81/semver-doctor.git
cd semver-doctor
pip install -e ".[dev]"
```

---

## CLI Usage

### 1. Validate & Lint Versions
Check whether version strings adhere to SemVer 2.0.0:

```bash
# Permissive mode (strips leading 'v', coerces partial versions)
semver-doctor lint v1.2.3 2.0.0-rc.1

# Strict mode (enforces strict SemVer 2.0.0 without leading 'v')
semver-doctor lint 1.2.3 --strict

# Automatically lint all project manifests and git tags
semver-doctor lint
```

### 2. Compare Versions
Compares two versions according to SemVer 2.0.0 precedence rules:

```bash
semver-doctor compare 1.2.0 1.2.1
# Output: 1.2.0 < 1.2.1 (1.2.0 is older than 1.2.1)
# Exit code: 1 (<), 0 (==), 2 (>)
```

### 3. Test Range Expressions
Verify if a version satisfies a dependency range requirement:

```bash
semver-doctor satisfies 1.2.4 "^1.2.0"
semver-doctor satisfies 2.1.0 ">=1.0.0 <3.0.0"
semver-doctor satisfies 1.0.0-rc.1 "^1.0.0 || ^2.0.0"
```

### 4. Release Bumping & Conventional Commits
Calculate the next version manually or automatically from git commits:

```bash
# Explicit bump
semver-doctor bump minor 1.2.3
# Output: Bumped version: 1.2.3 -> 1.3.0 (minor)

# Prerelease bump with custom tag identifier
semver-doctor bump prerelease 1.0.0 --preid rc
# Output: Bumped version: 1.0.0 -> 1.0.1-rc.0 (prerelease)

# Automatic bump based on Conventional Commits since last git tag
semver-doctor bump --auto

# Bump and synchronize version across all project manifests (pyproject.toml, package.json, etc.)
semver-doctor bump minor --sync
```

### 5. Git Tag Doctor
Inspect git repository tags for SemVer compliance and historical consistency:

```bash
# Audit tags in the current repository
semver-doctor tags

# Audit tags and suggest next version from unreleased commits
semver-doctor tags --suggest-next --json
```

### 6. Manifest Synchronization
Audit and synchronize version numbers across multiple config files:

```bash
# Audit all project manifests for version drift
semver-doctor manifest audit

# Preview synchronization changes without modifying files
semver-doctor manifest sync 2.0.0 --dry-run

# Synchronize all manifests to the highest detected version
semver-doctor manifest sync
```

### 7. Comprehensive Doctor Check
Run an all-in-one health check on your project:

```bash
semver-doctor doctor
```

Example output:
```text
=== SemVer Doctor Health Check: [HEALTHY] ===

[1] Manifests:
  Consistent: True
  - package.json: 0.1.0
  - pyproject.toml: 0.1.0

[2] Git Tags:
  Total tags: 5
  Highest tag: v0.1.0

[3] Next Release Recommendation:
  Current tag: v0.1.0
  Next version: v0.2.0 (minor)
  - Feature addition in commit: feat: add git tag auditor
```

---

## Python API

You can use `semver-doctor` as a Python library:

```python
from semver_doctor import (
    SemVer,
    parse_semver,
    is_valid_semver,
    satisfies,
    bump_version,
    sort_versions,
    audit_manifests,
)

# 1. Parse and validate
v1 = parse_semver("1.2.3-alpha.1+build.42")
print(v1.major, v1.minor, v1.patch)  # 1, 2, 3
print(v1.is_prerelease)              # True

# 2. Compare precedence
v2 = parse_semver("1.2.3")
print(v1 < v2)  # True (Prerelease has lower precedence)

# 3. Test ranges
print(satisfies("1.2.4", "^1.2.0"))  # True

# 4. Bump version
next_v = bump_version("1.2.3", "minor")
print(next_v)  # 1.3.0

# 5. Sort versions
sorted_list = sort_versions(["2.0.0", "1.0.0", "1.0.0-alpha"], reverse=False)
print(sorted_list)  # ['1.0.0-alpha', '1.0.0', '2.0.0']
```

---

## CI / GitHub Actions Integration

Add `semver-doctor` into your pull request workflows to prevent invalid release tags and manifest drift:

```yaml
name: SemVer Guard

on: [push, pull_request]

jobs:
  semver-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install semver-doctor
        run: pip install semver-doctor

      - name: Run SemVer Health Check
        run: semver-doctor doctor
```

---

## Testing

Run unit test suite with coverage:

```bash
pytest --cov=semver_doctor --cov-report=term-missing
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
