#!/usr/bin/env python3
"""Convert retained Token-Bleed reports into ACE trial evidence.

R1 reports stay incomplete by design. R2 reports retain exact seed pairs, context fit,
request attempts, and route-preparation timing so this adapter can compute only the
prespecified statistics from supplied observations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paired_analysis import paired_bootstrap_percentile_ci, paired_permutation_test


ROUTE_UNGOVERNED = "ungoverned (context-stuffing)"
ROUTE_GOVERNED = "governed (metadata layer)"
TIER_SPLITS = {300: "development", 1500: "validation", 3000: "holdout"}
EPSILON_MS = 0.001


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _r2_provenance_error(report: dict) -> str | None:
    provenance = report.get("r2_provenance")
    if not isinstance(provenance, dict):
        return "report lacks R2 endpoint provenance"
    missing = [field for field in ("endpoint_class", "model_digest", "runtime_version", "hardware")
               if not provenance.get(field)]
    if missing:
        return f"report lacks R2 provenance fields: {', '.join(missing)}"
    execution = report.get("r2_execution")
    if not isinstance(execution, dict) or execution.get("completion_cap_enforced") is not True:
        return "report lacks a verified enforced completion cap"
    if execution.get("completion_cap_parameter") != "max_tokens":
        return "report lacks the enforced completion-cap parameter"
    return None


def _r2_row_error(row: dict, route: str) -> str | None:
    if row.get("success") is not True:
        return f"{route} route has a retained terminal failure: {row.get('error_message') or 'unspecified'}"
    if not isinstance(row.get("attempts"), list) or not row["attempts"]:
        return f"{route} route lacks structured request attempts"
    if row.get("prompt_truncated_by_context") is not False:
        return f"{route} route is truncated or truncation status is not retained"
    required = ("context_window_tokens", "constructed_input_token_count", "requested_completion_tokens")
    if not all(isinstance(row.get(field), int) and row[field] > 0 for field in required):
        return f"{route} route lacks a complete context-budget record"
    if row["constructed_input_token_count"] + row["requested_completion_tokens"] > row["context_window_tokens"]:
        return f"{route} route exceeds its retained context budget"
    if not isinstance(row.get("route_preparation_ms"), (int, float)) or row["route_preparation_ms"] < 0:
        return f"{route} route lacks measured route-preparation time"
    if row.get("completion_cap_enforced") is not True or row.get("completion_cap_parameter") != "max_tokens":
        return f"{route} route lacks verified completion-cap enforcement"
    if row.get("token_parameter") != "max_tokens":
        return f"{route} route lacks the actual enforced completion-cap parameter"
    completion_tokens = row.get("completion_tokens")
    if not isinstance(completion_tokens, int) or completion_tokens < 0 or completion_tokens > row["requested_completion_tokens"]:
        return f"{route} route exceeds or lacks its retained completion cap"
    return None


def convert(report_path: Path, contract_path: Path) -> dict:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = report.get("results")
    if report.get("schema_version") not in {"1.0", "2.0"} or not isinstance(rows, list) or not rows:
        raise ValueError("report must be a non-empty Token-Bleed schema_version 1.0 or 2.0 report")
    source_revision = report.get("git_commit")
    if not source_revision:
        raise ValueError("report does not retain git_commit")
    is_r2 = report.get("schema_version") == "2.0"
    provenance_error = _r2_provenance_error(report) if is_r2 else None

    paired: dict[tuple[int, int], dict[str, dict]] = {}
    for row in rows:
        try:
            tier, seed, route = int(row["tier"]), int(row["seed"]), row["route"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("each report row needs integer tier/seed and route") from exc
        if tier in TIER_SPLITS and route in {ROUTE_UNGOVERNED, ROUTE_GOVERNED}:
            paired.setdefault((tier, seed), {})[route] = row

    trials, baseline_values = [], []
    development_f1_differences, development_ecd_values = [], []
    for (tier, seed), routes in sorted(paired.items()):
        baseline, governed = routes.get(ROUTE_UNGOVERNED), routes.get(ROUTE_GOVERNED)
        trial = {"trial_id": f"tier-{tier}-seed-{seed}", "seed": seed,
                 "split": TIER_SPLITS[tier], "success": bool(baseline and governed),
                 "metrics": {}, "metric_sources": {}}
        if not trial["success"]:
            trial["error_message"] = "retained report is missing an ungoverned or governed route row"
        else:
            if isinstance(baseline.get("f1"), (int, float)):
                baseline_values.append(float(baseline["f1"]))
            error = provenance_error
            if is_r2 and not error:
                error = _r2_row_error(baseline, "ungoverned") or _r2_row_error(governed, "governed")
            prompt_tokens, governed_prompt_tokens = baseline.get("prompt_tokens"), governed.get("prompt_tokens")
            if error:
                trial["success"] = False
                trial["error_message"] = error
            elif not all(isinstance(value, (int, float)) and value > 0
                         for value in (prompt_tokens, governed_prompt_tokens)):
                trial["success"] = False
                trial["error_message"] = "paired rows lack positive measured prompt-token counts"
            elif not all(isinstance(row.get("f1"), (int, float)) for row in (baseline, governed)):
                trial["success"] = False
                trial["error_message"] = "paired rows lack measured F1 values"
            else:
                ecd = 1 - float(governed_prompt_tokens) / float(prompt_tokens)
                trial["metrics"] = {"f1": float(governed["f1"]), "ecd_improvement": ecd}
                trial["metric_sources"] = {
                    "f1": "measured model response scored against retained synthetic answer key",
                    "ecd_improvement": "derived from measured prompt-token usage in paired retained rows",
                }
                if is_r2:
                    complexity = ((float(governed["route_preparation_ms"]) - float(baseline["route_preparation_ms"])) /
                                  max(float(baseline["route_preparation_ms"]), EPSILON_MS))
                    trial["metrics"]["complexity_overhead"] = complexity
                    trial["metric_sources"]["complexity_overhead"] = (
                        "derived from measured online route-preparation milliseconds; epsilon_ms=0.001"
                    )
                    if trial["split"] == "development":
                        development_f1_differences.append(float(governed["f1"]) - float(baseline["f1"]))
                        development_ecd_values.append(ecd)
        trials.append(trial)

    if not baseline_values:
        raise ValueError("no complete governed/ungoverned pairs were available")
    evidence = {
        "schema_version": "1.0", "artifact_type": "ace-trial-evidence",
        "experiment_id": contract_path.stem,
        "config_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(),
        "source_revision": source_revision, "telemetry_provenance": "measured",
        "baseline_metrics": {"f1": _mean(baseline_values)}, "trials": trials,
        "adapter_notes": [
            "Each tier is a declared ACE split; no tuning is performed by this adapter.",
            "R1 reports leave unavailable complexity/statistical evidence absent so ACE fails closed.",
        ],
    }
    if is_r2 and len(development_f1_differences) == 20 and len(development_ecd_values) == 20:
        f1_test = paired_permutation_test(development_f1_differences)
        ecd_ci = paired_bootstrap_percentile_ci(development_ecd_values)
        evidence["statistical_evidence"] = {"development": {
            "p_value": f1_test["p_value"], "ecd_confidence_interval": ecd_ci["interval"],
            "f1_permutation_test": f1_test, "ecd_bootstrap": ecd_ci,
            "paired_values": {"governed_minus_ungoverned_f1": development_f1_differences,
                              "ecd_improvement": development_ecd_values},
        }}
    elif is_r2:
        evidence["adapter_notes"].append(
            "R2 development pairs are incomplete; statistical evidence is intentionally absent."
        )
    return evidence


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
