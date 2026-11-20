import pytest
from update_logic import version_key, is_newer_version


@pytest.mark.unit
def test_version_key_parsing():
    assert version_key("1.2.3") == (1, 2, 3, True, "")
    assert version_key("v2.0.1") == (2, 0, 1, True, "")
    assert version_key("1.2.3-beta") == (1, 2, 3, False, "-beta")
    assert version_key("invalid") is None


@pytest.mark.unit
def test_is_newer_version_comparisons():
    # Newer major, minor, patch
    assert is_newer_version("2.0.0", "1.9.9") is True
    assert is_newer_version("1.3.0", "1.2.9") is True
    assert is_newer_version("1.2.4", "1.2.3") is True

    # Same version
    assert is_newer_version("1.2.3", "1.2.3") is False
    assert is_newer_version("1.2.3", "v1.2.3") is False

    # Stable version should be newer than pre-release of same version
    assert is_newer_version("1.2.0", "1.2.0-beta") is True
    assert is_newer_version("1.2.0-beta", "1.2.0") is False

    # Newer patch vs older pre-release
    assert is_newer_version("1.2.1-beta", "1.2.0") is True
