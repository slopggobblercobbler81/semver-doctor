"""Tests for SemVer range expression evaluator."""

import pytest
from semver_doctor.range_matcher import satisfies
from semver_doctor.version import parse_semver


def test_satisfies_wildcard():
    assert satisfies("1.2.3", "*") is True
    assert satisfies("1.2.3", "") is True
    assert satisfies("1.2.3", "x") is True
    assert satisfies("1.2.3", "X") is True
    assert satisfies("1.2.3", "1.x") is True
    assert satisfies("2.0.0", "1.x") is False
    assert satisfies("1.2.3", "1.2.*") is True
    assert satisfies("1.3.0", "1.2.*") is False


def test_satisfies_exact_and_operators():
    assert satisfies("1.2.3", "=1.2.3") is True
    assert satisfies("1.2.3", "==1.2.3") is True
    assert satisfies("1.2.3", "1.2.3") is True
    assert satisfies("1.2.4", "1.2.3") is False
    assert satisfies("1.2.4", "!=1.2.3") is True
    assert satisfies("1.2.3", "!=1.2.3") is False

    assert satisfies("1.2.4", ">1.2.3") is True
    assert satisfies("1.2.3", ">1.2.3") is False
    assert satisfies("1.2.3", ">=1.2.3") is True
    assert satisfies("1.2.2", "<1.2.3") is True
    assert satisfies("1.2.3", "<=1.2.3") is True


def test_satisfies_caret():
    # ^1.2.3 := >=1.2.3 <2.0.0
    assert satisfies("1.2.3", "^1.2.3") is True
    assert satisfies("1.9.9", "^1.2.3") is True
    assert satisfies("2.0.0", "^1.2.3") is False
    assert satisfies("1.2.2", "^1.2.3") is False

    # ^0.2.3 := >=0.2.3 <0.3.0
    assert satisfies("0.2.3", "^0.2.3") is True
    assert satisfies("0.2.9", "^0.2.3") is True
    assert satisfies("0.3.0", "^0.2.3") is False

    # ^0.0.3 := >=0.0.3 <0.0.4
    assert satisfies("0.0.3", "^0.0.3") is True
    assert satisfies("0.0.4", "^0.0.3") is False

    # ^1 := >=1.0.0 <2.0.0
    assert satisfies("1.5.0", "^1") is True
    assert satisfies("2.0.0", "^1") is False

    # ^0 := >=0.0.0 <1.0.0
    assert satisfies("0.5.0", "^0") is True
    assert satisfies("1.0.0", "^0") is False


def test_satisfies_tilde():
    # ~1.2.3 := >=1.2.3 <1.3.0
    assert satisfies("1.2.3", "~1.2.3") is True
    assert satisfies("1.2.9", "~1.2.3") is True
    assert satisfies("1.3.0", "~1.2.3") is False
    assert satisfies("1.2.2", "~1.2.3") is False

    # ~1.2 := >=1.2.0 <1.3.0
    assert satisfies("1.2.5", "~1.2") is True
    assert satisfies("1.3.0", "~1.2") is False

    # ~1 := >=1.0.0 <2.0.0
    assert satisfies("1.9.9", "~1") is True
    assert satisfies("2.0.0", "~1") is False


def test_satisfies_hyphen_range():
    # 1.2.3 - 2.3.4 := >=1.2.3 <=2.3.4
    assert satisfies("1.2.3", "1.2.3 - 2.3.4") is True
    assert satisfies("2.0.0", "1.2.3 - 2.3.4") is True
    assert satisfies("2.3.4", "1.2.3 - 2.3.4") is True
    assert satisfies("1.2.2", "1.2.3 - 2.3.4") is False
    assert satisfies("2.3.5", "1.2.3 - 2.3.4") is False


def test_satisfies_and_ranges():
    assert satisfies("1.5.0", ">=1.0.0 <2.0.0") is True
    assert satisfies("0.9.9", ">=1.0.0 <2.0.0") is False
    assert satisfies("2.0.0", ">=1.0.0 <2.0.0") is False

    # Spaces between operator and version
    assert satisfies("1.5.0", ">= 1.0.0 < 2.0.0") is True
    assert satisfies("1.2.3", "= 1.2.3") is True


def test_satisfies_or_ranges():
    assert satisfies("1.2.3", "^1.0.0 || ^3.0.0") is True
    assert satisfies("3.5.0", "^1.0.0 || ^3.0.0") is True
    assert satisfies("2.5.0", "^1.0.0 || ^3.0.0") is False


def test_satisfies_with_semver_object():
    sv = parse_semver("1.2.3")
    assert satisfies(sv, "^1.0.0") is True


def test_invalid_comparator():
    with pytest.raises(ValueError):
        satisfies("1.0.0", "invalid_range_symbol_123")
