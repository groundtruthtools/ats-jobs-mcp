"""The vendored modules must stay byte-identical to the Apify tool's copies.

Two copies of a salary parser that quietly disagree would mean two answers to
the same question, and no way to tell from the outside which one you got. The
Apify edition is the one with the golden records against employers' own pages,
so it is the one that decides.
"""
import hashlib
import os
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / "src" / "ats_jobs_mcp"
# The Apify edition's copy of these modules, if it is available locally.
# Point ATS_UPSTREAM_CORE at it to run the parity check; without it the check
# skips, so a contributor is never blocked by a repo they cannot see.
UPSTREAM = Path(os.environ.get("ATS_UPSTREAM_CORE", "")) if os.environ.get(
    "ATS_UPSTREAM_CORE") else Path("nonexistent")

SHARED = ["ats.py", "salary.py", "directory.py",
          "listings/listing.py", "listings/adapter.py", "listings/money.py",
          "listings/units.py", "listings/paging.py", "listings/__init__.py"]


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


@pytest.mark.skipif(not UPSTREAM.is_dir(), reason="upstream toolshop not present")
@pytest.mark.parametrize("name", SHARED)
def test_vendored_module_matches_upstream(name):
    mine = PACKAGE / name
    theirs = UPSTREAM / name
    assert mine.exists(), f"{name} missing from the package"
    assert theirs.exists(), f"{name} missing upstream"
    if name == "directory.py":
        # One deliberate difference: the package keeps directory.json beside
        # the module, the Actor keeps it one level up beside main.py.
        a = mine.read_text(encoding="utf-8").replace('HERE / "directory.json"', "X")
        b = theirs.read_text(encoding="utf-8").replace('HERE.parent / "directory.json"', "X")
        assert a.replace("\r\n", "\n") == b.replace("\r\n", "\n")
        return
    assert digest(mine) == digest(theirs), f"{name} has drifted from the Apify tool"


def test_the_directory_only_lists_systems_with_an_adapter():
    import sys
    sys.path.insert(0, str(PACKAGE.parent))
    from ats_jobs_mcp.ats import SYSTEMS
    from ats_jobs_mcp.directory import Directory
    listed = set(Directory().systems)
    assert listed <= set(SYSTEMS), f"{listed - set(SYSTEMS)} have no adapter"
