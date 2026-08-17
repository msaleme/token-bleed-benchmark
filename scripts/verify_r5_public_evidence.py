#!/usr/bin/env python3
"""Verify the public Token-Bleed R5 packet and regenerate its ACE decision summary.

This verifies published derived artifacts only. It cannot verify the private raw report or attest
to the original Mac-side collection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROUTES = {
    "ungoverned (context-stuffing)",
    "lexical prefilter (cheap baseline)",
    "governed (metadata layer)",
}
TIERS = {300, 800, 1200}
SEEDS = set(range(102, 122))
FN_RATES = {0.0, 0.05, 0.1}
EXPECTED_CLAIMS = {
    "selective_context_cost_vs_full": "ACCEPTED",
    "governed_quality_vs_full": "ACCEPTED",
    "governed_value_vs_lexical": "REJECTED",
    "governed_sensitivity_vs_lexical": "REJECTED",
}


def fail(message: str) -> None:
    raise ValueError(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path}") from exc
    if not isinstance(value, dict):
        fail(f"expected JSON object: {path}")
    return value


def parse_manifest(path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, separator, name = line.partition("  ")
        if not separator or len(digest) != 64:
            fail(f"invalid SHA256SUMS line: {line}")
        entries[name] = digest
    return entries


def claim_verdicts(pack: dict) -> dict[str, str]:
    claims = pack.get("claim_scoped_assessments", pack.get("claim_scoped_verdicts"))
    if not isinstance(claims, dict):
        fail("artifact lacks claim-scoped verdicts")
    verdicts = {name: value.get("verdict") for name, value in claims.items() if isinstance(value, dict)}
    if verdicts != EXPECTED_CLAIMS:
        fail(f"unexpected claim verdicts: {verdicts}")
    return verdicts


def verify_packet(root: Path) -> tuple[Path, Path, dict]:
    evidence_dir = root / "evidence" / "token-bleed-mac-r5"
    manifest = parse_manifest(evidence_dir / "SHA256SUMS.txt")
    required = {"preflight.json", "ace-evidence.json", "ace-decision-pack.json"}
    if not required.issubset(manifest):
        fail("SHA256SUMS lacks one or more published artifact digests")
    raw_entry = "report.json (retained raw evidence; not published because it embeds host identifiers)"
    if raw_entry not in manifest:
        fail("SHA256SUMS lacks the private raw-report hash commitment")
    for name in required:
        path = evidence_dir / name
        if not path.is_file() or sha256(path) != manifest[name]:
            fail(f"SHA-256 mismatch: {name}")

    preflight = load_json(evidence_dir / "preflight.json")
    rows = preflight.get("rows")
    if not isinstance(rows, list) or len(rows) != 540:
        fail("R5 preflight must retain exactly 540 rows")
    observed = set()
    for row in rows:
        if not isinstance(row, dict):
            fail("preflight row is not an object")
        key = (row.get("tier"), row.get("seed"), row.get("route"), row.get("classifier_fn_rate"))
        if key in observed:
            fail(f"duplicate preflight row: {key}")
        observed.add(key)
        if key[0] not in TIERS or key[1] not in SEEDS or key[2] not in ROUTES or key[3] not in FN_RATES:
            fail(f"unexpected R5 preflight row: {key}")
        if row.get("scenario") != "r5-compact-semantic-access" or row.get("fits_context_budget") is not True:
            fail(f"preflight row is not an R5 context-fit: {key}")
    expected = {(tier, seed, route, rate) for tier in TIERS for seed in SEEDS for route in ROUTES for rate in FN_RATES}
    if observed != expected:
        fail("preflight matrix does not cover every frozen R5 condition")

    contract = root / "experiments" / "token-bleed-mac-r5.yaml"
    evidence = load_json(evidence_dir / "ace-evidence.json")
    published_pack = load_json(evidence_dir / "ace-decision-pack.json")
    contract_digest = sha256(contract)
    if evidence.get("config_sha256") != contract_digest or published_pack.get("config_sha256") != contract_digest:
        fail("ACE artifact config digest does not match the frozen R5 contract")
    if published_pack.get("verdict") != "ACCEPTED":
        fail("published generic ACE verdict is not ACCEPTED")
    claim_verdicts(evidence)
    claim_verdicts(published_pack)
    return contract, evidence_dir / "ace-evidence.json", published_pack


def verify_ace_regeneration(contract: Path, evidence: Path, published_pack: dict, ace_command: str) -> None:
    with tempfile.TemporaryDirectory(prefix="token-bleed-r5-ace-") as temporary:
        output = Path(temporary) / "assessment"
        subprocess.run([ace_command, "assess", str(contract), str(evidence), "--output", str(output)], check=True)
        regenerated = load_json(output / "token-bleed-mac-r5.decision-pack.json")
    if regenerated.get("verdict") != published_pack.get("verdict"):
        fail("regenerated ACE generic verdict differs from published decision pack")
    if regenerated.get("config_sha256") != published_pack.get("config_sha256"):
        fail("regenerated ACE config digest differs from published decision pack")
    if claim_verdicts(regenerated) != claim_verdicts(published_pack):
        fail("regenerated ACE claim verdicts differ from published decision pack")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ace-command", default="ace", help="ACE 0.1.2 command to run")
    parser.add_argument("--skip-ace", action="store_true", help="verify the public packet without regenerating ACE output")
    args = parser.parse_args()
    contract, evidence, published_pack = verify_packet(args.root.resolve())
    if not args.skip_ace:
        verify_ace_regeneration(contract, evidence, published_pack, args.ace_command)
    print("R5 public evidence verification passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"R5 public evidence verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
