"""Tests for SemVer parsing, comparison, and validation."""

import pytest
from semver_doctor.version import (
    SemVer,
    parse_semver,
    is_valid_semver,
    clean_semver,
    sort_versions,
)


def test_semver_basic_properties():
    v = SemVer(major=1, minor=2, patch=3)
    assert v.major == 1
    assert v.minor == 2
    assert v.patch == 3
    assert v.prerelease is None
    assert v.build is None
    assert v.core == "1.2.3"
    assert v.to_tuple() == (1, 2, 3)
    assert str(v) == "1.2.3"
    assert repr(v) == "SemVer(1.2.3)"
    assert v.is_stable is True
    assert v.is_prerelease is False


def test_semver_prerelease_and_build():
    v = SemVer(major=2, minor=0, patch=0, prerelease="alpha.1", build="exp.sha.5114f85")
    assert v.is_prerelease is True
    assert v.is_stable is False
    assert v.core == "2.0.0"
    assert str(v) == "2.0.0-alpha.1+exp.sha.5114f85"


def test_semver_invalid_negative_numbers():
    with pytest.raises(ValueError, match="must be non-negative integers"):
        SemVer(major=-1, minor=0, patch=0)

    with pytest.raises(ValueError, match="must be non-negative integers"):
        SemVer(major=1, minor=-2, patch=0)

    with pytest.raises(ValueError, match="must be non-negative integers"):
        SemVer(major=1, minor=0, patch=-3)


@pytest.mark.parametrize("valid_v", [
    "0.0.4",
    "1.2.3",
    "10.20.30",
    "1.1.2-prerelease+meta",
    "1.1.2+meta",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-0.3.7",
    "1.0.0-x.7.z.92",
    "1.0.0-alpha+001",
    "1.0.0+20130313144700",
    "1.0.0-beta+exp.sha.5114f85",
    "1.0.0+21AF26D3----117B344092BD",
])
def test_parse_valid_semver_strict(valid_v):
    assert is_valid_semver(valid_v, loose=False) is True
    parsed = parse_semver(valid_v, loose=False)
    assert str(parsed) == valid_v


@pytest.mark.parametrize("invalid_v", [
    "1",
    "1.2",
    "1.2.3.4",
    "v1.2.3",           # strict mode rejects 'v'
    "01.1.1",          # leading zero in major
    "1.02.1",          # leading zero in minor
    "1.1.03",          # leading zero in patch
    "1.2.3-01",        # leading zero in numeric prerelease
    "1.2.3-",          # empty prerelease
    "1.2.3+",          # empty build
    "1.2.3-alpha..1",  # empty dot identifier
    "1.2.3-alpha@beta",# invalid character
    "not-a-version",
    "",
])
def test_parse_invalid_semver_strict(invalid_v):
    assert is_valid_semver(invalid_v, loose=False) is False
    with pytest.raises(ValueError):
        parse_semver(invalid_v, loose=False)


def test_loose_parsing():
    assert is_valid_semver("v1.2.3", loose=True) is True
    v1 = parse_semver("v1.2.3", loose=True)
    assert str(v1) == "1.2.3"

    v2 = parse_semver("1.2", loose=True)
    assert str(v2) == "1.2.0"

    v3 = parse_semver("v2", loose=True)
    assert str(v3) == "2.0.0"

    v4 = parse_semver("V1.0.0-rc.1", loose=True)
    assert str(v4) == "1.0.0-rc.1"


def test_clean_semver():
    assert clean_semver("v1.2.3") == "1.2.3"
    assert clean_semver("  v2.0.1  ") == "2.0.1"
    assert clean_semver("1.0") == "1.0.0"
    assert clean_semver("invalid-text") is None


def test_semver_precedence_rule_11():
    # Official SemVer 2.0.0 spec precedence examples:
    # 1.0.0-alpha < 1.0.0-alpha.1 < 1.0.0-alpha.beta < 1.0.0-beta < 1.0.0-beta.2 < 1.0.0-beta.11 < 1.0.0-rc.1 < 1.0.0
    chain = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    parsed_chain = [parse_semver(x) for x in chain]

    for i in range(len(parsed_chain) - 1):
        a = parsed_chain[i]
        b = parsed_chain[i + 1]
        assert a < b
        assert a <= b
        assert b > a
        assert b >= a
        assert a != b
        assert not (a == b)
        assert not (a > b)


def test_semver_build_metadata_ignored_in_precedence():
    # 1.0.0-alpha+001 == 1.0.0-alpha+exp
    # 1.0.0+20130313144700 == 1.0.0+exp.sha.5114f85
    v1 = parse_semver("1.0.0+20130313144700")
    v2 = parse_semver("1.0.0+exp.sha.5114f85")
    assert v1 == v2
    assert not (v1 < v2)
    assert not (v1 > v2)


def test_semver_numeric_vs_alphanumeric_prerelease():
    # Numeric identifier always lower precedence than alphanumeric
    # 1.0.0-1 < 1.0.0-a
    v_num = parse_semver("1.0.0-1")
    v_alpha = parse_semver("1.0.0-a")
    assert v_num < v_alpha

    # 1.0.0-alpha.1 < 1.0.0-alpha.a
    v_num2 = parse_semver("1.0.0-alpha.1")
    v_alpha2 = parse_semver("1.0.0-alpha.a")
    assert v_num2 < v_alpha2


def test_semver_comparison_with_non_semver():
    v = parse_semver("1.2.3")
    assert v == "1.2.3"
    assert v > "1.2.2"
    assert v < "1.2.4"
    assert (v == object()) is False
    with pytest.raises(TypeError):
        _ = (v < object())


def test_sort_versions():
    raw = ["1.0.0", "0.9.0", "2.1.0", "1.0.0-alpha", "1.0.0-beta", "2.0.0", "invalid"]
    sorted_asc = sort_versions(raw, reverse=False)
    assert sorted_asc == ["0.9.0", "1.0.0-alpha", "1.0.0-beta", "1.0.0", "2.0.0", "2.1.0"]

    sorted_desc = sort_versions(raw, reverse=True)
    assert sorted_desc == ["2.1.0", "2.0.0", "1.0.0", "1.0.0-beta", "1.0.0-alpha", "0.9.0"]
