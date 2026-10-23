"""Command-line interface for semver-doctor."""

from __future__ import annotations
import argparse
import sys
import json
from typing import List, Optional, Any
from semver_doctor.__version__ import __version__
from semver_doctor.version import (
    SemVer,
    parse_semver,
    is_valid_semver,
    clean_semver,
    sort_versions,
)
from semver_doctor.range_matcher import satisfies
from semver_doctor.bumper import bump_version, BUMP_TYPES
from semver_doctor.manifest import (
    audit_manifests,
    sync_manifests,
    find_manifest_files,
)
from semver_doctor.git_doctor import (
    audit_git_tags,
    suggest_next_version,
    is_git_repository,
    get_commits_since_last_tag,
)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2))


def handle_lint(args: argparse.Namespace) -> int:
    """Handles the 'lint' / 'check' subcommand."""
    loose = not args.strict
    versions = args.versions

    if not versions:
        # If no versions passed, automatically check manifest versions and git tags
        manifest_res = audit_manifests(args.path)
        tag_res = audit_git_tags(args.path)
        extracted = []
        for f, v in manifest_res.get("versions", {}).items():
            extracted.append((f"manifest:{f}", v))
        for t in tag_res.get("valid_loose_tags", []) + tag_res.get("invalid_tags", []):
            extracted.append((f"git-tag:{t}", t))

        if not extracted:
            print("No versions specified and no manifest files or git tags detected to check.")
            return 0

        results = []
        all_valid = True
        for source, v_str in extracted:
            valid = is_valid_semver(v_str, loose=loose)
            if not valid:
                all_valid = False
            results.append({
                "source": source,
                "version": v_str,
                "valid": valid,
                "strict": is_valid_semver(v_str, loose=False),
            })

        if args.json:
            _print_json({"all_valid": all_valid, "results": results})
        else:
            for r in results:
                status = "PASS" if r["valid"] else "FAIL"
                print(f"[{status}] {r['source']}: '{r['version']}' (strict: {r['strict']})")
        return 0 if all_valid else 1

    results = []
    all_valid = True
    for v_str in versions:
        valid = is_valid_semver(v_str, loose=loose)
        strict_valid = is_valid_semver(v_str, loose=False)
        if not valid:
            all_valid = False
        parsed_str = clean_semver(v_str) if valid else None
        results.append({
            "version": v_str,
            "valid": valid,
            "strict": strict_valid,
            "normalized": parsed_str,
        })

    if args.json:
        _print_json({"all_valid": all_valid, "results": results})
    else:
        for r in results:
            status = "VALID" if r["valid"] else "INVALID"
            norm = f" -> {r['normalized']}" if r["normalized"] and r["normalized"] != r["version"] else ""
            print(f"[{status}] {r['version']}{norm} (strict: {r['strict']})")

    return 0 if all_valid else 1


def handle_compare(args: argparse.Namespace) -> int:
    """Handles the 'compare' subcommand."""
    v1_str = args.v1
    v2_str = args.v2
    loose = not args.strict

    try:
        sv1 = parse_semver(v1_str, loose=loose)
        sv2 = parse_semver(v2_str, loose=loose)
    except ValueError as e:
        if args.json:
            _print_json({"error": str(e), "success": False})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 3

    if sv1 < sv2:
        operator = "<"
        cmp_result = -1
        exit_code = 1
        description = f"{v1_str} is older than {v2_str}"
    elif sv1 > sv2:
        operator = ">"
        cmp_result = 1
        exit_code = 2
        description = f"{v1_str} is newer than {v2_str}"
    else:
        operator = "=="
        cmp_result = 0
        exit_code = 0
        description = f"{v1_str} and {v2_str} are semantically equal"

    if args.json:
        _print_json({
            "v1": v1_str,
            "v2": v2_str,
            "operator": operator,
            "comparison": cmp_result,
            "description": description
        })
    else:
        print(f"{v1_str} {operator} {v2_str} ({description})")

    return exit_code


def handle_satisfies(args: argparse.Namespace) -> int:
    """Handles the 'satisfies' subcommand."""
    version_str = args.version
    range_expr = args.range
    loose = not args.strict

    try:
        res = satisfies(version_str, range_expr, loose=loose)
    except ValueError as e:
        if args.json:
            _print_json({"error": str(e), "satisfies": False})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 2

    if args.json:
        _print_json({
            "version": version_str,
            "range": range_expr,
            "satisfies": res
        })
    else:
        status = "SATISFIES" if res else "DOES NOT SATISFY"
        print(f"Version '{version_str}' {status} range '{range_expr}'")

    return 0 if res else 1


def handle_bump(args: argparse.Namespace) -> int:
    """Handles the 'bump' subcommand."""
    version_input = args.version
    bump_type = (args.bump_type or "").lower()
    preid = args.preid

    # If --auto is specified, analyze conventional commits
    if args.auto:
        suggestion = suggest_next_version(repo_dir=args.path, preid=preid)
        bump_type = suggestion["bump_type"]
        if bump_type in ("initial", "none") and not version_input:
            version_input = suggestion["next_version"]
            bump_type = None

    # If version not passed, infer from highest manifest or git tag
    if not version_input:
        manifest_res = audit_manifests(args.path)
        tag_res = audit_git_tags(args.path)
        candidates = []
        if manifest_res.get("highest_version"):
            candidates.append(manifest_res["highest_version"])
        if tag_res.get("highest_tag"):
            candidates.append(tag_res["highest_tag"])

        if candidates:
            version_input = sort_versions(candidates, reverse=True, loose=True)[0]
        else:
            version_input = "0.0.0"

    has_v_prefix = version_input.startswith(("v", "V"))

    try:
        if bump_type:
            new_sv = bump_version(version_input, bump_type, preid=preid)
            new_version_str = f"v{new_sv}" if has_v_prefix else str(new_sv)
        else:
            new_version_str = version_input
    except ValueError as e:
        if args.json:
            _print_json({"error": str(e), "success": False})
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 1

    manifest_changes = {}
    if args.sync:
        clean_target = new_version_str.lstrip("vV")
        manifest_changes = sync_manifests(args.path, target_version=clean_target, dry_run=args.dry_run)

    if args.json:
        _print_json({
            "previous_version": version_input,
            "bump_type": bump_type,
            "new_version": new_version_str,
            "synced_manifests": manifest_changes,
            "dry_run": args.dry_run
        })
    else:
        print(f"Bumped version: {version_input} -> {new_version_str} ({bump_type or 'no bump'})")
        if args.sync:
            if manifest_changes:
                action = "Planned updates" if args.dry_run else "Updated manifests"
                print(f"{action}:")
                for f, details in manifest_changes.items():
                    print(f"  - {f}: {details['old_version']} -> {details['new_version']}")
            else:
                print("Manifests already in sync or none found.")

    return 0


def handle_sort(args: argparse.Namespace) -> int:
    """Handles the 'sort' subcommand."""
    versions = args.versions
    if args.unique:
        seen = set()
        deduped = []
        for v in versions:
            if v not in seen:
                seen.add(v)
                deduped.append(v)
        versions = deduped

    sorted_list = sort_versions(versions, reverse=args.reverse, loose=True)

    if args.json:
        _print_json({"sorted": sorted_list})
    else:
        for v in sorted_list:
            print(v)

    return 0


def handle_tags(args: argparse.Namespace) -> int:
    """Handles the 'tags' subcommand."""
    repo_dir = args.path
    audit_data = audit_git_tags(repo_dir)

    if not audit_data["is_git_repo"]:
        if args.json:
            _print_json({"error": "Directory is not a git repository", "success": False})
        else:
            print("Error: Directory is not a git repository.", file=sys.stderr)
        return 1

    if args.suggest_next:
        suggestion = suggest_next_version(repo_dir=repo_dir)
        audit_data["suggestion"] = suggestion

    if args.json:
        _print_json(audit_data)
    else:
        print(f"Git Tag Audit for: {repo_dir}")
        print(f"  Total tags: {audit_data['total_tags']}")
        print(f"  Valid strict SemVer: {len(audit_data['valid_strict_tags'])}")
        print(f"  Valid loose SemVer:  {len(audit_data['valid_loose_tags'])}")
        print(f"  Invalid tags:        {len(audit_data['invalid_tags'])}")
        print(f"  Highest tag:         {audit_data['highest_tag'] or 'None'}")

        if audit_data["invalid_tags"]:
            print("\nInvalid Tags Found:")
            for tag in audit_data["invalid_tags"]:
                print(f"  - {tag} (fails SemVer 2.0.0)")

        if audit_data["chronology_issues"]:
            print("\nChronological Ordering Drift:")
            for issue in audit_data["chronology_issues"]:
                print(f"  - {issue['reason']}")

        if args.suggest_next and "suggestion" in audit_data:
            sug = audit_data["suggestion"]
            print(f"\nRecommended Next Version: {sug['next_version']} ({sug['bump_type']})")
            for r in sug["reasons"]:
                print(f"  - {r}")

    return 0 if audit_data["all_valid"] else 1


def handle_manifest(args: argparse.Namespace) -> int:
    """Handles the 'manifest' subcommand."""
    action = args.action
    repo_dir = args.path

    if action == "audit":
        data = audit_manifests(repo_dir)
        if args.json:
            _print_json(data)
        else:
            print(f"Manifest Audit for: {repo_dir}")
            print(f"  Manifests found: {data['manifest_count']}")
            print(f"  Consistent:      {data['consistent']}")
            print(f"  Highest version: {data['highest_version'] or 'None'}")
            if data["versions"]:
                print("  Files:")
                for f, v in data["versions"].items():
                    print(f"    - {f}: {v}")
            if data["mismatches"]:
                print("\nMismatches Detected:")
                for m in data["mismatches"]:
                    print(f"    - {m['file']}: {m['version']} (expected {m['expected']})")

        return 0 if data["consistent"] else 1

    elif action == "sync":
        target = args.version
        changes = sync_manifests(repo_dir, target_version=target, dry_run=args.dry_run)
        if args.json:
            _print_json({
                "target_version": target,
                "dry_run": args.dry_run,
                "changes": changes
            })
        else:
            action_desc = "Planned modifications" if args.dry_run else "Synchronized manifests"
            print(f"{action_desc}:")
            if not changes:
                print("  No manifest updates needed.")
            else:
                for f, details in changes.items():
                    print(f"  - {f}: {details['old_version']} -> {details['new_version']}")
        return 0

    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    """Handles the 'doctor' all-in-one check subcommand."""
    repo_dir = args.path
    manifest_data = audit_manifests(repo_dir)
    tag_data = audit_git_tags(repo_dir)
    suggestion = suggest_next_version(repo_dir=repo_dir)

    is_healthy = manifest_data["consistent"] and tag_data["all_valid"] and len(tag_data["chronology_issues"]) == 0

    report = {
        "healthy": is_healthy,
        "manifests": manifest_data,
        "tags": tag_data,
        "next_release": suggestion
    }

    if args.json:
        _print_json(report)
    else:
        status_str = "HEALTHY" if is_healthy else "ISSUES DETECTED"
        print(f"=== SemVer Doctor Health Check: [{status_str}] ===")
        print("\n[1] Manifests:")
        print(f"  Consistent: {manifest_data['consistent']}")
        for f, v in manifest_data["versions"].items():
            print(f"  - {f}: {v}")

        print("\n[2] Git Tags:")
        print(f"  Total tags: {tag_data['total_tags']}")
        print(f"  Highest tag: {tag_data['highest_tag'] or 'None'}")
        if tag_data["invalid_tags"]:
            print(f"  Invalid tags: {', '.join(tag_data['invalid_tags'])}")
        if tag_data["chronology_issues"]:
            for issue in tag_data["chronology_issues"]:
                print(f"  Chronology warning: {issue['reason']}")

        print("\n[3] Next Release Recommendation:")
        print(f"  Current tag: {suggestion['current_tag'] or 'None'}")
        print(f"  Next version: {suggestion['next_version']} ({suggestion['bump_type']})")
        for r in suggestion["reasons"]:
            print(f"  - {r}")

    return 0 if is_healthy else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semver-doctor",
        description="Production-grade Semantic Versioning (SemVer 2.0.0) linter, git tag doctor, and release bumper."
    )
    parser.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Lint / Check
    lint_parser = subparsers.add_parser("lint", aliases=["check"], help="Lint/validate SemVer version strings")
    lint_parser.add_argument("versions", nargs="*", help="Version strings to validate")
    lint_parser.add_argument("--strict", action="store_true", help="Reject 'v' prefix, enforce strict SemVer 2.0.0")
    lint_parser.add_argument("--path", default=".", help="Path to project directory for fallback checks")
    lint_parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    # Compare
    cmp_parser = subparsers.add_parser("compare", aliases=["cmp"], help="Compare two SemVer versions")
    cmp_parser.add_argument("v1", help="First version")
    cmp_parser.add_argument("v2", help="Second version")
    cmp_parser.add_argument("--strict", action="store_true", help="Enforce strict SemVer parsing")
    cmp_parser.add_argument("--json", action="store_true", help="Output comparison in JSON format")

    # Satisfies
    sat_parser = subparsers.add_parser("satisfies", help="Test if a version satisfies a range expression")
    sat_parser.add_argument("version", help="Version string to test")
    sat_parser.add_argument("range", help="SemVer range expression (e.g. '^1.2.0', '>=1.0 <2.0')")
    sat_parser.add_argument("--strict", action="store_true", help="Enforce strict SemVer parsing")
    sat_parser.add_argument("--json", action="store_true", help="Output result in JSON format")

    # Bump
    bump_parser = subparsers.add_parser("bump", help="Calculate or execute a version bump")
    bump_parser.add_argument("bump_type", nargs="?", choices=list(BUMP_TYPES), help="Bump type (major, minor, patch, prerelease, etc.)")
    bump_parser.add_argument("version", nargs="?", help="Base version to bump (optional, defaults to manifest/tag version)")
    bump_parser.add_argument("--preid", help="Prerelease identifier (e.g. alpha, beta, rc)")
    bump_parser.add_argument("--auto", action="store_true", help="Calculate bump type automatically from commit history")
    bump_parser.add_argument("--sync", action="store_true", help="Synchronize bumped version to project manifests")
    bump_parser.add_argument("--path", default=".", help="Project directory path")
    bump_parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying manifests")
    bump_parser.add_argument("--json", action="store_true", help="Output result in JSON format")

    # Sort
    sort_parser = subparsers.add_parser("sort", help="Sort version strings by SemVer precedence")
    sort_parser.add_argument("versions", nargs="+", help="Versions to sort")
    sort_parser.add_argument("-r", "--reverse", action="store_true", help="Sort in descending order")
    sort_parser.add_argument("-u", "--unique", action="store_true", help="Remove duplicate versions")
    sort_parser.add_argument("--json", action="store_true", help="Output sorted list in JSON format")

    # Tags
    tags_parser = subparsers.add_parser("tags", help="Audit git repository tags for SemVer compliance")
    tags_parser.add_argument("action", nargs="?", default="audit", choices=["audit"], help="Action to perform")
    tags_parser.add_argument("--path", default=".", help="Path to git repository")
    tags_parser.add_argument("--suggest-next", action="store_true", help="Suggest next version based on commits")
    tags_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Manifest
    manifest_parser = subparsers.add_parser("manifest", help="Audit or sync version manifests")
    manifest_parser.add_argument("action", choices=["audit", "sync"], help="Action: 'audit' or 'sync'")
    manifest_parser.add_argument("version", nargs="?", help="Target version for sync (defaults to highest found)")
    manifest_parser.add_argument("--path", default=".", help="Directory containing manifests")
    manifest_parser.add_argument("--dry-run", action="store_true", help="Preview sync modifications without writing")
    manifest_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Doctor
    doc_parser = subparsers.add_parser("doctor", help="Run full project SemVer health check")
    doc_parser.add_argument("--path", default=".", help="Project directory")
    doc_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        parser.print_help()
        return 0

    args = parser.parse_args(argv)

    if args.subcommand in ("lint", "check"):
        return handle_lint(args)
    elif args.subcommand in ("compare", "cmp"):
        return handle_compare(args)
    elif args.subcommand == "satisfies":
        return handle_satisfies(args)
    elif args.subcommand == "bump":
        return handle_bump(args)
    elif args.subcommand == "sort":
        return handle_sort(args)
    elif args.subcommand == "tags":
        return handle_tags(args)
    elif args.subcommand == "manifest":
        return handle_manifest(args)
    elif args.subcommand == "doctor":
        return handle_doctor(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
