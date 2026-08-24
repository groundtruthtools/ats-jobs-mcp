"""The canonical listing record, shared by every site adapter.

One shape per kind of listing, identical across every country. That is the
point of the factory: a buyer wiring up three markets gets three feeds with
the same field names, and a new market costs an adapter rather than a project.

Two rules are enforced here rather than left to reviewer discipline, because
both are the kind of thing that erodes quietly:

  1. Every record carries `verify_url`, a link to the original advert.
     STRATEGY.md keeps the verifiability gate from SELECTION-CRITERIA.md when
     moving to commercial sources; a record nobody can check is not a product.

  2. No personal data, ever. Seller names, agent names, phone numbers and
     email addresses are rejected by the validator, not merely left unmapped.
     This is not theoretical: an otodom search page carries the estate agent's
     full name in `advertOwner.name` on every listing. Publishing those turns
     the portfolio into a California data broker with GDPR exposure on top.
     The schema refuses the fields so the rule cannot lapse by oversight.
"""

from datetime import date

# Shared by every kind of record.
SHARED_FIELDS = ("source", "source_country", "verify_url")

# Shared by every kind of listing.
COMMON_FIELDS = (
    "listing_id",
    "source",
    "source_country",
    "title",
    "price_amount",
    "price_currency",
    "seller_type",
    "location_region",
    "location_city",
    "listed_date",
    "verify_url",
)

VEHICLE_FIELDS = (
    "make",
    "model",
    "variant",
    "year",
    "mileage_km",
    "fuel",
    "transmission",
    "body_type",
    "power_kw",
)

PROPERTY_FIELDS = (
    "property_type",
    "transaction",
    "area_sqm",
    "rooms",
    "floor",
    "price_per_sqm_amount",
    "year_built",
)

# An official company-registry record. Not a listing: there is no price and
# no seller, and the authority is a government register rather than a market.
COMPANY_FIELDS = SHARED_FIELDS + (
    "company_number",
    "legal_name",
    "status",
    "legal_form",
    "incorporated_date",
    "dissolved_date",
    "address_city",
    "address_postcode",
    "address_country",
    "activity_code",
    "activity_text",
    "employees_band",
    "lei",
    "previous_names",
    "last_updated",
)

# The result of checking one VAT number against an official validation
# service. Deliberately narrow: a validation answers "is this registration
# real, and whose is it", nothing more.
#
# The registered address is NOT collected. For a sole trader a VAT address is
# very often a home address, and unlike the trading name it is not something
# a counterparty needs in order to verify a registration.
VAT_FIELDS = SHARED_FIELDS + (
    "vat_number",
    "country_code",
    "is_valid",
    # Why is_valid is not enough on its own: a validation service that is busy
    # answers "false", which is not the same as "this number is not
    # registered". check_status separates the verdict from the failure, and
    # is_valid is None whenever no verdict was obtained.
    "check_status",
    "check_note",
    "legal_name",
    "checked_date",
)

VAT_CHECK_STATUSES = {"valid", "invalid", "unchecked"}

# One published job opening, as an applicant-tracking system serves it to the
# job sites the employer wants it on.
#
# Two things are deliberately missing.
#
# The **recruiter**. Some systems attach a hiring contact to a posting, with a
# name and often an email. That is a named private individual, and a job
# aggregator does not need one to describe an opening.
#
# The **candidate side of the application**. Nothing here touches an applicant.
# The record ends at `apply_url`, which is the employer's own public link.
JOB_FIELDS = SHARED_FIELDS + (
    "job_id",
    "ats",
    "board",
    "company",
    "title",
    "department",
    "team",
    "employment_type",
    "workplace_type",
    "location_raw",
    "location_city",
    "location_country",
    "is_remote",
    "posted_date",
    "updated_date",
    # When this feed first saw the posting. Only set in incremental mode,
    # where it is the one fact a caller cannot recover from the vendor: the
    # vendors publish when a job was posted, not when you first heard of it.
    "first_seen",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_text",
    "description_text",
    "apply_url",
)

# Coarse on purpose, the same argument as COMPANY_STATUSES. Six systems use
# about thirty words between them for four real distinctions.
EMPLOYMENT_TYPES = {"full_time", "part_time", "contract", "temporary",
                    "internship", "apprenticeship", "volunteer", "other"}
WORKPLACE_TYPES = {"on_site", "remote", "hybrid", "unknown"}

FIELDS_FOR = {
    "vehicle": COMMON_FIELDS + VEHICLE_FIELDS,
    "property": COMMON_FIELDS + PROPERTY_FIELDS,
    "company": COMPANY_FIELDS,
    "vat": VAT_FIELDS,
    "job": JOB_FIELDS,
}

REQUIRED_FOR = {
    "vehicle": ("listing_id", "source", "title", "verify_url"),
    "property": ("listing_id", "source", "title", "verify_url"),
    "company": ("company_number", "source", "legal_name", "verify_url"),
    # A VAT check is meaningful even when the number turns out to be invalid,
    # so a legal name is not required -- an invalid number has none.
    "vat": ("vat_number", "country_code", "check_status", "source", "verify_url"),
    # A posting with no company or no title is not a job advert, it is a row
    # that survived a parser. `board` is required because it is the only thing
    # that lets a caller re-run the exact query that produced the record.
    "job": ("job_id", "source", "ats", "board", "company", "title", "verify_url"),
}

KINDS = tuple(FIELDS_FOR)

# Rejected outright. Substring match, because `seller_email`, `contactEmail`
# and `advertOwner` are the same mistake wearing different names.
BANNED_SUBSTRINGS = (
    "email",
    "phone",
    "mobile",
    "telephone",
    "seller_name",
    "contact",
    "owner",
    "agent",
    "broker",
    "person",
    "first_name",
    "last_name",
    "full_name",
    "address_line",
    "street",
)

FUELS = {"petrol", "diesel", "electric", "hybrid", "plugin_hybrid", "lpg", "cng",
         "hydrogen", "other"}
TRANSMISSIONS = {"manual", "automatic", "semi_automatic", "other"}
SELLER_TYPES = {"dealer", "private", "unknown"}
# Deliberately coarse. Registries use dozens of local status words; a consumer
# comparing four countries needs three buckets, not forty untranslated ones.
COMPANY_STATUSES = {"active", "inactive", "dissolved", "unknown"}
PROPERTY_TYPES = {"flat", "house", "room", "land", "commercial", "garage", "other"}
TRANSACTIONS = {"sale", "rent", "other"}

# No production car or recorded building predates this, and an advert carrying
# a year beyond next year is a data error rather than a pre-order.
EARLIEST_YEAR = 1900


class ListingError(ValueError):
    """Raised with a message naming the field and what is wrong with it."""


def _check_kind(kind: str) -> None:
    if kind not in FIELDS_FOR:
        raise ListingError(f"unknown kind {kind!r}. Valid kinds: {', '.join(KINDS)}")


def _reject_personal(key: str) -> None:
    lowered = key.lower()
    for banned in BANNED_SUBSTRINGS:
        if banned in lowered:
            raise ListingError(
                f"field '{key}' looks like personal data and is not allowed in a "
                f"listing record. See listing.py for why this is a hard rule "
                f"rather than a preference."
            )


def blank(kind: str = "vehicle") -> dict:
    """An empty record with every field present. Adapters fill what they can."""
    _check_kind(kind)
    return {field: None for field in FIELDS_FOR[kind]}


def build(source: str, source_country: str, kind: str = "vehicle", **values) -> dict:
    """Assemble a record, rejecting unknown and forbidden fields early."""
    _check_kind(kind)
    record = blank(kind)
    record["source"] = source
    record["source_country"] = source_country

    for key, value in values.items():
        _reject_personal(key)
        if key not in FIELDS_FOR[kind]:
            raise ListingError(
                f"unknown field '{key}' for a {kind} listing. Valid fields: "
                f"{', '.join(FIELDS_FOR[kind])}"
            )
        record[key] = value
    return record


def _positive_number(record, field, found):
    value = record.get(field)
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        found.append(f"{field}: must be a number")
    elif value < 0:
        found.append(f"{field}: cannot be negative, got {value}")


def problems(record: dict, this_year: int | None = None, kind: str = "vehicle") -> list[str]:
    """Return everything wrong with a record. Empty list means valid.

    Returns a list rather than raising so one run can report every problem on a
    page at once instead of stopping at the first.
    """
    if not isinstance(record, dict):
        return ["record is not an object"]
    _check_kind(kind)

    found = []

    for key in record:
        lowered = key.lower()
        for banned in BANNED_SUBSTRINGS:
            if banned in lowered:
                found.append(f"{key}: personal-data field is not allowed")
                break

    for field in REQUIRED_FOR[kind]:
        value = record.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            found.append(f"{field}: required and missing")

    url = record.get("verify_url")
    if isinstance(url, str) and url.strip() and not url.startswith(("http://", "https://")):
        found.append("verify_url: must be an http or https link to the advert")

    limit = (this_year or date.today().year) + 1
    for field in ("year", "year_built"):
        value = record.get(field)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, int):
            found.append(f"{field}: must be a whole number")
        elif not EARLIEST_YEAR <= value <= limit:
            found.append(f"{field}: {value} is outside {EARLIEST_YEAR}-{limit}")

    for field in ("price_amount", "mileage_km", "power_kw", "area_sqm",
                  "price_per_sqm_amount", "rooms"):
        if field in record:
            _positive_number(record, field, found)

    price = record.get("price_amount")
    currency = record.get("price_currency")
    if price is not None and not currency:
        found.append("price_currency: required whenever price_amount is set")
    if currency is not None and (
        not isinstance(currency, str) or len(currency) != 3 or not currency.isupper()
    ):
        found.append(f"price_currency: must be a 3-letter ISO 4217 code, got {currency!r}")

    for field, allowed in (
        ("fuel", FUELS),
        ("transmission", TRANSMISSIONS),
        ("seller_type", SELLER_TYPES),
        ("property_type", PROPERTY_TYPES),
        ("transaction", TRANSACTIONS),
        ("status", COMPANY_STATUSES),
        ("employment_type", EMPLOYMENT_TYPES),
        ("workplace_type", WORKPLACE_TYPES),
    ):
        value = record.get(field)
        if value is not None and value not in allowed:
            found.append(f"{field}: {value!r} is not one of {', '.join(sorted(allowed))}")

    valid_flag = record.get("is_valid")
    if "is_valid" in record and valid_flag is not None and not isinstance(valid_flag, bool):
        found.append(
            f"is_valid: must be a real boolean, got {type(valid_flag).__name__}. "
            f"A string here is how a validation result silently inverts."
        )

    status = record.get("check_status")
    if status is not None and status not in VAT_CHECK_STATUSES:
        found.append(
            f"check_status: {status!r} is not one of {', '.join(sorted(VAT_CHECK_STATUSES))}"
        )
    # The invariant the whole VAT tool turns on: a verdict of valid or invalid
    # must carry a boolean, and no verdict must carry None. Getting this
    # backwards tells a customer a real VAT number is fake.
    if status == "unchecked" and record.get("is_valid") is not None:
        found.append("is_valid: must be None when check_status is 'unchecked'")
    if status in ("valid", "invalid") and not isinstance(record.get("is_valid"), bool):
        found.append(f"is_valid: must be a boolean when check_status is {status!r}")

    country = record.get("country_code")
    if country is not None and (
        not isinstance(country, str) or len(country) != 2 or not country.isupper()
    ):
        found.append(f"country_code: must be a 2-letter code, got {country!r}")

    for field in ("salary_min", "salary_max"):
        if field in record:
            _positive_number(record, field, found)
    low, high = record.get("salary_min"), record.get("salary_max")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
        found.append(f"salary_min: {low} is above salary_max {high}")
    salary_currency = record.get("salary_currency")
    if (low is not None or high is not None) and not salary_currency:
        found.append("salary_currency: required whenever a salary figure is set")
    if salary_currency is not None and (
        not isinstance(salary_currency, str)
        or len(salary_currency) != 3
        or not salary_currency.isupper()
    ):
        found.append(
            f"salary_currency: must be a 3-letter ISO 4217 code, got {salary_currency!r}"
        )

    remote = record.get("is_remote")
    if remote is not None and not isinstance(remote, bool):
        found.append(f"is_remote: must be a boolean, got {type(remote).__name__}")

    for field in ("incorporated_date", "dissolved_date", "last_updated",
                  "checked_date", "posted_date", "updated_date", "first_seen"):
        value = record.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            found.append(f"{field}: must be a YYYY-MM-DD string")
            continue
        try:
            date.fromisoformat(value)
        except ValueError:
            found.append(f"{field}: {value!r} is not a valid YYYY-MM-DD date")

    listed = record.get("listed_date")
    if listed is not None:
        if not isinstance(listed, str):
            found.append("listed_date: must be a YYYY-MM-DD string")
        else:
            try:
                date.fromisoformat(listed)
            except ValueError:
                found.append(f"listed_date: {listed!r} is not a valid YYYY-MM-DD date")

    return found


def is_valid(record: dict, this_year: int | None = None, kind: str = "vehicle") -> bool:
    return not problems(record, this_year, kind)
