import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "token_bleed_to_ace.py"
SPEC = importlib.util.spec_from_file_location("token_bleed_to_ace", MODULE_PATH)
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


class TokenBleedToAceTests(unittest.TestCase):
    def test_converts_retained_route_pairs_without_inventing_missing_evidence(self):
        rows = []
        for tier in (300, 1500, 3000):
            for route, prompt, f1 in (
                (adapter.ROUTE_UNGOVERNED, 100, 0.8),
                (adapter.ROUTE_GOVERNED, 20, 0.9),
            ):
                rows.append({"tier": tier, "seed": 42, "route": route, "prompt_tokens": prompt, "f1": f1})
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            contract = Path(tmp) / "token-bleed-local-ollama-r1.yaml"
            report.write_text(json.dumps({"schema_version": "1.0", "git_commit": "abc123", "results": rows}))
            contract.write_text("experiment_id: token-bleed-local-ollama-r1\n")
            evidence = adapter.convert(report, contract)
        self.assertEqual(evidence["experiment_id"], "token-bleed-local-ollama-r1")
        self.assertEqual(len(evidence["trials"]), 3)
        self.assertEqual(evidence["trials"][0]["metrics"]["ecd_improvement"], 0.8)
        self.assertNotIn("complexity_overhead", evidence["trials"][0]["metrics"])
        self.assertNotIn("statistical_evidence", evidence)
