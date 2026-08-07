"""Safe JSON serialization of model specifications and results.

Model persistence uses JSON only — never pickle — so a stored run cannot execute
arbitrary code on load. Numpy scalars/arrays are converted to native types. A
lightweight secret scan refuses to serialize obvious credential-like keys.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import numpy as np

_SECRET_KEY_RE = re.compile(
    r"(pass(word)?|secret|token|api[_-]?key|private[_-]?key|credential)", re.IGNORECASE
)


def _to_native(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _SECRET_KEY_RE.search(str(k)):
                raise ValueError(f"Refusing to serialize secret-like key: {k!r}")
            out[str(k)] = _to_native(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_to_native(v) for v in obj.tolist()]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def serialize_run(
    spec: dict, result: dict, provenance: dict | None = None, seed: int | None = None
) -> str:
    """Return a reproducible JSON document describing a model run."""
    payload = {
        "schema": "statinvest.run/v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "specification": _to_native(spec),
        "result": _to_native(result),
        "provenance": _to_native(provenance or {}),
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def deserialize_run(text: str) -> dict:
    doc = json.loads(text)
    if doc.get("schema") != "statinvest.run/v1":
        raise ValueError("Unrecognized run schema.")
    return doc
