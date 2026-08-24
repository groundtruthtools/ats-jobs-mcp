"""Adapters for applicant-tracking systems, one class per vendor.

Every endpoint here is one the vendor publishes so that third parties can
build job sites out of their customers' openings. That is the vendor's stated
purpose, not an inference, and it is recorded with the words and the date in
SOURCES.md. Nothing here interprets a terms page, works around bot protection,
or needs an account.

**SmartRecruiters is deliberately absent.** Its API host answers
`robots.txt` with `User-agent: LinkedInBot / Allow: /v1/companies/` followed by
`User-agent: * / Disallow: /`. LinkedIn is permitted by name and everyone else
is refused. That is an explicit no, so there is no SmartRecruiters adapter.

What is never mapped, from any vendor: **the hiring contact.** Several systems
attach a recruiter to a posting, with a name and often an email address. A job
aggregator does not need one, and the record schema refuses the fields.
"""

import html
import re
from datetime import datetime, timezone

from .listings import listing
from .listings.adapter import Adapter
from .salary import parse_range


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _nested(node, *path):
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"[ \t ]+")
_BLANK = re.compile(r"\n{3,}")

# A job description is free text written by a human, and humans put their
# colleagues' contact details in it. "Questions? Ask jane.doe@acme.com" is a
# named individual's work address, and republishing a column of those is the
# thing this whole portfolio refuses to become. The field-name rule in
# listing.py cannot catch it, because the field is called `description_text`,
# so the value is cleaned instead.
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<![\w])\+?\d[\d\s().-]{7,}\d(?![\w])")


def to_plain_text(value, redact: bool = True) -> str | None:
    """HTML to readable text, with contact details removed."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = html.unescape(value)
    text = re.sub(r"<\s*(br|/p|/div|/li|/h[1-6])\s*/?>", "\n", text, flags=re.I)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    if redact:
        text = _EMAIL.sub("[email removed]", text)
        text = _PHONE.sub("[phone removed]", text)
    text = _WS.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _BLANK.sub("\n\n", text).strip()
    return text or None


def _iso_date(value):
    """Every vendor dates a posting differently. Return YYYY-MM-DD or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Lever counts in milliseconds since the epoch. A seconds value would
        # land in 1970, so anything that small is refused rather than shifted.
        if value < 1_000_000_000_000:
            return None
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).date().isoformat()
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip()
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    try:
        from datetime import date
        return date.fromisoformat(candidate[:10]).isoformat()
    except ValueError:
        return None


# One vocabulary out of five. Every vendor spells these differently and a
# caller comparing boards needs eight buckets, not forty.
EMPLOYMENT = {
    "fulltime": "full_time", "full_time": "full_time", "full-time": "full_time",
    "full time": "full_time", "permanent": "full_time", "regular": "full_time",
    "parttime": "part_time", "part_time": "part_time", "part-time": "part_time",
    "part time": "part_time",
    "contract": "contract", "contractor": "contract", "consultant": "contract",
    "freelance": "contract", "b2b": "contract",
    "temporary": "temporary", "temp": "temporary", "seasonal": "temporary",
    "intern": "internship", "internship": "internship", "interim": "temporary",
    "working student": "internship", "student": "internship",
    "apprentice": "apprenticeship", "apprenticeship": "apprenticeship",
    "trainee": "apprenticeship",
    "volunteer": "volunteer",
}

WORKPLACE = {
    "onsite": "on_site", "on-site": "on_site", "on site": "on_site",
    "office": "on_site", "in office": "on_site",
    "remote": "remote", "fully remote": "remote",
    "hybrid": "hybrid",
}


def normalise_employment(value):
    key = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    key = re.sub(r"\s+", " ", key)
    direct = EMPLOYMENT.get(key) or EMPLOYMENT.get(key.replace(" ", ""))
    if direct:
        return direct
    return "other" if key else None


def normalise_workplace(value, is_remote=None):
    key = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    found = WORKPLACE.get(key) or WORKPLACE.get(key.replace(" ", ""))
    if found:
        return found
    if is_remote is True:
        return "remote"
    return "unknown" if not key else "unknown"


class Ats(Adapter):
    """Shared behaviour. Subclasses set the identity and implement parse_one."""

    kind = "job"
    country = "XX"          # a board's openings can be anywhere in the world
    licence = ""
    attribution = ""
    # Seconds to wait between requests. Lever's robots.txt asks for one.
    crawl_delay = 0.0

    def board_url(self, board: str) -> str:
        raise NotImplementedError

    def rows_from(self, payload) -> list:
        raise NotImplementedError

    def company_from(self, payload, board: str) -> str:
        """The employer's name, as good as this system will give it.

        **Only Greenhouse publishes a display name.** Lever and Ashby serve
        postings without one, so for those two `company` is the board slug:
        `spotify`, not `Spotify`. That is the truth of what the API returns,
        and inventing capitalisation from a slug would turn `openai` into
        `Openai`. The slug still identifies the employer exactly, which is
        what a machine consumer needs; `verify_url` shows a person the
        properly written name.
        """
        return board

    def prepare(self, row: dict, board: str, company: str) -> dict:
        """Carry the board identity into a row, the way VIES carries country."""
        row = dict(row)
        row["_board"], row["_company"] = board, company
        return row

    def parse_page(self, payload, board: str, include_description: bool = False):
        company = self.company_from(payload, board)
        out = []
        for row in self.rows_from(payload):
            if not isinstance(row, dict):
                continue
            try:
                record = self.parse_one(self.prepare(row, board, company),
                                        include_description)
            except (listing.ListingError, KeyError, TypeError, ValueError):
                continue
            if record is not None:
                out.append(record)
        return out

    def parse_one(self, raw, include_description: bool = False):
        raise NotImplementedError


class Greenhouse(Ats):
    """Greenhouse job board API. Powers each customer's embedded careers page."""

    site = "greenhouse"
    base_url = "https://boards-api.greenhouse.io"
    licence = "Publisher's public job board API"
    attribution = (
        "Job postings retrieved from employers' public Greenhouse job boards."
    )

    def board_url(self, board):
        # pay_transparency is opt-in per request and costs nothing. Without it
        # the response carries no pay at all; with it, boards that publish
        # ranges return them in exact cents.
        return (f"{self.base_url}/v1/boards/{board}/jobs"
                f"?content=true&pay_transparency=true")

    def rows_from(self, payload):
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        return rows if isinstance(rows, list) else []

    @staticmethod
    def pay_from(ranges):
        """Span the pay bands a posting lists, in one currency only.

        A posting often carries several bands, one per pay zone or country:
        Airbnb prints a "Germany Annual Pay Range" in EUR next to a US one in
        USD. Spanning across currencies would invent a range that does not
        exist, so only the bands sharing the first band's currency are used.
        """
        bands = [b for b in (ranges or []) if isinstance(b, dict)]
        if not bands:
            return None, None, None, None
        currency = _text(bands[0].get("currency_type"))
        if not currency:
            return None, None, None, None
        lows, highs = [], []
        for band in bands:
            if _text(band.get("currency_type")) != currency:
                continue
            for key, bucket in (("min_cents", lows), ("max_cents", highs)):
                value = band.get(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    bucket.append(value / 100)
        if not lows and not highs:
            return None, None, None, None
        titles = [_text(b.get("title")) for b in bands
                  if _text(b.get("currency_type")) == currency]
        label = "; ".join(t for t in titles if t) or None
        return (min(lows) if lows else None,
                max(highs) if highs else None,
                currency.upper(), label)

    def company_from(self, payload, board):
        for row in self.rows_from(payload):
            if not isinstance(row, dict):
                continue
            name = _text(row.get("company_name"))
            if name:
                return name
        return board

    def parse_one(self, raw, include_description=False):
        job_id = raw.get("id")
        title = _text(raw.get("title"))
        url = _text(raw.get("absolute_url"))
        if job_id is None or not title or not url:
            raise ValueError("posting has no id, title or url")

        departments = [_text(d.get("name")) for d in (raw.get("departments") or [])
                       if isinstance(d, dict)]
        departments = [d for d in departments if d]
        location = _text(_nested(raw, "location", "name"))
        low, high, currency, label = self.pay_from(raw.get("pay_input_ranges"))

        return self.record(
            job_id=str(job_id),
            ats=self.site,
            board=raw["_board"],
            company=raw["_company"],
            title=title,
            department=departments[0] if departments else None,
            location_raw=location,
            # Greenhouse publishes no employment type, and where a board has
            # pay transparency switched off it publishes no pay either. Both
            # are often in the description prose. Reading them out of prose
            # would be a guess, so both stay empty rather than wrong.
            salary_min=low, salary_max=high,
            salary_currency=currency if (low is not None or high is not None) else None,
            salary_text=label,
            posted_date=_iso_date(raw.get("first_published")),
            updated_date=_iso_date(raw.get("updated_at")),
            description_text=(to_plain_text(raw.get("content"))
                              if include_description else None),
            apply_url=url,
            verify_url=url,
        )


class Lever(Ats):
    """Lever postings API. Its own documentation: "This API is designed to
    help you create a job site."."""

    site = "lever"
    base_url = "https://api.lever.co"
    licence = "Publisher's public postings API"
    attribution = "Job postings retrieved from employers' public Lever job boards."
    # api.lever.co/robots.txt asks for one second between requests, and asking
    # is the only thing a robots.txt can do. It is honoured.
    crawl_delay = 1.0

    def board_url(self, board):
        return f"{self.base_url}/v0/postings/{board}?mode=json"

    def rows_from(self, payload):
        return payload if isinstance(payload, list) else []

    def parse_one(self, raw, include_description=False):
        job_id = _text(raw.get("id"))
        title = _text(raw.get("text"))
        url = _text(raw.get("hostedUrl"))
        if not job_id or not title or not url:
            raise ValueError("posting has no id, title or url")

        categories = raw.get("categories") or {}
        country = _text(raw.get("country"))
        low, high, currency = parse_range(_text(raw.get("salaryRange")) or "")
        if isinstance(raw.get("salaryRange"), dict):
            band = raw["salaryRange"]
            low = band.get("min") if isinstance(band.get("min"), (int, float)) else low
            high = band.get("max") if isinstance(band.get("max"), (int, float)) else high
            currency = _text(band.get("currency")) or currency

        return self.record(
            job_id=job_id,
            ats=self.site,
            board=raw["_board"],
            company=raw["_company"],
            title=title,
            department=_text(categories.get("department")),
            team=_text(categories.get("team")),
            employment_type=normalise_employment(categories.get("commitment")),
            workplace_type=normalise_workplace(raw.get("workplaceType")),
            location_raw=_text(categories.get("location")),
            location_country=country.upper() if country and len(country) == 2 else None,
            is_remote=(raw.get("workplaceType") == "remote"
                       if _text(raw.get("workplaceType")) else None),
            posted_date=_iso_date(raw.get("createdAt")),
            salary_min=low, salary_max=high,
            salary_currency=currency if (low is not None or high is not None) else None,
            salary_text=_text(raw.get("salaryRange"))
            if isinstance(raw.get("salaryRange"), str) else None,
            description_text=(to_plain_text(raw.get("descriptionPlain")
                                            or raw.get("description"))
                              if include_description else None),
            apply_url=_text(raw.get("applyUrl")) or url,
            verify_url=url,
        )


class Ashby(Ats):
    """Ashby job postings API. Its own documentation: "If you host your own
    careers page, you can use this data to populate it."."""

    site = "ashby"
    base_url = "https://api.ashbyhq.com"
    licence = "Publisher's public job postings API"
    attribution = "Job postings retrieved from employers' public Ashby job boards."

    def board_url(self, board):
        return f"{self.base_url}/posting-api/job-board/{board}?includeCompensation=true"

    def rows_from(self, payload):
        rows = payload.get("jobs") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return []
        # Ashby's own documentation: "Unlisted job postings should not be
        # displayed publicly." The flag is respected rather than noticed.
        return [r for r in rows if not (isinstance(r, dict) and r.get("isListed") is False)]

    def parse_one(self, raw, include_description=False):
        job_id = _text(raw.get("id"))
        title = _text(raw.get("title"))
        url = _text(raw.get("jobUrl"))
        if not job_id or not title or not url:
            raise ValueError("posting has no id, title or url")

        postal = _nested(raw, "address", "postalAddress") or {}
        country = _text(postal.get("addressCountry"))
        summary = _text(_nested(raw, "compensation",
                                "scrapeableCompensationSalarySummary"))
        tier = _text(_nested(raw, "compensation", "compensationTierSummary"))
        low, high, currency = parse_range(summary or tier or "")

        return self.record(
            job_id=job_id,
            ats=self.site,
            board=raw["_board"],
            company=raw["_company"],
            title=title,
            department=_text(raw.get("department")),
            team=_text(raw.get("team")),
            employment_type=normalise_employment(raw.get("employmentType")),
            workplace_type=normalise_workplace(raw.get("workplaceType"),
                                               raw.get("isRemote")),
            location_raw=_text(raw.get("location")),
            location_city=_text(postal.get("addressLocality")),
            location_country=COUNTRY_ALIASES.get(country, country),
            is_remote=raw.get("isRemote") if isinstance(raw.get("isRemote"), bool) else None,
            posted_date=_iso_date(raw.get("publishedAt")),
            salary_min=low, salary_max=high,
            salary_currency=currency if (low is not None or high is not None) else None,
            salary_text=summary or tier,
            description_text=(to_plain_text(raw.get("descriptionPlain")
                                            or raw.get("descriptionHtml"))
                              if include_description else None),
            apply_url=_text(raw.get("applyUrl")) or url,
            verify_url=url,
        )


# Ashby writes country names rather than ISO codes, and not consistently.
# Only mappings that are unambiguous are made; anything else is left as the
# register wrote it rather than guessed into a wrong code.
COUNTRY_ALIASES = {
    "USA": "US", "United States": "US", "United States of America": "US",
    "UK": "GB", "United Kingdom": "GB",
    "Canada": "CA", "Germany": "DE", "France": "FR", "Spain": "ES",
    "Netherlands": "NL", "Ireland": "IE", "Poland": "PL", "India": "IN",
    "Australia": "AU", "Brazil": "BR", "Mexico": "MX", "Japan": "JP",
    "Singapore": "SG", "Israel": "IL", "Sweden": "SE", "Portugal": "PT",
    "Italy": "IT", "Switzerland": "CH", "Austria": "AT", "Belgium": "BE",
    "Denmark": "DK", "Norway": "NO", "Finland": "FI", "Czechia": "CZ",
    "Czech Republic": "CZ", "Slovakia": "SK", "Romania": "RO",
    "New Zealand": "NZ", "South Africa": "ZA", "Argentina": "AR",
    "Colombia": "CO", "Chile": "CL", "Philippines": "PH", "Indonesia": "ID",
}

SYSTEMS = {a.site: a for a in (Greenhouse(), Lever(), Ashby())}

# A careers URL is what a person has in their hand; the board slug is what the
# API wants. These turn one into the other.
URL_PATTERNS = (
    ("greenhouse", re.compile(r"(?:boards|job-boards)\.greenhouse\.io/(?:embed/job_board\?for=)?([\w.-]+)", re.I)),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([\w.-]+)", re.I)),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([\w.-]+)", re.I)),
    ("lever", re.compile(r"api\.lever\.co/v0/postings/([\w.-]+)", re.I)),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([\w.-]+)", re.I)),
    ("ashby", re.compile(r"api\.ashbyhq\.com/posting-api/job-board/([\w.-]+)", re.I)),
)


class BoardError(ValueError):
    """The input does not name a board this tool can read."""


_SLUG = re.compile(r"^[\w.-]{1,120}$")


def parse_target(value) -> tuple[str | None, str]:
    """Turn one input entry into (ats or None, board slug).

    Accepts a careers URL, `ats:slug`, or a bare slug. A bare slug means the
    system is unknown and the caller wants it found, which the entry point
    does by asking each system in turn.
    """
    if not isinstance(value, str) or not value.strip():
        raise BoardError("empty entry: expected a careers URL or a board name")
    text = value.strip()

    for site, pattern in URL_PATTERNS:
        match = pattern.search(text)
        if match:
            return site, match.group(1)

    if "://" in text:
        raise BoardError(
            f"{text!r} is a URL, but not one of a supported job board. "
            f"Supported: {', '.join(sorted(SYSTEMS))}."
        )

    if ":" in text:
        site, _, slug = text.partition(":")
        site = site.strip().lower()
        slug = slug.strip()
        if site not in SYSTEMS:
            raise BoardError(
                f"{site!r} is not a system this tool reads. "
                f"Supported: {', '.join(sorted(SYSTEMS))}."
            )
        if not _SLUG.match(slug):
            raise BoardError(f"{slug!r} is not a usable board name")
        return site, slug

    if not _SLUG.match(text):
        raise BoardError(f"{text!r} is not a usable board name")
    return None, text


def shape_problems() -> list[str]:
    """Every system must declare what the core needs. Called by the tests."""
    from .listings import adapter

    found = []
    for name, system in SYSTEMS.items():
        found += [f"{name}: {p}" for p in adapter.check_shape(system)]
        if not system.licence:
            found.append(f"{name}: no licence declared")
        if not system.attribution:
            found.append(f"{name}: no attribution string declared")
    return found


def record_problems(record: dict) -> list[str]:
    return listing.problems(record, kind="job")
