"""Tests for semver-doctor CLI commands."""

import json
import subprocess
import pytest
from semver_doctor.cli import main


def _run_git_cmd(args, cwd):
    subprocess.run(["git"] + args, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_cli_help(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "semver-doctor" in captured.out


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "0.1.0" in captured.out


def test_cli_no_args(capsys):
    ret = main([])
    assert ret == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out or "semver-doctor" in captured.out


def test_cli_lint_valid_and_invalid(capsys):
    # Valid loose
    ret = main(["lint", "v1.2.3", "2.0.0-beta.1"])
    assert ret == 0
    out = capsys.readouterr().out
    assert "VALID" in out

    # Strict failure with 'v'
    ret_strict = main(["lint", "v1.2.3", "--strict"])
    assert ret_strict == 1
    capsys.readouterr()

    # Invalid version
    ret_inv = main(["lint", "invalid.version.foo"])
    assert ret_inv == 1
    capsys.readouterr()

    # JSON output
    ret_json = main(["lint", "1.0.0", "--json"])
    assert ret_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["all_valid"] is True


def test_cli_lint_directory_fallback(tmp_path, capsys):
    (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
    ret = main(["lint", "--path", str(tmp_path)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "PASS" in out

    # Empty dir fallback
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    ret_empty = main(["lint", "--path", str(empty_dir)])
    assert ret_empty == 0
    capsys.readouterr()

    # Directory with invalid manifest version
    (empty_dir / "package.json").write_text('{"version": "invalid_ver"}')
    ret_bad = main(["lint", "--path", str(empty_dir)])
    assert ret_bad == 1
    capsys.readouterr()


def test_cli_compare(capsys):
    # Equal
    ret0 = main(["compare", "1.2.3", "1.2.3"])
    assert ret0 == 0
    capsys.readouterr()

    # Less than
    ret1 = main(["compare", "1.0.0", "1.2.0"])
    assert ret1 == 1
    capsys.readouterr()

    # Greater than
    ret2 = main(["compare", "2.0.0", "1.9.9"])
    assert ret2 == 2
    capsys.readouterr()

    # JSON mode
    ret_json = main(["compare", "1.0.0", "2.0.0", "--json"])
    assert ret_json == 1
    data = json.loads(capsys.readouterr().out)
    assert data["operator"] == "<"
    assert data["comparison"] == -1

    # Invalid version in compare
    ret_err = main(["compare", "1.0.0", "bad_version"])
    assert ret_err == 3
    capsys.readouterr()

    ret_err_json = main(["compare", "1.0.0", "bad_version", "--json"])
    assert ret_err_json == 3
    capsys.readouterr()


def test_cli_satisfies(capsys):
    # Satisfied
    ret0 = main(["satisfies", "1.2.3", "^1.0.0"])
    assert ret0 == 0
    capsys.readouterr()

    # Not satisfied
    ret1 = main(["satisfies", "2.0.0", "^1.0.0"])
    assert ret1 == 1
    capsys.readouterr()

    # JSON mode
    ret_json = main(["satisfies", "1.2.3", ">=1.0.0 <2.0.0", "--json"])
    assert ret_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["satisfies"] is True

    # Error handling
    ret_err = main(["satisfies", "1.2.3", "invalid!#%range"])
    assert ret_err == 2
    capsys.readouterr()

    ret_err_json = main(["satisfies", "1.2.3", "invalid!#%range", "--json"])
    assert ret_err_json == 2
    capsys.readouterr()


def test_cli_bump(tmp_path, capsys):
    ret = main(["bump", "minor", "1.2.3"])
    assert ret == 0
    assert "1.3.0" in capsys.readouterr().out

    # With preid
    ret_pre = main(["bump", "prerelease", "1.0.0", "--preid", "rc"])
    assert ret_pre == 0
    assert "1.0.1-rc.0" in capsys.readouterr().out

    # JSON bump
    ret_json = main(["bump", "major", "1.2.3", "--json"])
    assert ret_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["new_version"] == "2.0.0"

    # With sync into tmp_path
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text('{"version": "1.0.0"}')

    ret_sync = main(["bump", "minor", "1.0.0", "--path", str(tmp_path), "--sync"])
    assert ret_sync == 0
    capsys.readouterr()
    assert '"version": "1.1.0"' in pkg_file.read_text()

    # Bump with invalid bump type
    with pytest.raises(SystemExit) as exc:
        main(["bump", "nonexistent_type", "1.0.0"])
    assert exc.value.code == 2
    capsys.readouterr()


def test_cli_bump_auto_and_inferred(tmp_path, capsys):
    _run_git_cmd(["init", "-b", "main"], cwd=str(tmp_path))
    _run_git_cmd(["config", "user.name", "Test User"], cwd=str(tmp_path))
    _run_git_cmd(["config", "user.email", "test@example.com"], cwd=str(tmp_path))

    f = tmp_path / "file.txt"
    f.write_text("initial")
    _run_git_cmd(["add", "."], cwd=str(tmp_path))
    _run_git_cmd(["commit", "-m", "chore: initial"], cwd=str(tmp_path))
    _run_git_cmd(["tag", "v1.0.0"], cwd=str(tmp_path))

    f.write_text("feature")
    _run_git_cmd(["commit", "-am", "feat: add magic"], cwd=str(tmp_path))

    # Auto bump
    ret_auto = main(["bump", "--auto", "--path", str(tmp_path)])
    assert ret_auto == 0
    out = capsys.readouterr().out
    assert "v1.1.0" in out


def test_cli_sort(capsys):
    ret = main(["sort", "2.0.0", "1.0.0", "1.5.0"])
    assert ret == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert lines == ["1.0.0", "1.5.0", "2.0.0"]

    ret_rev = main(["sort", "2.0.0", "1.0.0", "1.5.0", "-r"])
    assert ret_rev == 0
    lines_rev = capsys.readouterr().out.strip().splitlines()
    assert lines_rev == ["2.0.0", "1.5.0", "1.0.0"]

    # Unique JSON
    ret_json = main(["sort", "1.0.0", "1.0.0", "--unique", "--json"])
    assert ret_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["sorted"] == ["1.0.0"]


def test_cli_manifest(tmp_path, capsys):
    (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
    (tmp_path / "VERSION").write_text('1.0.0')

    # Audit consistent
    ret_audit = main(["manifest", "audit", "--path", str(tmp_path)])
    assert ret_audit == 0
    assert "Consistent:      True" in capsys.readouterr().out

    # Introduce drift
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "2.0.0"\n')
    ret_drift = main(["manifest", "audit", "--path", str(tmp_path)])
    assert ret_drift == 1
    capsys.readouterr()

    # Sync
    ret_sync = main(["manifest", "sync", "--path", str(tmp_path)])
    assert ret_sync == 0
    capsys.readouterr()

    # Re-audit after sync
    ret_audit2 = main(["manifest", "audit", "--path", str(tmp_path)])
    assert ret_audit2 == 0
    capsys.readouterr()

    # Audit JSON
    ret_audit_json = main(["manifest", "audit", "--path", str(tmp_path), "--json"])
    assert ret_audit_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["consistent"] is True

    # Sync JSON
    ret_sync_json = main(["manifest", "sync", "3.0.0", "--path", str(tmp_path), "--json"])
    assert ret_sync_json == 0
    data_sync = json.loads(capsys.readouterr().out)
    assert data_sync["target_version"] == "3.0.0"


def test_cli_tags(tmp_path, capsys):
    # Non git repo
    ret_non_git = main(["tags", "--path", str(tmp_path)])
    assert ret_non_git == 1
    capsys.readouterr()

    ret_non_git_json = main(["tags", "--path", str(tmp_path), "--json"])
    assert ret_non_git_json == 1
    capsys.readouterr()

    # Initialize git repo
    _run_git_cmd(["init", "-b", "main"], cwd=str(tmp_path))
    _run_git_cmd(["config", "user.name", "Tester"], cwd=str(tmp_path))
    _run_git_cmd(["config", "user.email", "tester@test.com"], cwd=str(tmp_path))

    f = tmp_path / "f"
    f.write_text("x")
    _run_git_cmd(["add", "."], cwd=str(tmp_path))
    _run_git_cmd(["commit", "-m", "init"], cwd=str(tmp_path))
    _run_git_cmd(["tag", "v1.0.0"], cwd=str(tmp_path))

    ret_tags = main(["tags", "--path", str(tmp_path), "--suggest-next"])
    assert ret_tags == 0
    out = capsys.readouterr().out
    assert "Git Tag Audit" in out
    assert "Total tags: 1" in out

    ret_tags_json = main(["tags", "--path", str(tmp_path), "--suggest-next", "--json"])
    assert ret_tags_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_tags"] == 1


def test_cli_doctor(tmp_path, capsys):
    (tmp_path / "package.json").write_text('{"version": "1.0.0"}')
    ret = main(["doctor", "--path", str(tmp_path)])
    assert ret == 0
    out = capsys.readouterr().out
    assert "SemVer Doctor Health Check" in out

    ret_json = main(["doctor", "--path", str(tmp_path), "--json"])
    assert ret_json == 0
    data = json.loads(capsys.readouterr().out)
    assert data["healthy"] is True
