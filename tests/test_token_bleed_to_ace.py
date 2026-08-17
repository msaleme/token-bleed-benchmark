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
    def test_r5_compact_semantic_evidence_uses_new_seeds_and_claims(self):
        rows = []
        for tier in (300, 800, 1200):
            for seed in range(102, 122):
                for rate in (0.0, 0.05, 0.1):
                    for route, prompt, f1 in ((adapter.ROUTE_UNGOVERNED, 100, 0.4),
                                              (adapter.ROUTE_LEXICAL, 20, 0.1),
                                              (adapter.ROUTE_GOVERNED, 40, 0.8)):
                        rows.append({"tier": tier, "seed": seed, "route": route, "classifier_fn_rate": rate,
                                     "scenario": "r5-compact-semantic-access", "success": True,
                                     "attempts": [{"attempt": 1, "outcome": "success"}], "prompt_tokens": prompt,
                                     "completion_tokens": 10, "token_parameter": "max_tokens", "f1": f1,
                                     "route_preparation_ms": 1.0, "prompt_truncated_by_context": False,
                                     "context_window_tokens": 10000, "constructed_input_token_count": 500,
                                     "requested_completion_tokens": 1024, "completion_cap_enforced": True,
                                     "completion_cap_parameter": "max_tokens"})
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r5.yaml"
            report.write_text(json.dumps({"schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x", "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": True, "completion_cap_parameter": "max_tokens"}}))
            contract.write_text("experiment_id: token-bleed-mac-r5\n")
            evidence = adapter.convert(report, contract)
        self.assertEqual({trial["split"] for trial in evidence["trials"]}, {"development", "validation", "holdout"})
        self.assertEqual(evidence["claim_scoped_verdicts"]["governed_value_vs_lexical"]["verdict"], "ACCEPTED")

    def test_r4_semantic_access_evidence_uses_r4_splits_and_claims(self):
        rows = []
        for tier in (300, 800, 1200):
            for seed in range(82, 102):
                for rate in (0.0, 0.05, 0.1):
                    for route, prompt, f1 in ((adapter.ROUTE_UNGOVERNED, 100, 0.4),
                                              (adapter.ROUTE_LEXICAL, 20, 0.1),
                                              (adapter.ROUTE_GOVERNED, 40, 0.8)):
                        rows.append({"tier": tier, "seed": seed, "route": route, "classifier_fn_rate": rate,
                                     "scenario": "r4-semantic-access", "success": True,
                                     "attempts": [{"attempt": 1, "outcome": "success"}], "prompt_tokens": prompt,
                                     "completion_tokens": 10, "token_parameter": "max_tokens", "f1": f1,
                                     "route_preparation_ms": 1.0, "prompt_truncated_by_context": False,
                                     "context_window_tokens": 10000, "constructed_input_token_count": 500,
                                     "requested_completion_tokens": 100, "completion_cap_enforced": True,
                                     "completion_cap_parameter": "max_tokens"})
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r4.yaml"
            report.write_text(json.dumps({"schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x", "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": True, "completion_cap_parameter": "max_tokens"}}))
            contract.write_text("experiment_id: token-bleed-mac-r4\n")
            evidence = adapter.convert(report, contract)
        self.assertEqual({trial["split"] for trial in evidence["trials"]}, {"development", "validation", "holdout"})
        self.assertEqual(evidence["claim_scoped_verdicts"]["governed_value_vs_lexical"]["verdict"], "ACCEPTED")

    def test_r4_wrong_scenario_is_inconclusive(self):
        rows = []
        for tier in (300, 800, 1200):
            for seed in range(82, 102):
                for rate in (0.0, 0.05, 0.1):
                    for route, prompt, f1 in ((adapter.ROUTE_UNGOVERNED, 100, 0.5),
                                              (adapter.ROUTE_LEXICAL, 20, 0.2),
                                              (adapter.ROUTE_GOVERNED, 40, 0.8)):
                        rows.append({"tier": tier, "seed": seed, "route": route, "classifier_fn_rate": rate,
                                     "scenario": "r3-name-selection", "success": True,
                                     "attempts": [{"attempt": 1, "outcome": "success"}], "prompt_tokens": prompt,
                                     "completion_tokens": 10, "token_parameter": "max_tokens", "f1": f1,
                                     "route_preparation_ms": 1.0, "prompt_truncated_by_context": False,
                                     "context_window_tokens": 10000, "constructed_input_token_count": 500,
                                     "requested_completion_tokens": 100, "completion_cap_enforced": True,
                                     "completion_cap_parameter": "max_tokens"})
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r4.yaml"
            report.write_text(json.dumps({"schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x", "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": True, "completion_cap_parameter": "max_tokens"}}))
            contract.write_text("experiment_id: token-bleed-mac-r4\n")
            evidence = adapter.convert(report, contract)
        self.assertEqual(evidence["claim_scoped_verdicts"]["governed_value_vs_lexical"]["verdict"], "INCONCLUSIVE")

    def test_r3_missing_sensitivity_pair_is_inconclusive(self):
        rows = []
        for tier in (300, 1500, 3000):
            for seed in range(62, 82):
                for rate in (0.0, 0.05, 0.1):
                    for route, prompt, f1 in ((adapter.ROUTE_UNGOVERNED, 100, 0.5),
                                              (adapter.ROUTE_LEXICAL, 20, 0.6),
                                              (adapter.ROUTE_GOVERNED, 20, 0.7)):
                        if tier == 3000 and seed == 62 and rate == 0.1 and route == adapter.ROUTE_GOVERNED:
                            continue
                        rows.append({"tier": tier, "seed": seed, "route": route, "classifier_fn_rate": rate,
                                     "success": True, "attempts": [{"attempt": 1, "outcome": "success"}],
                                     "prompt_tokens": prompt, "completion_tokens": 10, "token_parameter": "max_tokens",
                                     "f1": f1, "route_preparation_ms": 1.0, "prompt_truncated_by_context": False,
                                     "context_window_tokens": 10000, "constructed_input_token_count": 500,
                                     "requested_completion_tokens": 100, "completion_cap_enforced": True,
                                     "completion_cap_parameter": "max_tokens"})
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r3.yaml"
            report.write_text(json.dumps({"schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x", "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": True, "completion_cap_parameter": "max_tokens"}}))
            contract.write_text("experiment_id: token-bleed-mac-r3\n")
            evidence = adapter.convert(report, contract)
        self.assertEqual(evidence["claim_scoped_verdicts"]["governed_sensitivity_vs_lexical"]["verdict"], "INCONCLUSIVE")
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

    def test_r2_retains_paired_statistics_and_complexity(self):
        rows = []
        for tier in (300, 1500, 3000):
            for seed in range(42, 62):
                for route, prompt, f1, preparation in (
                    (adapter.ROUTE_UNGOVERNED, 100, 0.4, 2.0),
                    (adapter.ROUTE_GOVERNED, 20, 0.8, 3.0),
                ):
                    rows.append({
                        "tier": tier, "seed": seed, "route": route, "success": True,
                        "attempts": [{"attempt": 1, "outcome": "success"}],
                        "prompt_tokens": prompt, "completion_tokens": 10, "token_parameter": "max_tokens",
                        "f1": f1, "route_preparation_ms": preparation,
                        "prompt_truncated_by_context": False, "context_window_tokens": 10000,
                        "constructed_input_token_count": 500, "requested_completion_tokens": 100,
                        "completion_cap_enforced": True, "completion_cap_parameter": "max_tokens",
                    })
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r2.yaml"
            report.write_text(json.dumps({
                "schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x",
                                  "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": True,
                                 "completion_cap_parameter": "max_tokens"},
            }))
            contract.write_text("experiment_id: token-bleed-mac-r2\n")
            evidence = adapter.convert(report, contract)
        self.assertEqual(len(evidence["trials"]), 60)
        self.assertEqual(evidence["trials"][0]["metrics"]["complexity_overhead"], 0.5)
        self.assertEqual(len(evidence["statistical_evidence"]["development"]["paired_values"]["ecd_improvement"]), 20)
        self.assertLess(evidence["statistical_evidence"]["development"]["p_value"], 0.05)

    def test_r2_truncation_fails_the_paired_trial(self):
        rows = []
        for route in (adapter.ROUTE_UNGOVERNED, adapter.ROUTE_GOVERNED):
            rows.append({
                "tier": 300, "seed": 42, "route": route, "success": True,
                "attempts": [{"attempt": 1, "outcome": "success"}], "prompt_tokens": 100,
                "completion_tokens": 10, "token_parameter": "max_tokens",
                "f1": 0.8, "route_preparation_ms": 1.0,
                "prompt_truncated_by_context": route == adapter.ROUTE_UNGOVERNED,
                "context_window_tokens": 10000, "constructed_input_token_count": 500,
                "requested_completion_tokens": 100,
                "completion_cap_enforced": True, "completion_cap_parameter": "max_tokens",
            })
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r2.yaml"
            report.write_text(json.dumps({
                "schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x",
                                  "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": True,
                                 "completion_cap_parameter": "max_tokens"},
            }))
            contract.write_text("experiment_id: token-bleed-mac-r2\n")
            evidence = adapter.convert(report, contract)
        self.assertFalse(evidence["trials"][0]["success"])
        self.assertIn("truncated", evidence["trials"][0]["error_message"])

    def test_r2_unenforced_completion_cap_fails_the_paired_trial(self):
        rows = []
        for route in (adapter.ROUTE_UNGOVERNED, adapter.ROUTE_GOVERNED):
            rows.append({
                "tier": 300, "seed": 42, "route": route, "success": True,
                "attempts": [{"attempt": 1, "outcome": "success"}], "prompt_tokens": 100,
                "completion_tokens": 101, "token_parameter": "max_completion_tokens",
                "f1": 0.8, "route_preparation_ms": 1.0,
                "prompt_truncated_by_context": False, "context_window_tokens": 10000,
                "constructed_input_token_count": 500, "requested_completion_tokens": 100,
                "completion_cap_enforced": False, "completion_cap_parameter": "max_completion_tokens",
            })
        with tempfile.TemporaryDirectory() as tmp:
            report, contract = Path(tmp) / "report.json", Path(tmp) / "token-bleed-mac-r2-1.yaml"
            report.write_text(json.dumps({
                "schema_version": "2.0", "git_commit": "abc123", "results": rows,
                "r2_provenance": {"endpoint_class": "local", "model_digest": "sha256:x",
                                  "runtime_version": "test", "hardware": "test"},
                "r2_execution": {"completion_cap_enforced": False,
                                 "completion_cap_parameter": "max_completion_tokens"},
            }))
            contract.write_text("experiment_id: token-bleed-mac-r2-1\n")
            evidence = adapter.convert(report, contract)
        self.assertFalse(evidence["trials"][0]["success"])
        self.assertIn("completion cap", evidence["trials"][0]["error_message"])
