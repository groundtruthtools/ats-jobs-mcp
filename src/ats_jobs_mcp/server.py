"""Standalone MCP server: open jobs, read from the employer's own careers system.

A second distribution channel for the same logic that runs on Apify. This one
is found in MCP registries rather than the Apify Store, runs on the user's own
machine, and costs nothing to anyone.

The parsing lives in `ats.py`, `salary.py` and `directory.py`, byte-identical
to the Apify tool's copies -- `tests/test_core_parity.py` fails if they drift.

Nothing here scrapes. Greenhouse, Ashby and Workable each publish a job board
API so that third parties can build job sites from their customers' openings,
and this reads those. No key, no login, no bot protection to work around.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from typing import Annotated

import certifi
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .ats import SYSTEMS, BoardError, parse_target
from .directory import Directory

TIMEOUT = 60
CTX = ssl.create_default_context(cafile=certifi.where())
UA = "ats-jobs-mcp (+https://github.com/groundtruthtools/ats-jobs-mcp)"

DIRECTORY = Directory()
# Derived from SYSTEMS, never written out: naming a system with no
# adapter is how the Apify edition shipped a KeyError for a while.
_PREFERRED = ("greenhouse", "ashby", "workable", "lever")
DETECT_ORDER = tuple(n for n in _PREFERRED if n in SYSTEMS) + tuple(
    sorted(set(SYSTEMS) - set(_PREFERRED)))

mcp = MCPServer(
    name="ats-jobs",
    instructions=(
        "Open job postings, read first-hand from the applicant-tracking system "
        "behind a company's careers page: Greenhouse, Ashby, Lever or Workable. "
        f"Ships a directory of {len(DIRECTORY):,} company job boards, so a "
        "company can be named rather than looked up by URL. "
        "Salary ranges are parsed into numbers where the employer publishes "
        "them, and refused rather than guessed where they are ambiguous. "
        "Every posting carries verify_url pointing at the employer's own "
        "advert, so anything reported to a user can be checked at the source. "
        "No personal data: recruiter names are never returned, and email "
        "addresses and phone numbers are removed from job descriptions."
    ),
)


def fetch(url: str) -> dict:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=CTX) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def read_board(system, board: str):
    payload = fetch(system.board_url(board))
    if system.crawl_delay:
        time.sleep(system.crawl_delay)
    return payload


def resolve(entry: str):
    """(system, board, payload) for one company, or raise ValueError."""
    site, board = parse_target(entry)

    if site is None:
        for row in DIRECTORY.resolve(board):
            if row["ats"] in SYSTEMS:
                try:
                    return row["ats"], row["board"], read_board(SYSTEMS[row["ats"]], row["board"])
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
                    break
        tried = []
        for name in DETECT_ORDER:
            try:
                return name, board, read_board(SYSTEMS[name], board)
            except urllib.error.HTTPError as e:
                tried.append(f"{name} {e.code}")
            except (urllib.error.URLError, TimeoutError) as e:
                tried.append(f"{name} {e}")
        raise ValueError(
            f"'{board}' was not found on {', '.join(DETECT_ORDER)} "
            f"({'; '.join(tried)}). Try find_company_board first, or give the "
            f"careers URL."
        )

    try:
        return site, board, read_board(SYSTEMS[site], board)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"{site} has no board called '{board}'") from None
        raise ValueError(f"{site} returned HTTP {e.code} for '{board}'") from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise ValueError(f"could not reach {site}: {e}") from None


@mcp.tool()
def find_company_board(
    company: Annotated[str, Field(
        description="Company name or board name, for example 'anthropic' or "
                    "'1Password'. Case and punctuation do not matter.")],
    limit: Annotated[int, Field(
        description="Maximum matches to return.", ge=1, le=100)] = 10,
) -> dict:
    """Find which applicant-tracking system a company's careers page runs on.

    Greenhouse, Ashby, Lever and Workable all publish open job board APIs, and
    all of them are unusable unless you already know the company's board name.
    None of them publishes a directory of its customers, and none could, since
    no vendor knows about the others.

    Use this first when you have a company name rather than a careers URL.
    """
    hits = DIRECTORY.search(company, limit=limit)
    return {
        "query": company,
        "directory_size": len(DIRECTORY),
        "matches": [
            {"company": row.get("company") or row["board"],
             "ats": row["ats"],
             "board": row["board"],
             "open_jobs_when_checked": row.get("jobs"),
             "checked": row["checked"]}
            for row in hits
        ],
        "note": (
            "Job counts are a snapshot from when the board was confirmed and go "
            "stale within a day. Call list_open_jobs for what is open now."
            if hits else
            f"No match in the directory of {len(DIRECTORY):,} boards. The "
            f"company may use a system this does not read, or a board name "
            f"unlike its trading name. list_open_jobs also accepts a careers URL."
        ),
    }


@mcp.tool()
def list_open_jobs(
    company: Annotated[str, Field(
        description="A company's board name ('stripe'), a careers URL "
                    "('https://jobs.ashbyhq.com/ramp'), or system:name "
                    "('ashby:ramp').")],
    limit: Annotated[int, Field(
        description="Maximum postings to return.", ge=1, le=1000)] = 50,
    include_description: Annotated[bool, Field(
        description="Include the full job description. Off by default because "
                    "descriptions are long; email addresses and phone numbers "
                    "are removed from them either way.")] = False,
) -> dict:
    """Every open job at one company, read from its own careers system.

    Returns title, department, location, employment type, workplace type,
    posted date, a parsed salary range where the employer publishes one, and a
    verify_url pointing at the employer's own advert.

    Salaries are refused rather than guessed: an hourly rate, an ambiguous
    currency, or bands in two currencies all yield no figure, and salary_text
    keeps whatever the employer actually wrote.
    """
    try:
        site, board, payload = resolve(company)
    except (BoardError, ValueError) as e:
        return {"error": str(e), "jobs": []}

    system = SYSTEMS[site]
    records = system.parse_page(payload, board, include_description)
    total = len(records)
    return {
        "company": records[0]["company"] if records else board,
        "ats": site,
        "board": board,
        "open_jobs": total,
        "returned": min(total, limit),
        "jobs": records[:limit],
        "attribution": system.attribution,
        "note": ("This company's board is live and currently has no open "
                 "postings. That is an answer, not a failure."
                 if total == 0 else None),
    }


@mcp.tool()
def compare_companies(
    companies: Annotated[list[str], Field(
        description="Up to 20 company board names or careers URLs.")],
    per_company: Annotated[int, Field(
        description="Maximum postings per company.", ge=1, le=200)] = 25,
) -> dict:
    """Open jobs across several companies at once, in one schema.

    This is the thing no single applicant-tracking system can do: each vendor
    only knows about its own customers. Companies on different systems come
    back with the same field names, so they can be compared directly.

    One company failing does not lose the others; each failure is reported
    beside the results that did work.
    """
    if not companies:
        return {"error": "give at least one company", "jobs": []}
    if len(companies) > 20:
        return {"error": f"{len(companies)} companies given, the maximum is 20",
                "jobs": []}

    jobs, failures, seen = [], [], set()
    for entry in companies:
        try:
            site, board, payload = resolve(entry)
        except (BoardError, ValueError) as e:
            failures.append({"company": entry, "reason": str(e)})
            continue
        if (site, board) in seen:
            continue
        seen.add((site, board))
        records = SYSTEMS[site].parse_page(payload, board, False)
        jobs.extend(records[:per_company])

    return {
        "companies_requested": len(companies),
        "companies_read": len(seen),
        "jobs": jobs,
        "total_returned": len(jobs),
        "failures": failures,
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
