"""Shared statistical-modeling laboratory.

Model families:
    * :mod:`statinvest.models.linear`   — OLS / linear regression (stable QR/SVD).
    * :mod:`statinvest.models.logistic` — binary logistic regression (IRLS).
    * :mod:`statinvest.models.poisson`  — Poisson regression (IRLS, log link).

Supporting modules:
    * :mod:`statinvest.models.transforms`  — auditable specification transforms.
    * :mod:`statinvest.models.optim`       — SGD/Adam optimization laboratory.
    * :mod:`statinvest.models.evaluation`  — leakage-resistant chronological splits.
    * :mod:`statinvest.models.serialize`   — safe JSON serialization of runs.
"""

from statinvest.models.linear import OLSModel, OLSResult
from statinvest.models.logistic import LogisticModel, LogisticResult
from statinvest.models.poisson import PoissonModel, PoissonResult

__all__ = [
    "OLSModel",
    "OLSResult",
    "LogisticModel",
    "LogisticResult",
    "PoissonModel",
    "PoissonResult",
]
