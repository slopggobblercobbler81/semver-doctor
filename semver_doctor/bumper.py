"""SemVer version bumping and Conventional Commits analyzer."""

from __future__ import annotations
import re
from typing import List, Tuple, Optional, Union
from semver_doctor.version import SemVer, parse_semver

BUMP_TYPES = {"major", "minor", "patch", "premajor", "preminor", "prepatch", "prerelease"}

def bump_version(
    version: Union[str, SemVer],
    bump_type: str,
    preid: Optional[str] = None
) -> SemVer:
    """Calculates next SemVer based on bump type."""
    v = parse_semver(str(version), loose=True) if not isinstance(version, SemVer) else version
    bump = bump_type.lower()
    tag_id = preid or "alpha"

    if bump not in BUMP_TYPES:
        raise ValueError(f"Invalid bump type '{bump}'. Supported: {', '.join(sorted(BUMP_TYPES))}")

    if bump == "major":
        return SemVer(major=v.major + 1, minor=0, patch=0)
    elif bump == "minor":
        return SemVer(major=v.major, minor=v.minor + 1, patch=0)
    elif bump == "patch":
        if v.is_prerelease:
            # If currently 1.0.0-alpha, patch bump returns 1.0.0
            return SemVer(major=v.major, minor=v.minor, patch=v.patch)
        return SemVer(major=v.major, minor=v.minor, patch=v.patch + 1)
    elif bump == "premajor":
        return SemVer(major=v.major + 1, minor=0, patch=0, prerelease=f"{tag_id}.0")
    elif bump == "preminor":
        return SemVer(major=v.major, minor=v.minor + 1, patch=0, prerelease=f"{tag_id}.0")
    elif bump == "prepatch":
        return SemVer(major=v.major, minor=v.minor, patch=v.patch + 1, prerelease=f"{tag_id}.0")
    elif bump == "prerelease":
        if not v.is_prerelease:
            return SemVer(major=v.major, minor=v.minor, patch=v.patch + 1, prerelease=f"{tag_id}.0")

        # Existing prerelease e.g. "alpha.0" or "rc.1"
        pr = v.prerelease or ""
        parts = pr.split(".")
        # Check if preid matches or was specified
        if len(parts) >= 2 and parts[-1].isdigit():
            existing_id = ".".join(parts[:-1])
            counter = int(parts[-1])
            if preid is None or preid == existing_id:
                new_pr = f"{existing_id}.{counter + 1}"
            else:
                new_pr = f"{tag_id}.0"
        elif len(parts) == 1 and parts[0].isdigit():
            new_pr = str(int(parts[0]) + 1)
        else:
            # Alpha without counter e.g. "beta"
            if preid and preid != pr:
                new_pr = f"{preid}.0"
            else:
                new_pr = f"{pr}.1"

        return SemVer(major=v.major, minor=v.minor, patch=v.patch, prerelease=new_pr)

    raise ValueError(f"Unhandled bump type: {bump}")


def analyze_conventional_commits(commits: List[str]) -> Tuple[str, List[str]]:
    """Analyzes a list of commit messages following Conventional Commits specification.
    
    Returns (recommended_bump_type, summary_reasons).
    """
    has_breaking = False
    has_feat = False
    has_fix = False
    reasons = []

    breaking_pattern = re.compile(r"^[a-zA-Z0-9_-]+(\([a-zA-Z0-9_ -]+\))?!:|BREAKING[ -]CHANGE:", re.MULTILINE)
    feat_pattern = re.compile(r"^feat(\([a-zA-Z0-9_ -]+\))?:", re.IGNORECASE)
    fix_pattern = re.compile(r"^(fix|perf|refactor|revert)(\([a-zA-Z0-9_ -]+\))?:", re.IGNORECASE)

    for commit in commits:
        commit_clean = commit.strip()
        if not commit_clean:
            continue

        if breaking_pattern.search(commit_clean):
            has_breaking = True
            reasons.append(f"Breaking change found in commit: {commit_clean.splitlines()[0]}")
        elif feat_pattern.search(commit_clean):
            has_feat = True
            reasons.append(f"Feature addition in commit: {commit_clean.splitlines()[0]}")
        elif fix_pattern.search(commit_clean):
            has_fix = True
            reasons.append(f"Bugfix or performance fix in commit: {commit_clean.splitlines()[0]}")

    if has_breaking:
        return "major", reasons
    elif has_feat:
        return "minor", reasons
    elif has_fix:
        return "patch", reasons
    else:
        # Default to patch if there are unclassified commits
        return "patch" if commits else "none", reasons
