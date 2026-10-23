"""Inspects and synchronizes SemVer versions across project manifest files."""

from __future__ import annotations
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Any
from semver_doctor.version import parse_semver, SemVer, sort_versions

MANIFEST_FILES = [
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "VERSION",
    "version.txt",
    "setup.cfg",
    "composer.json",
    "pom.xml",
]


def read_manifest_version(filepath: str) -> Optional[str]:
    """Extracts version string from a manifest file."""
    if not os.path.isfile(filepath):
        return None

    filename = os.path.basename(filepath)

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return None

    if filename in ("package.json", "composer.json"):
        try:
            data = json.loads(content)
            return data.get("version")
        except Exception:
            return None

    if filename == "pyproject.toml":
        # Look for [project] version = "..." or [tool.poetry] version = "..."
        m = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if m:
            return m.group(1)
        return None

    if filename == "Cargo.toml":
        in_package = False
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("["):
                in_package = (line_str == "[package]")
            elif in_package:
                m = re.match(r'^version\s*=\s*["\']([^"\']+)["\']', line_str)
                if m:
                    return m.group(1)
        return None

    if filename == "setup.cfg":
        in_metadata = False
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("["):
                in_metadata = (line_str.lower() == "[metadata]")
            elif in_metadata:
                m = re.match(r'^version\s*=\s*(.+)$', line_str)
                if m:
                    return m.group(1).strip().strip('"\'')
        return None

    if filename == "pom.xml":
        m = re.search(r'<version>([^<]+)</version>', content)
        if m:
            return m.group(1).strip()
        return None

    if filename in ("VERSION", "version.txt"):
        return content.strip().splitlines()[0].strip() if content.strip() else None

    return None


def write_manifest_version(filepath: str, new_version: str) -> bool:
    """Updates version in a manifest file. Returns True if modified."""
    if not os.path.isfile(filepath):
        return False

    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    new_content = content

    if filename in ("package.json", "composer.json"):
        try:
            data = json.loads(content)
            data["version"] = new_version
            new_content = json.dumps(data, indent=2) + "\n"
        except Exception:
            return False

    elif filename == "pyproject.toml":
        new_content = re.sub(
            r'(^\s*version\s*=\s*["\'])[^"\']+(["\'])',
            rf'\g<1>{new_version}\g<2>',
            content,
            count=1,
            flags=re.MULTILINE
        )

    elif filename == "Cargo.toml":
        lines = content.splitlines()
        in_package = False
        updated = False
        new_lines = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("["):
                in_package = (line_str == "[package]")
            elif in_package and not updated:
                if re.match(r'^version\s*=\s*["\'][^"\']+["\']', line_str):
                    line = f'version = "{new_version}"'
                    updated = True
            new_lines.append(line)
        new_content = "\n".join(new_lines) + "\n"

    elif filename == "setup.cfg":
        lines = content.splitlines()
        in_metadata = False
        updated = False
        new_lines = []
        for line in lines:
            line_str = line.strip()
            if line_str.startswith("["):
                in_metadata = (line_str.lower() == "[metadata]")
            elif in_metadata and not updated:
                if re.match(r'^version\s*=', line_str):
                    line = f'version = {new_version}'
                    updated = True
            new_lines.append(line)
        new_content = "\n".join(new_lines) + "\n"

    elif filename == "pom.xml":
        new_content = re.sub(
            r'<version>[^<]+</version>',
            f'<version>{new_version}</version>',
            content,
            count=1
        )

    elif filename in ("VERSION", "version.txt"):
        new_content = f"{new_version}\n"

    if new_content != content:
        with open(filepath, "w", encoding="utf-8", newline="\n") as f:
            f.write(new_content)
        return True

    return False


def find_manifest_files(directory: str) -> Dict[str, str]:
    """Finds all existing manifest files and their detected versions in directory."""
    results: Dict[str, str] = {}
    for filename in MANIFEST_FILES:
        full_path = os.path.join(directory, filename)
        if os.path.isfile(full_path):
            ver = read_manifest_version(full_path)
            if ver:
                results[filename] = ver
    return results


def audit_manifests(directory: str = ".") -> Dict[str, Any]:
    """Audits all manifest files in the directory for version consistency."""
    manifests = find_manifest_files(directory)
    if not manifests:
        return {
            "manifest_count": 0,
            "consistent": True,
            "versions": {},
            "highest_version": None,
            "mismatches": [],
        }

    unique_versions = set(manifests.values())
    sorted_vers = sort_versions(list(unique_versions), reverse=True)
    highest = sorted_vers[0] if sorted_vers else None
    consistent = len(unique_versions) == 1

    mismatches = []
    if not consistent and highest:
        for fname, ver in manifests.items():
            if ver != highest:
                mismatches.append({
                    "file": fname,
                    "version": ver,
                    "expected": highest
                })

    return {
        "manifest_count": len(manifests),
        "consistent": consistent,
        "versions": manifests,
        "highest_version": highest,
        "mismatches": mismatches,
    }


def sync_manifests(
    directory: str = ".",
    target_version: Optional[str] = None,
    dry_run: bool = False
) -> Dict[str, Dict[str, str]]:
    """Synchronizes all detected manifests in directory to target_version (or highest version)."""
    manifests = find_manifest_files(directory)
    if not manifests:
        return {}

    if not target_version:
        sorted_vers = sort_versions(list(manifests.values()), reverse=True)
        target = sorted_vers[0] if sorted_vers else None
    else:
        target = target_version

    if not target:
        return {}

    changes: Dict[str, Dict[str, str]] = {}
    for fname, old_ver in manifests.items():
        if old_ver != target:
            full_path = os.path.join(directory, fname)
            if not dry_run:
                write_manifest_version(full_path, target)
            changes[fname] = {
                "old_version": old_ver,
                "new_version": target,
                "modified": not dry_run
            }

    return changes
