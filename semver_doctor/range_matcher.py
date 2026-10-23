"""SemVer range expression parsing and evaluation engine."""

from __future__ import annotations
import re
from typing import List, Callable, Union
from semver_doctor.version import SemVer, parse_semver

ComparatorFn = Callable[[SemVer], bool]

def _parse_simple_comparator(comp_str: str) -> ComparatorFn:
    comp_str = comp_str.strip()
    if not comp_str or comp_str in ("*", "x", "X"):
        return lambda v: True

    # Check Caret ^
    if comp_str.startswith("^"):
        target_str = comp_str[1:].strip()
        target = parse_semver(target_str, loose=True)
        if target.major > 0:
            upper = SemVer(major=target.major + 1, minor=0, patch=0)
        elif target.minor > 0:
            upper = SemVer(major=0, minor=target.minor + 1, patch=0)
        else:
            # Check if patch was explicitly specified as 0 or missing
            dots = target_str.lstrip("vV").count(".")
            if dots == 0:
                # ^0 means <1.0.0
                upper = SemVer(major=1, minor=0, patch=0)
            elif dots == 1 and target.patch == 0:
                # ^0.0 means <0.1.0
                upper = SemVer(major=0, minor=1, patch=0)
            else:
                upper = SemVer(major=0, minor=0, patch=target.patch + 1)
        return lambda v: (v >= target and v < upper)

    # Check Tilde ~
    if comp_str.startswith("~"):
        target_str = comp_str[1:].strip()
        target = parse_semver(target_str, loose=True)
        clean_target = target_str.lstrip("vV")
        dots = clean_target.count(".")
        if dots == 0:
            # ~1 matches >=1.0.0 <2.0.0
            upper = SemVer(major=target.major + 1, minor=0, patch=0)
        else:
            # ~1.2 or ~1.2.3 matches >=target <(major.minor+1.0)
            upper = SemVer(major=target.major, minor=target.minor + 1, patch=0)
        return lambda v: (v >= target and v < upper)

    # Check Wildcard patterns like 1.x, 1.*, 1.2.x, 1.2.*
    m_wild = re.match(r"^(\d+)\.(x|\*)$", comp_str, re.IGNORECASE)
    if m_wild:
        maj = int(m_wild.group(1))
        return lambda v: (v.major == maj)

    m_wild2 = re.match(r"^(\d+)\.(\d+)\.(x|\*)$", comp_str, re.IGNORECASE)
    if m_wild2:
        maj = int(m_wild2.group(1))
        min_v = int(m_wild2.group(2))
        return lambda v: (v.major == maj and v.minor == min_v)

    # Standard operators: >=, <=, >, <, !=, =, ==, or bare version
    op_match = re.match(r"^(>=|<=|>|<|!=|==|=)?\s*(.*)$", comp_str)
    if op_match:
        op = op_match.group(1) or "="
        target_str = op_match.group(2).strip()
        if not target_str:
            raise ValueError(f"Empty version target in comparator: '{comp_str}'")
        target = parse_semver(target_str, loose=True)

        if op in ("=", "=="):
            return lambda v: v == target
        elif op == "!=":
            return lambda v: v != target
        elif op == ">":
            return lambda v: v > target
        elif op == ">=":
            return lambda v: v >= target
        elif op == "<":
            return lambda v: v < target
        elif op == "<=":
            return lambda v: v <= target

    raise ValueError(f"Unrecognized comparator: '{comp_str}'")


def _parse_and_set(set_str: str) -> List[ComparatorFn]:
    """Parse space-separated comparators within an AND clause (e.g. '>=1.0.0 <2.0.0')."""
    s = set_str.strip()
    if not s:
        return [lambda v: True]

    # Check for hyphen range: 1.2.3 - 2.3.4
    hyphen_match = re.match(r"^\s*([vV]?\d+(?:\.[0-9a-zA-Z.-]+)*)\s+-\s+([vV]?\d+(?:\.[0-9a-zA-Z.-]+)*)\s*$", s)
    if hyphen_match:
        lower = parse_semver(hyphen_match.group(1), loose=True)
        upper = parse_semver(hyphen_match.group(2), loose=True)
        return [lambda v: v >= lower, lambda v: v <= upper]

    # Normalize spaces after operators, e.g. ">= 1.0.0" -> ">=1.0.0"
    normalized = re.sub(r'(>=|<=|>|<|!=|==|=|\^|~)\s+', r'\1', s)
    parts = re.split(r"\s+", normalized.strip())
    comparators: List[ComparatorFn] = []
    for part in parts:
        if part:
            comparators.append(_parse_simple_comparator(part))
    return comparators


def satisfies(version: Union[str, SemVer], range_expr: str, loose: bool = True) -> bool:
    """Evaluate whether version satisfies the given range expression."""
    if not range_expr or range_expr.strip() in ("", "*"):
        return True

    if not isinstance(version, SemVer):
        version = parse_semver(version, loose=loose)

    # Range expression may contain OR sets: 'expr1 || expr2'
    or_clauses = [clause.strip() for clause in range_expr.split("||")]

    for clause in or_clauses:
        comparators = _parse_and_set(clause)
        # All comparators in this AND clause must match
        if all(comp(version) for comp in comparators):
            return True

    return False
