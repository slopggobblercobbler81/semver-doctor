"""Semantic Versioning (SemVer 2.0.0) parser, comparator, and validator."""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Tuple, Union, List, Any

# Official SemVer 2.0.0 Regular Expression from semver.org
SEMVER_REGEX = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

# Coercion regex for lenient parsing (e.g. v1.2, 1.2, etc.)
COERCE_REGEX = re.compile(
    r"^[vV]?\s*(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?"
    r"(?:-(?P<prerelease>[0-9a-zA-Z.-]+))?(?:\+(?P<buildmetadata>[0-9a-zA-Z.-]+))?$"
)

@dataclass(frozen=True)
class SemVer:
    """Represents a SemVer 2.0.0 compliant version."""
    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None
    build: Optional[str] = None

    def __post_init__(self):
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError("Version numbers (major, minor, patch) must be non-negative integers.")

    @property
    def is_prerelease(self) -> bool:
        return self.prerelease is not None and len(self.prerelease) > 0

    @property
    def is_stable(self) -> bool:
        return self.major >= 1 and not self.is_prerelease

    @property
    def core(self) -> str:
        """Returns MAJOR.MINOR.PATCH without prerelease or build metadata."""
        return f"{self.major}.{self.minor}.{self.patch}"

    def to_tuple(self) -> Tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        res = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            res += f"-{self.prerelease}"
        if self.build:
            res += f"+{self.build}"
        return res

    def __repr__(self) -> str:
        return f"SemVer({self.__str__()})"

    def _parsed_prerelease_identifiers(self) -> List[Union[int, str]]:
        if not self.prerelease:
            return []
        parts = self.prerelease.split(".")
        result: List[Union[int, str]] = []
        for p in parts:
            if p.isdigit():
                result.append(int(p))
            else:
                result.append(p)
        return result

    def _cmp_key(self) -> Tuple[int, int, int, int, List[Union[int, str]]]:
        # SemVer 2.0.0 Rule 11:
        # Normal version has higher precedence than a pre-release version:
        # e.g., 1.0.0 > 1.0.0-alpha.
        # We encode: has_prerelease=1 if prerelease is None else 0.
        is_normal = 1 if self.prerelease is None else 0
        return (self.major, self.minor, self.patch, is_normal, self._parsed_prerelease_identifiers())

    def _compare(self, other: Any) -> int:
        if not isinstance(other, SemVer):
            try:
                other = parse_semver(str(other))
            except Exception:
                return NotImplemented

        # 1. Compare major, minor, patch
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            if (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch):
                return -1
            return 1

        # 2. Compare prerelease existence
        if self.prerelease is None and other.prerelease is None:
            return 0
        if self.prerelease is None and other.prerelease is not None:
            return 1  # 1.0.0 > 1.0.0-alpha
        if self.prerelease is not None and other.prerelease is None:
            return -1 # 1.0.0-alpha < 1.0.0

        # 3. Compare prerelease identifiers step by step
        self_parts = self._parsed_prerelease_identifiers()
        other_parts = other._parsed_prerelease_identifiers()
        min_len = min(len(self_parts), len(other_parts))

        for i in range(min_len):
            s = self_parts[i]
            o = other_parts[i]
            if s == o:
                continue

            # Identifiers consisting of only digits are compared numerically
            # Identifiers with letters/hyphens are compared lexically
            # Numeric identifiers always have lower precedence than non-numeric identifiers
            if isinstance(s, int) and isinstance(o, int):
                return -1 if s < o else 1
            elif isinstance(s, int) and isinstance(o, str):
                return -1
            elif isinstance(s, str) and isinstance(o, int):
                return 1
            else: # both str
                return -1 if s < o else 1

        # A larger set of pre-release fields has a higher precedence than a smaller set
        if len(self_parts) < len(other_parts):
            return -1
        elif len(self_parts) > len(other_parts):
            return 1

        return 0

    def __eq__(self, other: Any) -> bool:
        cmp = self._compare(other)
        if cmp is NotImplemented:
            return False
        return cmp == 0

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: Any) -> bool:
        cmp = self._compare(other)
        if cmp is NotImplemented:
            return NotImplemented
        return cmp < 0

    def __le__(self, other: Any) -> bool:
        cmp = self._compare(other)
        if cmp is NotImplemented:
            return NotImplemented
        return cmp <= 0

    def __gt__(self, other: Any) -> bool:
        cmp = self._compare(other)
        if cmp is NotImplemented:
            return NotImplemented
        return cmp > 0

    def __ge__(self, other: Any) -> bool:
        cmp = self._compare(other)
        if cmp is NotImplemented:
            return NotImplemented
        return cmp >= 0


def parse_semver(version_str: str, loose: bool = False) -> SemVer:
    """Parse a version string into a SemVer object.
    
    If loose=True, strips leading 'v'/'V' and fills missing minor/patch.
    """
    cleaned = version_str.strip()
    if loose:
        if cleaned.startswith(("v", "V")):
            cleaned = cleaned[1:].strip()

    m = SEMVER_REGEX.match(cleaned)
    if m:
        major = int(m.group("major"))
        minor = int(m.group("minor"))
        patch = int(m.group("patch"))
        prerelease = m.group("prerelease")
        build = m.group("buildmetadata")
        return SemVer(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)

    if loose:
        m2 = COERCE_REGEX.match(cleaned)
        if m2:
            major = int(m2.group("major"))
            minor = int(m2.group("minor") or 0)
            patch = int(m2.group("patch") or 0)
            prerelease = m2.group("prerelease")
            build = m2.group("buildmetadata")
            return SemVer(major=major, minor=minor, patch=patch, prerelease=prerelease, build=build)

    raise ValueError(f"Invalid SemVer 2.0.0 string: '{version_str}'")


def is_valid_semver(version_str: str, loose: bool = False) -> bool:
    """Validate whether a version string complies with SemVer 2.0.0."""
    try:
        parse_semver(version_str, loose=loose)
        return True
    except (ValueError, TypeError):
        return False


def clean_semver(version_str: str) -> Optional[str]:
    """Clean a version string (e.g. 'v1.2.3' -> '1.2.3'). Returns None if unparseable."""
    try:
        v = parse_semver(version_str, loose=True)
        return str(v)
    except Exception:
        return None


def sort_versions(versions: List[str], reverse: bool = False, loose: bool = True) -> List[str]:
    """Sort a list of version strings according to SemVer 2.0.0 precedence."""
    parsed = []
    for v in versions:
        try:
            parsed.append((parse_semver(v, loose=loose), v))
        except ValueError:
            pass
    parsed.sort(key=lambda item: item[0], reverse=reverse)
    return [item[1] for item in parsed]
