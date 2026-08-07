"""Currency / unit normalization with an auditable rule trail.

Tel Aviv Stock Exchange equities are frequently quoted in *agorot* (ILA), i.e.
1/100 of a shekel (ILS). When — and only when — the provider metadata indicates
ILA/agorot quoting do we divide by 100. We never blindly divide "every
Israeli-looking symbol" by 100, and we always keep the raw value plus the rule
that was applied so the calculation is auditable.
"""

from __future__ import annotations

from dataclasses import dataclass

AGOROT_PER_SHEKEL = 100.0


@dataclass
class Normalization:
    raw_price: float | None
    raw_currency: str | None
    normalized_price: float | None
    normalized_currency: str | None
    rule: str


def normalize_price(
    raw_price: float | None, raw_currency: str | None
) -> Normalization:
    """Return a :class:`Normalization` describing raw and normalized values.

    Only ILA/agorot quotes are converted (to ILS). All other currencies pass
    through unchanged, with the rule recorded as ``passthrough``.
    """
    if raw_price is None:
        return Normalization(None, raw_currency, None, raw_currency, "no-price")

    cur = (raw_currency or "").upper()
    if cur in ("ILA", "AGOROT"):
        return Normalization(
            raw_price=raw_price,
            raw_currency=raw_currency,
            normalized_price=raw_price / AGOROT_PER_SHEKEL,
            normalized_currency="ILS",
            rule=f"ILA/agorot -> ILS (divide by {AGOROT_PER_SHEKEL:g})",
        )
    return Normalization(
        raw_price=raw_price,
        raw_currency=raw_currency,
        normalized_price=raw_price,
        normalized_currency=raw_currency,
        rule="passthrough",
    )


def consistent_pe(price: float | None, eps: float | None) -> float | None:
    """Trailing P/E computed from *normalized* price and EPS in the same unit."""
    if price is None or eps is None or eps == 0:
        return None
    return price / eps
