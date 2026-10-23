"""Tests for manifest version reader, writer, auditor, and synchronizer."""

import os
import json
import pytest
from semver_doctor.manifest import (
    read_manifest_version,
    write_manifest_version,
    find_manifest_files,
    audit_manifests,
    sync_manifests,
)


def test_package_json(tmp_path):
    f = tmp_path / "package.json"
    f.write_text(json.dumps({"name": "test-pkg", "version": "1.0.0"}, indent=2))

    assert read_manifest_version(str(f)) == "1.0.0"

    assert write_manifest_version(str(f), "1.1.0") is True
    assert read_manifest_version(str(f)) == "1.1.0"
    data = json.loads(f.read_text())
    assert data["version"] == "1.1.0"


def test_pyproject_toml(tmp_path):
    f = tmp_path / "pyproject.toml"
    content = """[project]
name = "my-tool"
version = "0.2.5"
description = "Sample"
"""
    f.write_text(content)

    assert read_manifest_version(str(f)) == "0.2.5"

    assert write_manifest_version(str(f), "0.3.0") is True
    assert read_manifest_version(str(f)) == "0.3.0"
    assert 'version = "0.3.0"' in f.read_text()


def test_cargo_toml(tmp_path):
    f = tmp_path / "Cargo.toml"
    content = """[package]
name = "my_crate"
version = "2.1.0"
edition = "2021"

[dependencies]
serde = "1.0"
"""
    f.write_text(content)

    assert read_manifest_version(str(f)) == "2.1.0"

    assert write_manifest_version(str(f), "2.2.0") is True
    assert read_manifest_version(str(f)) == "2.2.0"
    assert 'version = "2.2.0"' in f.read_text()


def test_setup_cfg(tmp_path):
    f = tmp_path / "setup.cfg"
    content = """[metadata]
name = my_package
version = 3.0.1
author = slopggobblercobbler81
"""
    f.write_text(content)

    assert read_manifest_version(str(f)) == "3.0.1"

    assert write_manifest_version(str(f), "3.1.0") is True
    assert read_manifest_version(str(f)) == "3.1.0"


def test_pom_xml(tmp_path):
    f = tmp_path / "pom.xml"
    content = """<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>app</artifactId>
  <version>1.4.2</version>
</project>
"""
    f.write_text(content)

    assert read_manifest_version(str(f)) == "1.4.2"

    assert write_manifest_version(str(f), "1.5.0") is True
    assert read_manifest_version(str(f)) == "1.5.0"


def test_version_txt_and_version(tmp_path):
    f1 = tmp_path / "VERSION"
    f1.write_text("1.0.0\n")
    assert read_manifest_version(str(f1)) == "1.0.0"
    assert write_manifest_version(str(f1), "1.0.1") is True
    assert read_manifest_version(str(f1)) == "1.0.1"

    f2 = tmp_path / "version.txt"
    f2.write_text("0.9.0\n")
    assert read_manifest_version(str(f2)) == "0.9.0"
    assert write_manifest_version(str(f2), "0.9.1") is True
    assert read_manifest_version(str(f2)) == "0.9.1"


def test_find_manifest_files(tmp_path):
    (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
    (tmp_path / "VERSION").write_text('1.0.0')

    found = find_manifest_files(str(tmp_path))
    assert "package.json" in found
    assert "VERSION" in found
    assert found["package.json"] == "1.0.0"
    assert found["VERSION"] == "1.0.0"


def test_audit_manifests_consistent_and_drift(tmp_path):
    # Empty
    empty_res = audit_manifests(str(tmp_path))
    assert empty_res["manifest_count"] == 0
    assert empty_res["consistent"] is True

    # Consistent
    (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
    (tmp_path / "VERSION").write_text('1.0.0')
    res = audit_manifests(str(tmp_path))
    assert res["manifest_count"] == 2
    assert res["consistent"] is True
    assert res["highest_version"] == "1.0.0"
    assert len(res["mismatches"]) == 0

    # Inconsistent / drift
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.1.0"\n')
    drift_res = audit_manifests(str(tmp_path))
    assert drift_res["manifest_count"] == 3
    assert drift_res["consistent"] is False
    assert drift_res["highest_version"] == "1.1.0"
    assert len(drift_res["mismatches"]) == 2  # package.json and VERSION are behind


def test_sync_manifests(tmp_path):
    (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.2.0"\n')

    # Dry run
    changes_dry = sync_manifests(str(tmp_path), dry_run=True)
    assert "package.json" in changes_dry
    assert changes_dry["package.json"]["new_version"] == "1.2.0"
    # verify file was NOT modified
    assert read_manifest_version(str(tmp_path / "package.json")) == "1.0.0"

    # Actual sync to highest
    changes = sync_manifests(str(tmp_path), dry_run=False)
    assert "package.json" in changes
    assert read_manifest_version(str(tmp_path / "package.json")) == "1.2.0"
    assert read_manifest_version(str(tmp_path / "pyproject.toml")) == "1.2.0"

    # Sync to explicit version
    sync_manifests(str(tmp_path), target_version="2.0.0")
    assert read_manifest_version(str(tmp_path / "package.json")) == "2.0.0"
    assert read_manifest_version(str(tmp_path / "pyproject.toml")) == "2.0.0"
