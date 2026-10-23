"""Git repository tag auditing, commit analysis, and release version suggestion."""

from __future__ import annotations
import subprocess
import re
import os
from typing import List, Dict, Any, Optional, Tuple
from semver_doctor.version import parse_semver, is_valid_semver, sort_versions, SemVer
from semver_doctor.bumper import bump_version, analyze_conventional_commits


def _run_git(args: List[str], cwd: str = ".") -> Tuple[int, str, str]:
    """Execute git command safely."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (FileNotFoundError, PermissionError) as e:
        return 1, "", str(e)


def is_git_repository(repo_dir: str = ".") -> bool:
    """Check if directory is inside a valid git repository."""
    code, out, _ = _run_git(["rev-parse", "--is-inside-work-tree"], cwd=repo_dir)
    return code == 0 and out.strip() == "true"


def get_git_tags(repo_dir: str = ".") -> List[str]:
    """Retrieve all git tags from repository in topological/creation order."""
    if not is_git_repository(repo_dir):
        return []

    code, out, _ = _run_git(["tag", "-l", "--sort=creatordate"], cwd=repo_dir)
    if code != 0 or not out:
        return []
    return [t.strip() for t in out.splitlines() if t.strip()]


def audit_git_tags(repo_dir: str = ".") -> Dict[str, Any]:
    """Audits git tags in the repository for SemVer 2.0.0 compliance and ordering."""
    if not is_git_repository(repo_dir):
        return {
            "is_git_repo": False,
            "total_tags": 0,
            "valid_strict_tags": [],
            "valid_loose_tags": [],
            "invalid_tags": [],
            "highest_tag": None,
            "chronology_issues": [],
            "all_valid": True,
        }

    raw_tags = get_git_tags(repo_dir)
    valid_strict: List[str] = []
    valid_loose: List[str] = []
    invalid: List[str] = []

    for tag in raw_tags:
        if is_valid_semver(tag, loose=False):
            valid_strict.append(tag)
            valid_loose.append(tag)
        elif is_valid_semver(tag, loose=True):
            valid_loose.append(tag)
        else:
            invalid.append(tag)

    # Sort valid tags by SemVer precedence
    sorted_loose = sort_versions(valid_loose, reverse=True, loose=True)
    highest_tag = sorted_loose[0] if sorted_loose else None

    # Check for chronology issues:
    # A newer tag created later in git history should normally have a higher or equal SemVer than the previous tag
    chronology_issues: List[Dict[str, str]] = []
    parsed_history: List[Tuple[str, SemVer]] = []

    for tag in valid_loose:
        try:
            sv = parse_semver(tag, loose=True)
            parsed_history.append((tag, sv))
        except ValueError:
            pass

    for i in range(1, len(parsed_history)):
        prev_tag, prev_sv = parsed_history[i - 1]
        curr_tag, curr_sv = parsed_history[i]
        # Flag if a tag created later has a lower SemVer than an earlier tag
        if curr_sv < prev_sv:
            chronology_issues.append({
                "earlier_tag": prev_tag,
                "later_tag": curr_tag,
                "reason": f"Tag '{curr_tag}' (v{curr_sv}) was created after higher tag '{prev_tag}' (v{prev_sv})"
            })

    return {
        "is_git_repo": True,
        "total_tags": len(raw_tags),
        "valid_strict_tags": valid_strict,
        "valid_loose_tags": valid_loose,
        "invalid_tags": invalid,
        "highest_tag": highest_tag,
        "chronology_issues": chronology_issues,
        "all_valid": len(invalid) == 0,
    }


def get_commits_since_last_tag(repo_dir: str = ".") -> Tuple[Optional[str], List[str]]:
    """Returns (last_tag, commit_messages) since the latest git tag."""
    if not is_git_repository(repo_dir):
        return None, []

    tags = get_git_tags(repo_dir)
    # Find latest tag
    if tags:
        last_tag = tags[-1]
        code, out, _ = _run_git(["log", f"{last_tag}..HEAD", "--pretty=format:%s"], cwd=repo_dir)
        commits = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []
        return last_tag, commits
    else:
        code, out, _ = _run_git(["log", "--pretty=format:%s"], cwd=repo_dir)
        commits = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []
        return None, commits


def suggest_next_version(
    repo_dir: str = ".",
    default_initial: str = "0.1.0",
    preid: Optional[str] = None
) -> Dict[str, Any]:
    """Calculates the recommended next version based on Conventional Commits since last tag."""
    last_tag, commits = get_commits_since_last_tag(repo_dir)

    if not last_tag:
        # Check if there is any manifest version
        return {
            "current_tag": None,
            "commits_analyzed": len(commits),
            "bump_type": "initial",
            "next_version": default_initial,
            "reasons": ["Initial release; no git tags found."],
        }

    has_v_prefix = last_tag.startswith(("v", "V"))
    try:
        current_sv = parse_semver(last_tag, loose=True)
    except ValueError:
        current_sv = parse_semver(default_initial, loose=True)

    bump_type, reasons = analyze_conventional_commits(commits)
    if bump_type == "none" or not commits:
        next_sv = current_sv
        next_ver_str = f"v{next_sv}" if has_v_prefix else str(next_sv)
        return {
            "current_tag": last_tag,
            "commits_analyzed": len(commits),
            "bump_type": "none",
            "next_version": next_ver_str,
            "reasons": ["No commits found since last tag."] if not commits else reasons,
        }

    next_sv = bump_version(current_sv, bump_type, preid=preid)
    next_ver_str = f"v{next_sv}" if has_v_prefix else str(next_sv)

    return {
        "current_tag": last_tag,
        "commits_analyzed": len(commits),
        "bump_type": bump_type,
        "next_version": next_ver_str,
        "reasons": reasons,
    }
