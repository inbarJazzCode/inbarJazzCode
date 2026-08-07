"""Symbol validation.

A ticker is *never* passed to a shell. Validation rejects empty values, control
characters, path-like input and unreasonably long input, while preserving
provider syntax such as index (``^GSPC``), exchange suffix (``TEVA.TA``),
currency (``EURUSD=X``) and crypto (``BTC-USD``) forms.
"""

from __future__ import annotations

import re

MAX_SYMBOL_LEN = 24
# Allow letters, digits and the small set of punctuation Yahoo actually uses.
_ALLOWED = re.compile(r"^[A-Za-z0-9.\-=^]+$")


class SymbolError(ValueError):
    """Raised when a symbol fails validation."""


def validate_symbol(symbol: str) -> str:
    if not isinstance(symbol, str):
        raise SymbolError("Symbol must be a string.")
    s = symbol.strip()
    if not s:
        raise SymbolError("Symbol must not be empty.")
    if len(s) > MAX_SYMBOL_LEN:
        raise SymbolError(f"Symbol too long (> {MAX_SYMBOL_LEN} characters).")
    if any(ord(c) < 0x20 for c in s):
        raise SymbolError("Symbol contains control characters.")
    if "/" in s or "\\" in s or ".." in s:
        raise SymbolError("Symbol looks path-like; rejected.")
    if not _ALLOWED.match(s):
        raise SymbolError(
            "Symbol contains unsupported characters. Allowed: letters, digits and . - = ^"
        )
    return s.upper()
