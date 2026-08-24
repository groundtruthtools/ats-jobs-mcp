"""Generic page driver for listing feeds.

Pure: the caller injects a fetch function, exactly as the USAspending tool
injects fetch_page into core.expiry. That keeps every stopping rule testable
offline with a fake fetcher.

The stopping rules exist because a paging bug on a paid tool bills the
customer for pages nobody asked for. Every run reports why it stopped.
"""

MAX_PAGES_DEFAULT = 200


def collect(
    fetch_page,
    parse_page,
    limit: int,
    max_pages: int = MAX_PAGES_DEFAULT,
    key: str = "listing_id",
) -> tuple[list[dict], dict]:
    """Page until `limit` records, an empty page, or `max_pages`.

    fetch_page(page) -> raw rows for that page, 0-indexed.
    parse_page(rows) -> canonical records.

    Returns (records, stats). Stats names the stop reason in plain language so
    the run log explains itself without anyone reading code.
    """
    records: list[dict] = []
    seen: set = set()
    pages_read = 0
    duplicates = 0
    empty_page_at = None
    stopped = "reached the requested number of listings"

    for page in range(max_pages):
        rows = fetch_page(page)
        pages_read += 1

        if not rows:
            empty_page_at = page
            stopped = "the site returned no more listings"
            break

        parsed = parse_page(rows)

        # A page of rows that all fail to parse is the signature of a site
        # markup change. Report it rather than treating it as "no results",
        # which is the silent-breakage failure mode the monitor exists to catch.
        if rows and not parsed:
            stopped = (
                "a page of listings could not be read, which usually means the "
                "site changed its markup"
            )
            break

        new_on_page = 0
        for record in parsed:
            identity = record.get(key)
            if identity is not None:
                if identity in seen:
                    duplicates += 1
                    continue
                seen.add(identity)
            records.append(record)
            new_on_page += 1
            if len(records) >= limit:
                break

        if len(records) >= limit:
            break

        # Every row already seen means the site is serving the same page
        # again, which is how an offset bug turns into an infinite loop.
        if new_on_page == 0:
            stopped = "the site repeated a page it had already returned"
            break
    else:
        stopped = f"reached the {max_pages}-page ceiling"

    return records[:limit], {
        "pages_read": pages_read,
        "records": len(records[:limit]),
        "duplicates_skipped": duplicates,
        "empty_page_at": empty_page_at,
        "stopped_because": stopped,
    }
