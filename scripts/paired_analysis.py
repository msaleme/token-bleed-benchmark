"""Deterministic paired analysis for Token-Bleed R2 retained evidence.

This module consumes complete matched seed pairs.  It never reconstructs observations from
aggregate console output and keeps the resampling configuration in the returned artifact.
"""

from __future__ import annotations

import math
import random
from typing import Iterable


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a percentile of an empty sample")
    index = (len(ordered) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def paired_permutation_test(differences: Iterable[float]) -> dict:
    """Exact two-sided paired sign-flip permutation test.

    R2 has 20 pairs, so enumerating all 2^20 sign assignments is cheap and avoids a
    Monte-Carlo p-value.  The test statistic is the mean paired difference.
    """
    values = [float(value) for value in differences]
    if not values:
        raise ValueError("paired permutation test requires at least one difference")
    observed = sum(values) / len(values)
    threshold = abs(observed)
    extreme = 0
    total = 1 << len(values)
    for mask in range(total):
        signed_sum = sum(value if mask & (1 << index) else -value for index, value in enumerate(values))
        if abs(signed_sum / len(values)) >= threshold - 1e-12:
            extreme += 1
    return {
        "method": "exact two-sided paired sign-flip permutation test",
        "alternative": "two-sided",
        "statistic": "mean(governed_f1 - ungoverned_f1)",
        "observed_statistic": observed,
        "p_value": extreme / total,
        "permutations": total,
        "random_seed": None,
    }


def paired_bootstrap_percentile_ci(
    values: Iterable[float], *, resamples: int = 10_000, random_seed: int = 20260815
) -> dict:
    """Return a deterministic 95% percentile bootstrap CI for matched-pair values."""
    observed = [float(value) for value in values]
    if not observed:
        raise ValueError("paired bootstrap requires at least one value")
    if resamples < 1:
        raise ValueError("resamples must be positive")
    rng = random.Random(random_seed)
    n = len(observed)
    means = [sum(observed[rng.randrange(n)] for _ in range(n)) / n for _ in range(resamples)]
    return {
        "method": "paired bootstrap percentile confidence interval",
        "confidence_level": 0.95,
        "resamples": resamples,
        "random_seed": random_seed,
        "statistic": "mean(ecd_improvement)",
        "observed_statistic": sum(observed) / n,
        "interval": [_percentile(means, 0.025), _percentile(means, 0.975)],
    }
