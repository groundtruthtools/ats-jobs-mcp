"""Unit conversions for vehicle listings. Pure, exact, and sourced.

Every constant here is a defined exact value, not a measurement, so each one
can be checked against a published definition rather than against this code.
That is what makes Tier A golden records possible for this module.
"""

# 1 international mile = 1609.344 metres exactly.
# Source: International Yard and Pound Agreement of 1959 (1 yd = 0.9144 m
# exactly, 1 mile = 1760 yd), retrieved 2026-08-23.
METRES_PER_MILE = 1609.344
KM_PER_MILE = 1.609344

# 1 metric horsepower (PS, cv, pk) = 735.49875 watts exactly.
# Source: DIN 66036 (75 kgf*m/s, with g = 9.80665 m/s^2), retrieved 2026-08-23.
WATTS_PER_PS = 735.49875

# 1 mechanical horsepower (hp, bhp) = 745.6998715822702 watts.
# Source: 550 foot-pounds-force per second, from the exact definitions
# 1 ft = 0.3048 m, 1 lbf = 0.45359237 kgf, g = 9.80665 m/s^2.
WATTS_PER_HP = 745.6998715822702


def _round_or_none(value, digits: int):
    if value is None:
        return None
    return round(value, digits) if digits else int(round(value))


def miles_to_km(miles: float | int | None) -> float | None:
    """UK and US adverts quote mileage in miles; the record stores km."""
    if miles is None or isinstance(miles, bool):
        return None
    return round(float(miles) * KM_PER_MILE, 1)


def km_to_miles(km: float | int | None) -> float | None:
    if km is None or isinstance(km, bool):
        return None
    return round(float(km) / KM_PER_MILE, 1)


def ps_to_kw(ps: float | int | None) -> float | None:
    """German, Italian and Polish adverts quote PS/CV/KM; the record stores kW."""
    if ps is None or isinstance(ps, bool):
        return None
    return round(float(ps) * WATTS_PER_PS / 1000.0, 2)


def kw_to_ps(kw: float | int | None) -> float | None:
    if kw is None or isinstance(kw, bool):
        return None
    return round(float(kw) * 1000.0 / WATTS_PER_PS, 1)


def hp_to_kw(hp: float | int | None) -> float | None:
    """UK adverts quote bhp."""
    if hp is None or isinstance(hp, bool):
        return None
    return round(float(hp) * WATTS_PER_HP / 1000.0, 2)


def kw_to_hp(kw: float | int | None) -> float | None:
    if kw is None or isinstance(kw, bool):
        return None
    return round(float(kw) * 1000.0 / WATTS_PER_HP, 1)
