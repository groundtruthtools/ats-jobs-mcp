"""server.json, pyproject.toml and the README must agree.

The registry hosts metadata only and verifies ownership by finding an
mcp-name marker in the package README, which becomes the PyPI description. If
those three drift apart the publish fails in CI, which is a slow way to learn
something a test can say in a millisecond.
"""
import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent

SERVER = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
PYPROJECT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
VERSION = re.search(r'^version\s*=\s*"([^"]+)"', PYPROJECT, re.M).group(1)


def test_server_json_version_matches_the_package():
    assert SERVER["version"] == VERSION


def test_every_package_entry_matches_the_package():
    for package in SERVER["packages"]:
        assert package["version"] == VERSION, package


def test_the_package_name_matches_what_pypi_holds():
    name = re.search(r'^name\s*=\s*"([^"]+)"', PYPROJECT, re.M).group(1)
    for package in SERVER["packages"]:
        if package["registryType"] == "pypi":
            assert package["identifier"] == name


def test_the_readme_carries_the_ownership_marker():
    """Without this exact string the registry cannot prove we own the PyPI
    package, and the publish is refused."""
    assert f'mcp-name: {SERVER["name"]}' in README


def test_the_description_fits_the_registry_limit():
    """The registry rejects anything over 100 characters, which it does at
    publish time rather than at validate time if you are unlucky."""
    assert len(SERVER["description"]) <= 100, len(SERVER["description"])
