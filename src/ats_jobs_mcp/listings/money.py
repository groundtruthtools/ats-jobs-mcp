"""Locale-aware price parsing for marketplace listings.

Pure: text in, numbers out. No network, no platform code, no wall-clock.

This is the single hardest reusable piece of a multi-country listings
portfolio. "12.500" means twelve and a half thousand in Berlin and twelve
point five in Boston, and getting it backwards silently multiplies every
price by a thousand. So the locale is a required argument -- there is no
guessing mode, because a wrong guess here is invisible in the output.
"""

import re
from decimal import Decimal, InvalidOperation

# Spaces that appear as digit-group separators in real listing markup.
# U+00A0 no-break, U+202F narrow no-break, U+2009 thin, U+2007 figure.
SPACES = "     "

# Group and decimal separators per locale.
# Source: Unicode CLDR 47 number formats, retrieved 2026-08-23.
# Key is a BCP 47 tag; value is (group separators, decimal separator).
LOCALES: dict[str, tuple[str, str]] = {
    "en-US": (",", "."),
    "en-GB": (",", "."),
    "en-AU": (",", "."),
    "en-CA": (",", "."),
    "en-IE": (",", "."),
    "en-IN": (",", "."),      # grouping positions differ; see group_digits()
    "en-MY": (",", "."),
    "en-SG": (",", "."),
    "de-DE": (".", ","),
    "de-AT": (".", ","),
    "de-CH": ("'" + SPACES, "."),
    "nl-NL": (".", ","),
    "it-IT": (".", ","),
    "es-ES": (".", ","),
    "pt-PT": (SPACES, ","),
    "pt-BR": (".", ","),
    "fr-FR": (SPACES, ","),
    "pl-PL": (SPACES, ","),
    "cs-CZ": (SPACES, ","),
    "sk-SK": (SPACES, ","),
    "hu-HU": (SPACES, ","),
    "ro-RO": (".", ","),
    "bg-BG": (SPACES, ","),
    "hr-HR": (".", ","),
    "sl-SI": (".", ","),
    "lt-LT": (SPACES, ","),
    "lv-LV": (SPACES, ","),
    "et-EE": (SPACES, ","),
    "ru-RU": (SPACES, ","),
    "uk-UA": (SPACES, ","),
    "tr-TR": (".", ","),
    "sv-SE": (SPACES, ","),
    "nb-NO": (SPACES, ","),
    "da-DK": (".", ","),
    "fi-FI": (SPACES, ","),
    "he-IL": (",", "."),
    "ja-JP": (",", "."),
    "ko-KR": (",", "."),
    "id-ID": (".", ","),
    "ms-MY": (",", "."),
    "th-TH": (",", "."),
    "ar-AE": (",", "."),
}

# ISO 4217 minor-unit exponents for the currencies this portfolio touches.
# Source: ISO 4217:2015 Table A.1, retrieved 2026-08-23.
# Only currencies that differ from the default of 2 need care, but all are
# listed explicitly so a reader can check any of them against the table.
MINOR_UNITS: dict[str, int] = {
    "AED": 2, "AUD": 2, "BGN": 2, "BRL": 2, "CAD": 2, "CHF": 2, "CZK": 2,
    "DKK": 2, "EUR": 2, "GBP": 2, "HUF": 2, "IDR": 2, "ILS": 2, "INR": 2,
    "JPY": 0, "KRW": 0, "MYR": 2, "NOK": 2, "PLN": 2, "RON": 2, "RSD": 2,
    "RUB": 2, "SEK": 2, "SGD": 2, "THB": 2, "TRY": 2, "UAH": 2, "USD": 2,
}

# Currency symbols and local abbreviations seen in listing prices.
# Symbols shared by several currencies (notably "$" and "kr") are deliberately
# absent here and resolved from the adapter's declared currency instead.
UNAMBIGUOUS_SYMBOLS: dict[str, str] = {
    "€": "EUR",
    "£": "GBP",
    "₴": "UAH",
    "₺": "TRY",
    "₪": "ILS",
    "₹": "INR",
    "¥": "JPY",
    "₩": "KRW",
    "zł": "PLN",
    "kč": "CZK",
    "ft": "HUF",
    "lei": "RON",
    "лв": "BGN",
    "₽": "RUB",
    "rp": "IDR",
    "rm": "MYR",
    "chf": "CHF",
    "kn": "HRK",
}


class PriceError(ValueError):
    """Raised with a message naming what could not be parsed."""


def _clean(text: str) -> str:
    """Drop everything that is not a digit, separator, or minus sign."""
    keep = []
    for ch in text:
        if ch.isdigit() or ch in ".,'-" or ch in SPACES:
            keep.append(ch)
    return "".join(keep).strip()


def parse_decimal(text: str, locale: str) -> Decimal | None:
    """Parse a formatted number in a known locale. None if there is no number.

    Raises PriceError for an unknown locale, because falling back to a default
    is exactly the silent thousand-fold error this module exists to prevent.
    """
    if locale not in LOCALES:
        raise PriceError(
            f"unknown locale '{locale}'. Add it to LOCALES with a CLDR source "
            f"before using it; guessing separators corrupts prices silently"
        )
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)

    groups, decimal_sep = LOCALES[locale]
    cleaned = _clean(text)
    if not cleaned:
        return None

    negative = cleaned.startswith("-")
    cleaned = cleaned.lstrip("-")

    # Remove group separators, then normalise the decimal separator to a dot.
    for ch in groups:
        cleaned = cleaned.replace(ch, "")
    if decimal_sep in groups:
        # de-CH uses "'" for groups and "." for decimals; nothing to swap.
        pass
    cleaned = cleaned.replace(decimal_sep, ".")

    # Any separator still present that is not the decimal point is a stray
    # group separator the locale table did not list (site markup varies).
    cleaned = cleaned.replace(",", "") if decimal_sep != "," else cleaned
    cleaned = "".join(c for c in cleaned if c.isdigit() or c == ".")

    if not cleaned or cleaned == ".":
        return None
    if cleaned.count(".") > 1:
        # Several dots after group removal means the dots were groups too.
        cleaned = cleaned.replace(".", "")

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        return None
    return -value if negative else value


def _has_word(text: str, word: str) -> bool:
    """Whole-token match for letter-based markers.

    A bare substring test is wrong here: "Firma" contains "rm", which would
    silently label a German advert as Malaysian ringgit. Letters must sit at a
    token boundary; symbols like the euro sign never need one.
    """
    return bool(re.search(rf"(?<![^\W\d_]){re.escape(word)}(?![^\W\d_])", text))


def detect_currency(text: str, default: str | None = None) -> str | None:
    """Return an ISO 4217 code from a symbol or code in the text.

    Falls back to `default`, which the adapter supplies from the site it
    covers. Ambiguous symbols such as "$" and "kr" are never guessed.
    """
    if not isinstance(text, str):
        return default
    lowered = text.lower()

    # An explicit three-letter code in the text wins over any symbol.
    for code in MINOR_UNITS:
        if _has_word(lowered, code.lower()):
            return code

    for symbol, code in UNAMBIGUOUS_SYMBOLS.items():
        if symbol.isalpha():
            if _has_word(lowered, symbol):
                return code
        elif symbol in lowered:
            return code
    return default


def parse_price(
    text: str, locale: str, default_currency: str | None = None
) -> tuple[float | None, str | None]:
    """Parse "12.500,50 €" into (12500.5, "EUR").

    Returns (None, currency) when the text carries no number at all, which is
    normal for adverts listed as "price on application".
    """
    amount = parse_decimal(text, locale)
    currency = detect_currency(text, default_currency)
    if amount is None:
        return None, currency

    exponent = MINOR_UNITS.get(currency or "", 2)
    quantized = round(float(amount), exponent)
    # A zero-decimal currency should never carry a fractional part.
    return (float(int(quantized)) if exponent == 0 else quantized), currency
