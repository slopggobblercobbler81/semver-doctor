"""Tests for SemVer bumping and Conventional Commits analyzer."""

import pytest
from semver_doctor.bumper import bump_version, analyze_conventional_commits
from semver_doctor.version import SemVer


def test_bump_major():
    assert bump_version("1.2.3", "major") == SemVer(2, 0, 0)
    assert bump_version("0.1.0", "major") == SemVer(1, 0, 0)


def test_bump_minor():
    assert bump_version("1.2.3", "minor") == SemVer(1, 3, 0)
    assert bump_version("0.0.1", "minor") == SemVer(0, 1, 0)


def test_bump_patch():
    assert bump_version("1.2.3", "patch") == SemVer(1, 2, 4)
    # Prerelease patch bumps to release version
    assert bump_version("1.2.3-alpha.1", "patch") == SemVer(1, 2, 3)


def test_bump_premajor():
    assert bump_version("1.2.3", "premajor", preid="beta") == SemVer(2, 0, 0, prerelease="beta.0")
    assert bump_version("1.2.3", "premajor") == SemVer(2, 0, 0, prerelease="alpha.0")


def test_bump_preminor():
    assert bump_version("1.2.3", "preminor", preid="rc") == SemVer(1, 3, 0, prerelease="rc.0")


def test_bump_prepatch():
    assert bump_version("1.2.3", "prepatch") == SemVer(1, 2, 4, prerelease="alpha.0")


def test_bump_prerelease_sequences():
    # From non-prerelease
    v1 = bump_version("1.2.3", "prerelease", preid="alpha")
    assert v1 == SemVer(1, 2, 4, prerelease="alpha.0")

    # Incrementing alpha.0 -> alpha.1
    v2 = bump_version(v1, "prerelease")
    assert v2 == SemVer(1, 2, 4, prerelease="alpha.1")

    # Incrementing single integer prerelease
    v_int = bump_version("1.2.3-0", "prerelease")
    assert v_int == SemVer(1, 2, 3, prerelease="1")

    # Changing preid from alpha.1 to beta
    v3 = bump_version(v2, "prerelease", preid="beta")
    assert v3 == SemVer(1, 2, 4, prerelease="beta.0")

    # Bare prerelease identifier like "beta" -> "beta.1"
    v_bare = bump_version("1.2.3-beta", "prerelease")
    assert v_bare == SemVer(1, 2, 3, prerelease="beta.1")


def test_invalid_bump_type():
    with pytest.raises(ValueError, match="Invalid bump type"):
        bump_version("1.0.0", "supermajor")


def test_analyze_conventional_commits():
    # Breaking change
    commits_breaking = [
        "fix: tiny bug",
        "feat(api)!: drop legacy endpoint",
        "docs: update readme"
    ]
    bump, reasons = analyze_conventional_commits(commits_breaking)
    assert bump == "major"
    assert len(reasons) > 0

    # BREAKING CHANGE footer
    commits_breaking_footer = [
        "feat: new feature\n\nBREAKING CHANGE: changes authentication signature"
    ]
    bump, reasons = analyze_conventional_commits(commits_breaking_footer)
    assert bump == "major"

    # Feature
    commits_feat = [
        "fix: resolve race condition",
        "feat: add export to json",
        "chore: lint cleanups"
    ]
    bump, _ = analyze_conventional_commits(commits_feat)
    assert bump == "minor"

    # Fix
    commits_fix = [
        "fix: resolve null dereference",
        "perf: optimize memory usage",
        "refactor: modularize internals"
    ]
    bump, _ = analyze_conventional_commits(commits_fix)
    assert bump == "patch"

    # No commits or empty
    bump_empty, _ = analyze_conventional_commits([])
    assert bump_empty == "none"
