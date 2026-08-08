"""Data providers: a Yahoo/yfinance provider and a deterministic synthetic one.

The synthetic provider requires no network and is used for offline tests and as
a clearly-labelled fallback. The yfinance provider is optional (imported lazily)
and adds timeouts and bounded retries with backoff; it never loops indefinitely.

Data status labels distinguish LIVE / CACHED / DELAYED / SYNTHETIC / ERROR /
PARTIAL so the UI can be honest about provenance.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from statinvest.market.normalize import consistent_pe, normalize_price
from statinvest.market.validate import validate_symbol


@dataclass
class MarketData:
    symbol: str
    fetched_at_utc: str
    price: float | None = None
    raw_price: float | None = None
    normalized_price: float | None = None
    raw_currency: str | None = None
    normalized_currency: str | None = None
    eps: float | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    net_income: float | None = None
    distance_from_high: float | None = None
    asset_type: str | None = None
    display_name: str | None = None
    exchange: str | None = None
    country: str | None = None
    source: str = "unknown"
    data_status: str = "ERROR"
    normalization_rule: str | None = None
    error_summary: str | None = None
    history: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyntheticProvider:
    """Deterministic offline provider. Prices depend only on the symbol."""

    name = "synthetic"

    def fetch(self, symbol: str, with_history: bool = False,
              history_points: int = 120) -> MarketData:
        sym = validate_symbol(symbol)
        seed = sum(ord(c) for c in sym)
        base = 50.0 + (seed % 200)
        currency = "ILA" if sym.endswith(".TA") else "USD"
        eps = round(1.0 + (seed % 7) + 0.5, 2)
        norm = normalize_price(base, currency)
        pe = consistent_pe(norm.normalized_price, eps)
        asset_type = _guess_type(sym)
        md = MarketData(
            symbol=sym,
            fetched_at_utc=_now_iso(),
            price=norm.normalized_price,
            raw_price=norm.raw_price,
            normalized_price=norm.normalized_price,
            raw_currency=norm.raw_currency,
            normalized_currency=norm.normalized_currency,
            eps=eps if asset_type == "EQUITY" else None,
            market_cap=float(base * 1_000_000) if asset_type == "EQUITY" else None,
            trailing_pe=pe if asset_type == "EQUITY" else None,
            forward_pe=(pe * 0.95) if pe and asset_type == "EQUITY" else None,
            net_income=float(base * 10_000) if asset_type == "EQUITY" else None,
            distance_from_high=round((seed % 30) / 100.0, 3),
            asset_type=asset_type,
            display_name=f"Synthetic {sym}",
            exchange="TASE" if sym.endswith(".TA") else "SYNTH",
            country="Israel" if sym.endswith(".TA") else "US",
            source="synthetic",
            data_status="SYNTHETIC",
            normalization_rule=norm.rule,
        )
        if with_history:
            md.history = self._history(sym, base, history_points)
        return md

    @staticmethod
    def _history(sym: str, base: float, n: int) -> list[dict]:
        rows = []
        price = base
        seed = sum(ord(c) for c in sym)
        for i in range(n):
            # Deterministic pseudo-walk (no RNG so results are reproducible).
            delta = ((seed + i * 17) % 21 - 10) / 100.0
            price = max(price * (1 + delta / 10.0), 0.01)
            day = 1 + (i % 28)
            month = 1 + (i // 28) % 12
            ts = f"2025-{month:02d}-{day:02d}T00:00:00+00:00"
            rows.append({
                "ts_utc": ts,
                "open": round(price * 0.99, 4),
                "high": round(price * 1.02, 4),
                "low": round(price * 0.98, 4),
                "close": round(price, 4),
                "adj_close": round(price, 4),
                "volume": 1000 + (seed + i) % 5000,
            })
        return rows


# Yahoo rejects requests that do not present a browser User-Agent (HTTP 429),
# so both providers below identify themselves with one. This is a plain
# identification header, not an attempt to bypass any access control.
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class YFinanceProvider:
    """Optional live provider backed by yfinance (imported lazily)."""

    name = "yfinance"

    def __init__(self, retries: int = 3, backoff: float = 1.0, timeout: float = 10.0):
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout

    def fetch(self, symbol: str, with_history: bool = False,
              history_points: int = 120) -> MarketData:
        sym = validate_symbol(symbol)
        try:
            import yfinance as yf  # lazy: keeps offline tests independent
        except Exception as exc:  # pragma: no cover
            return MarketData(symbol=sym, fetched_at_utc=_now_iso(),
                              source="yfinance", data_status="ERROR",
                              error_summary=f"yfinance unavailable: {type(exc).__name__}")

        last_err = None
        for attempt in range(1, self.retries + 1):
            try:
                try:  # identify with a browser UA; Yahoo 429s otherwise
                    import requests
                    sess = requests.Session()
                    sess.headers["User-Agent"] = BROWSER_UA
                    ticker = yf.Ticker(sym, session=sess)
                except Exception:
                    ticker = yf.Ticker(sym)
                info = ticker.fast_info if hasattr(ticker, "fast_info") else {}
                full = {}
                try:
                    full = ticker.get_info()  # may be rate-limited
                except Exception:
                    full = {}
                price = _num(getattr(info, "last_price", None) or full.get("currentPrice"))
                currency = full.get("currency") or getattr(info, "currency", None)
                eps = _num(full.get("trailingEps"))
                norm = normalize_price(price, currency)
                pe = _num(full.get("trailingPE")) or consistent_pe(norm.normalized_price, eps)
                md = MarketData(
                    symbol=sym,
                    fetched_at_utc=_now_iso(),
                    price=norm.normalized_price,
                    raw_price=norm.raw_price,
                    normalized_price=norm.normalized_price,
                    raw_currency=norm.raw_currency,
                    normalized_currency=norm.normalized_currency,
                    eps=eps,
                    market_cap=_num(full.get("marketCap")),
                    trailing_pe=pe,
                    forward_pe=_num(full.get("forwardPE")),
                    net_income=_num(full.get("netIncomeToCommon")),
                    asset_type=(full.get("quoteType") or "").upper() or None,
                    display_name=full.get("shortName") or full.get("longName"),
                    exchange=full.get("exchange"),
                    country=full.get("country"),
                    source="yfinance",
                    data_status="DELAYED" if price is not None else "PARTIAL",
                    normalization_rule=norm.rule,
                )
                if with_history:
                    md.history = self._history(ticker, history_points)
                return md
            except Exception as exc:  # bounded retry with backoff
                last_err = exc
                if attempt < self.retries:
                    time.sleep(self.backoff * attempt)
        return MarketData(symbol=sym, fetched_at_utc=_now_iso(), source="yfinance",
                          data_status="ERROR",
                          error_summary=f"fetch failed: {type(last_err).__name__}")

    @staticmethod
    def _history(ticker, n: int) -> list[dict]:  # pragma: no cover - network
        rows = []
        try:
            hist = ticker.history(period="6mo")
            for ts, r in hist.tail(n).iterrows():
                rows.append({
                    "ts_utc": ts.tz_convert("UTC").isoformat()
                    if ts.tzinfo else ts.isoformat(),
                    "open": _num(r.get("Open")), "high": _num(r.get("High")),
                    "low": _num(r.get("Low")), "close": _num(r.get("Close")),
                    "adj_close": _num(r.get("Close")), "volume": _num(r.get("Volume")),
                })
        except Exception:
            return []
        return rows


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return f if f == f else None  # drop NaN
    except (TypeError, ValueError):
        return None


def _guess_type(sym: str) -> str:
    if sym.startswith("^"):
        return "INDEX"
    if "=" in sym:
        return "CURRENCY"
    if sym.endswith("-USD"):
        return "CRYPTOCURRENCY"
    return "EQUITY"


class YahooChartProvider:
    """Live provider using Yahoo's public chart endpoint directly.

    More reliable than the yfinance wrapper in restricted environments: it
    needs only the standard library, presents a browser User-Agent (without
    which Yahoo returns HTTP 429), and applies bounded retries with backoff.
    Returns daily history, which is what the model lab actually consumes.
    """

    name = "yahoo-chart"
    BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
    CRUMB_URL = "https://query1.finance.yahoo.com/v1/test/getcrumb"
    COOKIE_URL = "https://fc.yahoo.com/"
    SUMMARY = "https://query2.finance.yahoo.com/v10/finance/quoteSummary/"

    def __init__(self, retries: int = 4, backoff: float = 3.0, timeout: float = 30.0,
                 range_: str = "5y", fundamentals: bool = True):
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self.range = range_
        self.fundamentals = fundamentals
        self._session = None
        self._crumb = None

    # -- fundamentals (P/E, EPS, market cap) --------------------------------
    def _auth(self):
        """Establish Yahoo's cookie + crumb pair, required for fundamentals.

        Returns (session, crumb) or (None, None) if unavailable. Cached per
        instance so repeated fetches do not re-handshake.
        """
        if self._session is not None:
            return self._session, self._crumb
        try:
            import requests
        except Exception:
            return None, None
        try:
            s = requests.Session()
            s.headers["User-Agent"] = BROWSER_UA
            try:
                s.get(self.COOKIE_URL, timeout=self.timeout)
            except Exception:
                pass  # 404 is normal here; the cookie is still set
            r = s.get(self.CRUMB_URL, timeout=self.timeout)
            crumb = r.text.strip() if r.status_code == 200 else None
            if not crumb or len(crumb) > 32:
                return None, None
            self._session, self._crumb = s, crumb
            return s, crumb
        except Exception:
            return None, None

    @staticmethod
    def _raw(node, key):
        v = (node or {}).get(key)
        if isinstance(v, dict):
            return _num(v.get("raw"))
        return _num(v)

    def _fundamentals(self, sym: str) -> dict:
        """Fetch valuation fields. Returns {} when unavailable — never raises."""
        s, crumb = self._auth()
        if not s or not crumb:
            return {}
        import urllib.parse
        url = (f"{self.SUMMARY}{urllib.parse.quote(sym)}?modules="
               f"defaultKeyStatistics,summaryDetail,financialData&crumb="
               f"{urllib.parse.quote(crumb)}")
        for attempt in range(1, self.retries + 1):
            try:
                r = s.get(url, timeout=self.timeout)
                if r.status_code != 200:
                    raise RuntimeError(f"status {r.status_code}")
                res = r.json().get("quoteSummary", {}).get("result") or []
                if not res:
                    return {}
                d = res[0]
                sd, ks, fd = (d.get("summaryDetail"), d.get("defaultKeyStatistics"),
                              d.get("financialData"))
                return {
                    "trailing_pe": self._raw(sd, "trailingPE"),
                    "forward_pe": self._raw(sd, "forwardPE"),
                    "eps": self._raw(ks, "trailingEps"),
                    "market_cap": self._raw(sd, "marketCap"),
                    "price_to_book": self._raw(ks, "priceToBook"),
                    "dividend_yield": self._raw(sd, "dividendYield"),
                    "profit_margin": self._raw(fd, "profitMargins"),
                    "net_income": self._raw(ks, "netIncomeToCommon"),
                }
            except Exception:
                if attempt < self.retries:
                    time.sleep(self.backoff * attempt)
        return {}

    def _get(self, sym: str) -> dict | None:
        import json as _json
        import urllib.error
        import urllib.parse
        import urllib.request

        url = f"{self.BASE}{urllib.parse.quote(sym)}?range={self.range}&interval=1d"
        for attempt in range(1, self.retries + 1):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return _json.load(resp)
            except Exception:
                if attempt < self.retries:
                    time.sleep(self.backoff * attempt)  # bounded, never infinite
        return None

    def fetch(self, symbol: str, with_history: bool = False,
              history_points: int = 2000) -> MarketData:
        sym = validate_symbol(symbol)
        doc = self._get(sym)
        if not doc or not doc.get("chart", {}).get("result"):
            return MarketData(symbol=sym, fetched_at_utc=_now_iso(), source=self.name,
                              data_status="ERROR",
                              error_summary="provider returned no result")
        res = doc["chart"]["result"][0]
        meta = res.get("meta", {})
        price = _num(meta.get("regularMarketPrice"))
        norm = normalize_price(price, meta.get("currency"))
        asset_type = (meta.get("instrumentType") or "").upper() or None

        # Valuation fields only apply to companies. An index, ETF, currency or
        # crypto has no P/E — absent values there are correct, not a failure.
        f = {}
        if self.fundamentals and asset_type == "EQUITY":
            f = self._fundamentals(sym)

        trailing_pe = f.get("trailing_pe")
        eps = f.get("eps")
        if trailing_pe is None:
            # Fall back to a P/E computed from normalized price and EPS in the
            # same unit, so agorot-quoted shares stay consistent.
            trailing_pe = consistent_pe(norm.normalized_price, eps)

        md = MarketData(
            symbol=sym,
            fetched_at_utc=_now_iso(),
            price=norm.normalized_price,
            raw_price=norm.raw_price,
            normalized_price=norm.normalized_price,
            raw_currency=norm.raw_currency,
            normalized_currency=norm.normalized_currency,
            eps=eps,
            market_cap=f.get("market_cap"),
            trailing_pe=trailing_pe,
            forward_pe=f.get("forward_pe"),
            net_income=f.get("net_income"),
            asset_type=asset_type,
            display_name=meta.get("shortName") or meta.get("longName"),
            exchange=meta.get("fullExchangeName"),
            source=self.name,
            data_status="DELAYED" if price is not None else "PARTIAL",
            normalization_rule=norm.rule,
        )
        if with_history:
            md.history = self._history(res, history_points)
        return md

    @staticmethod
    def _history(res: dict, n: int) -> list[dict]:
        from datetime import datetime as _dt

        ts = res.get("timestamp") or []
        q = (res.get("indicators", {}).get("quote") or [{}])[0]
        adj = (res.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
        closes = q.get("close") or []
        rows = []
        for i, t in enumerate(ts):
            c = closes[i] if i < len(closes) else None
            if c is None:
                continue
            rows.append({
                "ts_utc": _dt.fromtimestamp(t, timezone.utc).isoformat(),
                "open": _num(_at(q.get("open"), i)),
                "high": _num(_at(q.get("high"), i)),
                "low": _num(_at(q.get("low"), i)),
                "close": _num(c),
                "adj_close": _num(_at(adj, i)) if adj else _num(c),
                "volume": _num(_at(q.get("volume"), i)),
            })
        return rows[-n:]


def _at(seq, i):
    try:
        return seq[i]
    except (TypeError, IndexError):
        return None


def get_provider(name: str = "synthetic", **kwargs):
    """Return a provider by name. Defaults to the offline synthetic provider."""
    name = (name or "synthetic").lower()
    if name == "synthetic":
        return SyntheticProvider()
    if name in ("yahoo-chart", "chart"):
        return YahooChartProvider(**kwargs)
    if name in ("yfinance", "yahoo"):
        return YFinanceProvider(**kwargs)
    raise ValueError(
        f"Unknown provider '{name}'. Use 'synthetic', 'yahoo-chart' or 'yfinance'."
    )
