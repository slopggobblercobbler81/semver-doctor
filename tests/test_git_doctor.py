"""Tests for git doctor tag auditing and commit release suggestions."""

import subprocess
import pytest
from semver_doctor.git_doctor import (
    is_git_repository,
    get_git_tags,
    audit_git_tags,
    get_commits_since_last_tag,
    suggest_next_version,
)


def test_non_git_repo(tmp_path):
    assert is_git_repository(str(tmp_path)) is False
    assert get_git_tags(str(tmp_path)) == []
    audit = audit_git_tags(str(tmp_path))
    assert audit["is_git_repo"] is False
    assert audit["all_valid"] is True


def _run_git_cmd(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_git_tag_audit_and_suggestions(tmp_path):
    # Initialize a temporary git repository
    _run_git_cmd(["init", "-b", "main"], cwd=str(tmp_path))
    _run_git_cmd(["config", "user.name", "Test User"], cwd=str(tmp_path))
    _run_git_cmd(["config", "user.email", "test@example.com"], cwd=str(tmp_path))

    assert is_git_repository(str(tmp_path)) is True

    # Initial state with no tags and no commits
    sug0 = suggest_next_version(str(tmp_path))
    assert sug0["bump_type"] == "initial"
    assert sug0["next_version"] == "0.1.0"

    # Make first commit (2026-01-01) and tag v1.0.0
    f = tmp_path / "file.txt"
    f.write_text("initial")
    _run_git_cmd(["add", "."], cwd=str(tmp_path))
    _run_git_cmd(["commit", "-m", "chore: initial commit", "--date=2026-01-01T10:00:00"], cwd=str(tmp_path))
    _run_git_cmd(["tag", "v1.0.0"], cwd=str(tmp_path))

    # Audit tags
    audit1 = audit_git_tags(str(tmp_path))
    assert audit1["total_tags"] == 1
    assert audit1["valid_loose_tags"] == ["v1.0.0"]
    assert audit1["highest_tag"] == "v1.0.0"
    assert audit1["all_valid"] is True

    # Add feature commit (2026-01-02)
    f.write_text("new feature")
    _run_git_cmd(["commit", "-am", "feat: add user login", "--date=2026-01-02T10:00:00"], cwd=str(tmp_path))

    sug1 = suggest_next_version(str(tmp_path))
    assert sug1["current_tag"] == "v1.0.0"
    assert sug1["bump_type"] == "minor"
    assert sug1["next_version"] == "v1.1.0"

    # Tag v1.1.0 and add breaking change commit (2026-01-03)
    _run_git_cmd(["tag", "v1.1.0"], cwd=str(tmp_path))
    f.write_text("breaking")
    _run_git_cmd(["commit", "-am", "feat!: overhaul api", "--date=2026-01-03T10:00:00"], cwd=str(tmp_path))

    sug2 = suggest_next_version(str(tmp_path))
    assert sug2["current_tag"] == "v1.1.0"
    assert sug2["bump_type"] == "major"
    assert sug2["next_version"] == "v2.0.0"

    # Add an invalid tag and an out-of-order tag on a later commit (2026-01-04)
    _run_git_cmd(["tag", "release-candidate-final"], cwd=str(tmp_path))
    f.write_text("later regression commit")
    _run_git_cmd(["commit", "-am", "fix: old patch", "--date=2026-01-04T10:00:00"], cwd=str(tmp_path))
    _run_git_cmd(["tag", "v1.0.5"], cwd=str(tmp_path))

    audit2 = audit_git_tags(str(tmp_path))
    assert "release-candidate-final" in audit2["invalid_tags"]
    assert audit2["all_valid"] is False
    assert len(audit2["chronology_issues"]) > 0  # v1.0.5 tagged on later commit than v1.1.0
