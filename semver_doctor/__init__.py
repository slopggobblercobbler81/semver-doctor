"""semver-doctor: Production-grade SemVer 2.0.0 linter, git tag doctor, and release bumper."""

from semver_doctor.__version__ import __version__, __author__, __license__
from semver_doctor.version import (
    SemVer,
    parse_semver,
    is_valid_semver,
    clean_semver,
    sort_versions,
)
from semver_doctor.range_matcher import (
    satisfies,
)
from semver_doctor.bumper import (
    bump_version,
    analyze_conventional_commits,
    BUMP_TYPES,
)
from semver_doctor.manifest import (
    read_manifest_version,
    write_manifest_version,
    find_manifest_files,
    audit_manifests,
    sync_manifests,
)
from semver_doctor.git_doctor import (
    is_git_repository,
    get_git_tags,
    audit_git_tags,
    get_commits_since_last_tag,
    suggest_next_version,
)

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "SemVer",
    "parse_semver",
    "is_valid_semver",
    "clean_semver",
    "sort_versions",
    "satisfies",
    "bump_version",
    "analyze_conventional_commits",
    "BUMP_TYPES",
    "read_manifest_version",
    "write_manifest_version",
    "find_manifest_files",
    "audit_manifests",
    "sync_manifests",
    "is_git_repository",
    "get_git_tags",
    "audit_git_tags",
    "get_commits_since_last_tag",
    "suggest_next_version",
]
