#!/usr/bin/env python3
"""Convert a retained Token-Bleed report into ACE trial evidence.

This is a provenance-preserving adapter, not an assessment.  It pairs the retained
ungoverned and governed rows for each declared seed/tier, labels the three catalog
tiers as development/validation/holdout, and leaves unavailable complexity/statistical
evidence absent so ACE can fail closed rather than manufacture it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROUTE_UNGOVERNED = "ungoverned (context-stuffing)"
ROUTE_GOVERNED = "governed (metadata layer)"
TIER_SPLITS = {300: "development", 1500: "validation", 3000: "holdout"}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def convert(report_path: Path, contract_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = report.get("results")
    if report.get("schema_version") != "1.0" or not isinstance(rows, list) or not rows:
        raise ValueError("report must be a non-empty Token-Bleed schema_version 1.0 report")
    source_revision = report.get("git_commit")
    if not source_revision:
        raise ValueError("report does not retain git_commit")

    paired: dict[tuple[int, int], dict[str, dict]] = {}
    for row in rows:
        try:
            tier, seed, route = int(row["tier"]), int(row["seed"]), row["route"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("each report row needs integer tier/seed and route") from exc
        if tier not in TIER_SPLITS or route not in {ROUTE_UNGOVERNED, ROUTE_GOVERNED}:
            continue
        paired.setdefault((tier, seed), {})[route] = row

    trials = []
    baseline_values = []
    for (tier, seed), routes in sorted(paired.items()):
        baseline = routes.get(ROUTE_UNGOVERNED)
        governed = routes.get(ROUTE_GOVERNED)
        trial = {
            "trial_id": f"tier-{tier}-seed-{seed}",
            "seed": seed,
            "split": TIER_SPLITS[tier],
            "success": bool(baseline and governed),
            "metrics": {},
            "metric_sources": {},
        }
        if not trial["success"]:
            trial["error_message"] = "retained report is missing an ungoverned or governed route row"
        else:
            prompt_tokens = baseline.get("prompt_tokens")
            governed_prompt_tokens = governed.get("prompt_tokens")
            if not all(isinstance(value, (int, float)) and value > 0 for value in (prompt_tokens, governed_prompt_tokens)):
                trial["success"] = False
                trial["error_message"] = "paired rows lack positive measured prompt-token counts"
            elif not isinstance(governed.get("f1"), (int, float)) or not isinstance(baseline.get("f1"), (int, float)):
                trial["success"] = False
                trial["error_message"] = "paired rows lack measured F1 values"
            else:
                baseline_values.append(float(baseline["f1"]))
                trial["metrics"] = {
                    "f1": float(governed["f1"]),
                    "ecd_improvement": 1 - (float(governed_prompt_tokens) / float(prompt_tokens)),
                }
                trial["metric_sources"] = {
                    "f1": "measured model response scored against retained synthetic answer key",
                    "ecd_improvement": "derived from measured prompt-token usage in paired retained rows",
                }
        trials.append(trial)

    if not baseline_values:
        raise ValueError("no complete governed/ungoverned pairs were available")
    contract_sha256 = hashlib.sha256(contract_path.read_bytes()).hexdigest()
    contract_id = contract_path.stem
    return {
        "schema_version": "1.0",
        "artifact_type": "ace-trial-evidence",
        "experiment_id": contract_id,
        "config_sha256": contract_sha256,
        "source_revision": source_revision,
        "telemetry_provenance": "measured",
        "baseline_metrics": {"f1": _mean(baseline_values)},
        "trials": trials,
        "adapter_notes": [
            "Each tier is a declared ACE split; no tuning is performed by this adapter.",
            "Complexity and statistical evidence are intentionally not inferred from Token-Bleed rows.",
            "ACE must mark a record inconclusive when its contract requires evidence this report does not retain.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("contract", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    evidence = convert(args.report, args.contract)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
