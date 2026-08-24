"""Turn a pay string an applicant-tracking system prints into numbers.

Why this exists rather than passing the string through: a caller filtering
"jobs paying over 150k" cannot filter on `"$211.4K - $290.6K"`. Nor on
`"EUR 65,000 - 80,000 per year"`, which is the same fact written by a
different system in a different country.

Why it is careful rather than clever: **a salary parsed wrong is worse than a
salary not parsed at all.** Reading "$120K" as 120 would file a senior
engineering job next to a day rate. Every function here returns None when it
is not sure, and `salary_text` always carries the original string, so nothing
is lost by refusing.

The specific traps, all found in real postings on 2026-08-24:

  - **`$211.4K` is 211,400.** Not 211.4, and not 2,114,000.
  - **`70,000` and `70.000` are the same number** in different conventions,
    and `1.234` is one thousand two hundred and thirty-four in German.
  - **`$50 - $80 / hour` is not an annual salary** and must never be reported
    as one. Hourly, daily, weekly and monthly rates are refused.
  - Equity and bonus clauses ride in the same sentence:
    `"$211.4K - $290.6K - Offers Equity"`. An equity percentage must not
    become a salary figure.
  - **`kr` is Swedish, Norwegian and Danish**, and the amounts differ by a
    factor that matters. An ambiguous currency marker yields no numbers.
"""

import re

# The space characters job boards use interchangeably inside numbers:
# ordinary, non-breaking, narrow non-breaking.
SPACES = "   "

# ISO 4217 for the markers that actually appear on job boards. A marker mapped
# to None is real but ambiguous, and ambiguity here produces no numbers at
# all: an amount whose currency is unknown is not a salary.
SYMBOLS = {
    "$": "USD", "US$": "USD", "USD": "USD",
    "£": "GBP", "GBP": "GBP",
    "€": "EUR", "EUR": "EUR",
    "C$": "CAD", "CA$": "CAD", "CAD": "CAD",
    "A$": "AUD", "AU$": "AUD", "AUD": "AUD",
    "CHF": "CHF",
    "SEK": "SEK", "NOK": "NOK", "DKK": "DKK", "PLN": "PLN", "CZK": "CZK",
    "zł": "PLN", "Kč": "CZK",
    "kr": None,          # Swedish, Norwegian or Danish
    "₹": "INR", "INR": "INR",
    "R$": "BRL", "BRL": "BRL",
    "¥": None,      # yen or yuan
    "SGD": "SGD", "S$": "SGD",
    "NZD": "NZD", "NZ$": "NZD",
    "ILS": "ILS", "₪": "ILS",
    "MXN": "MXN", "ZAR": "ZAR", "JPY": "JPY", "CNY": "CNY",
}

# Longest first, so "CA$" is matched before "$" and "CAD" before "CA$".
_SYMBOL = re.compile("|".join(
    re.escape(s) for s in sorted(SYMBOLS, key=len, reverse=True)
))

# A rate, not an annual salary. Anything matching is refused.
_PER_UNIT = re.compile(
    r"(?:per|/|a)\s*(?:hour|hr|hourly|day|daily|week|weekly|month|monthly)\b"
    r"|\b(?:hourly|per-hour|daily|day\s*rate|monthly)\b",
    re.I,
)
_ANNUAL = re.compile(r"\b(?:per\s*(?:year|annum)|annually|/\s*yr|p\.?a\.?)\b", re.I)

# 211.4K, 290,600, "80 000", 70.000
_AMOUNT = re.compile(
    r"(?P<num>\d[\d.,{sp}]*\d|\d)[{sp}]*(?P<suffix>[KkMm])?".format(sp=SPACES)
)

# Below this, a bare number is far more likely to be an hourly rate, a
# headcount or an equity figure than an annual salary.
MIN_PLAUSIBLE_ANNUAL = 1000
# Above this the string is being misread. No job board advertises a hundred
# million a year.
MAX_PLAUSIBLE_ANNUAL = 100_000_000


def find_currency(text: str) -> str | None:
    """The ISO code of the first unambiguous currency marker, else None.

    An ambiguous marker is skipped rather than guessed at; a clear one later
    in the same string still counts.
    """
    for match in _SYMBOL.finditer(text):
        code = SYMBOLS.get(match.group(0))
        if code:
            return code
    return None


def to_number(raw: str, suffix: str | None = None) -> float | None:
    """Read one number the way a person reads it, or give up.

    The rule: **a group of exactly three digits after the final separator is a
    thousands group; anything else after a separator is a decimal fraction.**
    That reads `1,234` and `1.234` as one thousand two hundred and thirty-four,
    and `211.4` as two hundred and eleven point four, which is what both
    conventions intend.

    A suffix changes the reading: `211.4K` must be 211,400, so when a suffix
    is present a trailing group is always a fraction.
    """
    if not isinstance(raw, str):
        return None
    text = raw
    for space in SPACES[1:]:
        text = text.replace(space, " ")
    text = re.sub(r"(?<=\d) (?=\d)", "", text).strip()

    last = max(text.rfind(","), text.rfind("."))
    if last == -1:
        digits = text
    else:
        head, tail = text[:last], text[last + 1:]
        head = head.replace(",", "").replace(".", "")
        if len(tail) == 3 and not suffix:
            digits = head + tail
        else:
            digits = f"{head}.{tail}" if tail else head
    try:
        value = float(digits)
    except ValueError:
        return None

    if suffix and suffix in "Kk":
        value *= 1_000
    elif suffix and suffix in "Mm":
        value *= 1_000_000
    return value


def parse_range(text) -> tuple[float | None, float | None, str | None]:
    """Return (minimum, maximum, ISO currency), any of which may be None.

    Nothing at all is a normal outcome, not a failure: it means the string was
    not something this module is willing to read as an annual salary.
    """
    if not isinstance(text, str) or not text.strip():
        return None, None, None

    if _PER_UNIT.search(text) and not _ANNUAL.search(text):
        return None, None, None

    currency = find_currency(text)
    if not currency:
        return None, None, None

    # Cut at the first clause that is not pay. Ashby writes equity and bonus
    # into the same sentence as the salary band.
    body = re.split(r"[•·|]|\bOffers\b|\bplus\b|\bequity\b|\bbonus\b",
                    text, flags=re.I)[0]

    values = []
    for match in _AMOUNT.finditer(body):
        if body[match.end():match.end() + 2].lstrip().startswith("%"):
            continue                       # a percentage is never a salary
        value = to_number(match.group("num"), match.group("suffix"))
        if value is None or not MIN_PLAUSIBLE_ANNUAL <= value <= MAX_PLAUSIBLE_ANNUAL:
            continue
        values.append(value)

    if not values:
        return None, None, currency
    return min(values), max(values), currency
