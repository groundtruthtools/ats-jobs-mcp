"""Shared core for the multi-market listings portfolio.

One core, one adapter per site. See STRATEGY.md for why the portfolio is
shaped this way, and listing.py for the two rules the schema enforces.
"""

from . import adapter, listing, money, paging, units

__all__ = ["adapter", "listing", "money", "paging", "units"]
