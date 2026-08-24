"""The board directory: which company is on which applicant-tracking system.

This is the half the vendors do not supply. Greenhouse, Lever, Ashby and
Workable all publish open, documented job board APIs, and all four are
unusable unless you already know that Anthropic's Greenhouse board is
`anthropic` and Ramp's Ashby board is `ramp`. None of them publishes a
directory of its customers: verified 2026-08-24, `sitemap.xml` on
job-boards.greenhouse.io, boards.greenhouse.io, jobs.lever.co and
apply.workable.com all 404 or redirect.

No single vendor could supply it either, because no vendor knows about the
others. That is the SELECTION-CRITERIA.md gate: a question the official
sources cannot answer, rather than a rebuild of one that they can.

Every row was confirmed against the vendor's own API on the date it carries.
See SOURCES.md for how the candidates were found and why none of that
provenance reaches a customer.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "directory.json"


def _normalise(text: str) -> str:
    """Fold a company name and a board slug onto common ground.

    `1Password`, `1password` and `1-password` are one company written three
    ways, and a caller types whichever they have.
    """
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


class Directory:
    """Loaded once. Small enough to hold in memory, large enough to matter."""

    def __init__(self, path: Path | None = None):
        self.rows: list[dict] = []
        self.by_board: dict[str, list[dict]] = {}
        self._index: list[tuple[str, str, dict]] = []
        source = path or DATA
        if not source.exists():
            return
        payload = json.loads(source.read_text(encoding="utf-8"))
        self.rows = payload.get("boards") or []
        for row in self.rows:
            key = _normalise(row["board"])
            self.by_board.setdefault(key, []).append(row)
            self._index.append((key, _normalise(row.get("company") or ""), row))

    def __len__(self) -> int:
        return len(self.rows)

    @property
    def systems(self) -> dict:
        counted: dict[str, int] = {}
        for row in self.rows:
            counted[row["ats"]] = counted.get(row["ats"], 0) + 1
        return counted

    def resolve(self, board: str) -> list[dict]:
        """Which systems host a board of this name.

        Usually one. Occasionally a company keeps boards on two systems during
        a migration, and returning both is more honest than picking.
        """
        return list(self.by_board.get(_normalise(board), []))

    def search(self, query: str, limit: int = 50) -> list[dict]:
        """Find boards by company name or board name.

        Exact matches first, then prefix, then substring. A caller who types
        `stripe` wants Stripe, not `stripe-partners-emea`, and ranking is the
        difference between a useful answer and a haystack.
        """
        needle = _normalise(query)
        if not needle:
            return []
        exact, prefix, contains = [], [], []
        for board_key, company_key, row in self._index:
            if needle in (board_key, company_key):
                exact.append(row)
            elif board_key.startswith(needle) or company_key.startswith(needle):
                prefix.append(row)
            elif needle in board_key or needle in company_key:
                contains.append(row)
        out, seen = [], set()
        for row in exact + prefix + contains:
            key = (row["ats"], row["board"])
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
            if len(out) >= limit:
                break
        return out


def problems(payload: dict) -> list[str]:
    """Everything wrong with a directory file. Empty list means valid."""
    found = []
    rows = payload.get("boards")
    if not isinstance(rows, list):
        return ["boards: must be a list"]
    seen = set()
    for index, row in enumerate(rows):
        where = f"row {index}"
        if not isinstance(row, dict):
            found.append(f"{where}: not an object")
            continue
        for field in ("ats", "board", "checked"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                found.append(f"{where}: {field} is required")
        key = (row.get("ats"), row.get("board"))
        if key in seen:
            found.append(f"{where}: {key} appears twice")
        seen.add(key)
        jobs = row.get("jobs")
        if jobs is not None and (isinstance(jobs, bool) or not isinstance(jobs, int)
                                 or jobs < 0):
            found.append(f"{where}: jobs must be a non-negative whole number or null")
    return found
