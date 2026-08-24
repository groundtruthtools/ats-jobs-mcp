"""The contract every site adapter implements.

A new market is one subclass and a golden file. Nothing else in the portfolio
changes, which is the arithmetic that makes twenty markets affordable.

Adapters stay pure: they turn already-fetched raw data into records. Fetching
lives in the tool's entry point, exactly as it does for the two government
tools, so every adapter is testable offline against saved fixtures.
"""

from . import listing


class Adapter:
    """Base class. Subclasses set the class attributes and implement parse_one."""

    # Identity, used in output and in the store listing.
    site: str = ""
    country: str = ""          # ISO 3166-1 alpha-2
    locale: str = ""           # BCP 47, must exist in money.LOCALES
    currency: str = ""         # ISO 4217, the site's default
    base_url: str = ""
    kind: str = "vehicle"      # one of listing.KINDS; sets the record shape

    # Mileage and power units as the site quotes them, so the adapter does not
    # each have to remember to convert.
    mileage_unit: str = "km"   # "km" or "mi"
    power_unit: str = "kw"     # "kw", "ps" or "hp"

    def parse_one(self, raw: dict) -> dict:
        """Turn one raw item into a canonical record via listing.build()."""
        raise NotImplementedError

    def list_url(self, query: dict, page: int) -> str:
        """The URL for one page of results. Implemented per site."""
        raise NotImplementedError

    # ---- helpers shared by every adapter -------------------------------

    def record(self, **values) -> dict:
        return listing.build(self.site, self.country, self.kind, **values)

    def parse_many(self, rows) -> list[dict]:
        """Parse a page. A single unparseable row is skipped, not fatal:
        one malformed advert should not empty a page of good ones."""
        out = []
        if not isinstance(rows, list):
            return out
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                parsed = self.parse_one(row)
            except (listing.ListingError, KeyError, TypeError, ValueError):
                continue
            if parsed is not None:
                out.append(parsed)
        return out

    def describe(self) -> dict:
        """Used by the monitor and the scaffold to report what exists."""
        return {
            "site": self.site,
            "kind": self.kind,
            "country": self.country,
            "locale": self.locale,
            "currency": self.currency,
            "mileage_unit": self.mileage_unit,
            "power_unit": self.power_unit,
        }


def check_shape(adapter: Adapter) -> list[str]:
    """Verify an adapter declares everything the core needs.

    Called by the deploy gate so a half-filled adapter cannot ship.
    """
    from . import money

    found = []
    if adapter.kind not in listing.FIELDS_FOR:
        return [f"kind: '{adapter.kind}' must be one of {', '.join(listing.KINDS)}"]

    # Locale, currency and unit declarations describe a marketplace listing.
    # A company register, a VAT check and a job posting have no price and no
    # vehicle, so they do not apply.
    non_listing = adapter.kind in ("company", "vat", "job")
    for attribute in ("site", "country", "locale", "currency", "base_url"):
        if non_listing and attribute in ("locale", "currency"):
            continue
        if not getattr(adapter, attribute, ""):
            found.append(f"{attribute}: must be set on the adapter")

    if non_listing:
        for attribute in ("site", "country", "base_url"):
            if not getattr(adapter, attribute, ""):
                found.append(f"{attribute}: must be set on the adapter")
        if adapter.country and (len(adapter.country) != 2 or not adapter.country.isupper()):
            if adapter.country != "XX":  # XX marks a genuinely multi-country registry
                found.append(f"country: '{adapter.country}' must be ISO 3166-1 alpha-2")
        return found

    if adapter.locale and adapter.locale not in money.LOCALES:
        found.append(
            f"locale: '{adapter.locale}' is not in money.LOCALES. Add it with a "
            f"CLDR source before shipping this adapter."
        )
    if adapter.currency and adapter.currency not in money.MINOR_UNITS:
        found.append(
            f"currency: '{adapter.currency}' is not in money.MINOR_UNITS. Add it "
            f"with an ISO 4217 source."
        )
    if adapter.country and (len(adapter.country) != 2 or not adapter.country.isupper()):
        found.append(
            f"country: '{adapter.country}' must be an ISO 3166-1 alpha-2 code"
        )
    if adapter.mileage_unit not in ("km", "mi"):
        found.append(f"mileage_unit: '{adapter.mileage_unit}' must be 'km' or 'mi'")
    if adapter.power_unit not in ("kw", "ps", "hp"):
        found.append(f"power_unit: '{adapter.power_unit}' must be 'kw', 'ps' or 'hp'")
    if adapter.kind not in listing.FIELDS_FOR:
        found.append(
            f"kind: '{adapter.kind}' must be one of {', '.join(listing.KINDS)}"
        )
    return found
