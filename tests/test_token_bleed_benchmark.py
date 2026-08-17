import json
import random
import tempfile
import unittest
from unittest import mock
from argparse import Namespace
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import token_bleed_benchmark as benchmark


class GovernedCandidateTests(unittest.TestCase):
    def test_false_negatives_are_removed_and_false_positives_retained(self):
        columns = [
            {"fqname": "A.SSN", "is_gov_id": True},
            {"fqname": "A.PASSPORT_NO", "is_gov_id": True},
            {"fqname": "A.TAX_ID", "is_gov_id": False},
            {"fqname": "A.LICENSE_NO", "is_gov_id": False},
        ]
        key = {"A.SSN", "A.PASSPORT_NO"}
        candidates = benchmark.governed_candidates(columns, key, 1.0, 0.5, random.Random(7))
        self.assertEqual(len(candidates), 3)
        self.assertEqual(len(set(candidates) & key), 1)
        self.assertEqual(len(set(candidates) - key), 2)

    def test_zero_false_negative_rate_retains_every_true_positive(self):
        columns = [
            {"fqname": "A.SSN", "is_gov_id": True},
            {"fqname": "A.PASSPORT_NO", "is_gov_id": True},
            {"fqname": "A.TAX_ID", "is_gov_id": False},
        ]
        key = {"A.SSN", "A.PASSPORT_NO"}
        candidates = benchmark.governed_candidates(columns, key, 0.0, 0.0, random.Random(7))
        self.assertEqual(set(candidates), key)

    def test_catalog_has_fixed_positive_and_decoy_quotas(self):
        first, first_key = benchmark.build_catalog(300, 11)
        second, second_key = benchmark.build_catalog(300, 12)
        self.assertEqual(len(first), 300)
        self.assertEqual(len(second), 300)
        self.assertEqual(len(first_key), 6)
        self.assertEqual(len(second_key), 6)
        def decoys(columns):
            return [c for c in columns if any(c["fqname"].split(".", 1)[1].startswith(f"{d}_")
                                              for d in benchmark.DECOY_COLUMNS)]
        self.assertEqual(len(decoys(first)), 24)
        self.assertEqual(len(decoys(second)), 24)

    def test_lexical_baseline_is_name_only_and_not_answer_key(self):
        columns = [
            {"fqname": "A.SSN_1", "is_gov_id": True},
            {"fqname": "A.ID_DOC_NUMBER_2", "is_gov_id": True},
            {"fqname": "A.TAX_ID_3", "is_gov_id": False},
        ]
        self.assertEqual(benchmark.lexical_candidates(columns), ["A.SSN_1"])

    def test_r4_opaque_schema_has_no_lexical_government_id_shortcut(self):
        columns, key = benchmark.build_r4_catalog(300, 82)
        self.assertTrue(key)
        self.assertEqual(benchmark.lexical_candidates(columns), [])
        self.assertTrue(all("r4_metadata" in column for column in columns))
        # The answer key is policy-aware: restricted Government-ID fields are present but excluded.
        restricted_gov = [column for column in columns if column["is_gov_id"] and
                          column["r4_metadata"]["access_policy"] == "restricted"]
        self.assertTrue(restricted_gov)
        self.assertTrue(all(column["fqname"] not in key for column in restricted_gov))

    def test_r4_preflight_retains_semantic_access_scenario(self):
        result = benchmark.preflight_context([1200], 82, 1.0, 0.0, 131072, 3000,
                                             "r4-semantic-access")
        self.assertTrue(result["passed"])
        self.assertEqual({row["scenario"] for row in result["rows"]}, {"r4-semantic-access"})

    def test_r5_compact_metadata_uses_codes_without_exposing_the_answer_key(self):
        column = {
            "fqname": "TABLE.PERSON_REF_1",
            "r5_compact": True,
            "r4_metadata": {
                "business_term": "government-issued identity number",
                "lineage": "identity-vault",
                "access_policy": "approved",
            },
        }
        self.assertEqual(benchmark._catalog_line(column, compact=True), "TABLE.PERSON_REF_1|t=GID|l=IDV|p=A")

    def test_r5_all_seed_preflight_covers_every_seed_and_condition(self):
        columns = [{"fqname": "TABLE.FIELD", "is_gov_id": False}]
        with mock.patch.object(benchmark, "build_catalog_for_scenario", return_value=(columns, set())):
            result = benchmark.preflight_context_for_seeds(
                [300], [102, 103], 1.0, [0.0, 0.1], 10000, 1024,
                "r5-compact-semantic-access",
            )
        self.assertTrue(result["passed"])
        self.assertEqual(len(result["rows"]), 12)
        self.assertEqual({row["seed"] for row in result["rows"]}, {102, 103})
        self.assertEqual({row["classifier_fn_rate"] for row in result["rows"]}, {0.0, 0.1})

    def test_route_order_is_seeded_and_preserves_every_route(self):
        first = [name for name, _ in benchmark.randomized_routes(42)]
        again = [name for name, _ in benchmark.randomized_routes(42)]
        other = [name for name, _ in benchmark.randomized_routes(43)]
        expected = {name for name, _ in benchmark.ROUTES}
        self.assertEqual(first, again)
        self.assertEqual(set(first), expected)
        self.assertEqual(set(other), expected)

    def test_r3_route_order_is_condition_specific_and_deterministic(self):
        zero = [name for name, _ in benchmark.randomized_routes(62, 0.0)]
        again = [name for name, _ in benchmark.randomized_routes(62, 0.0)]
        sensitivity = [name for name, _ in benchmark.randomized_routes(62, 0.1)]
        self.assertEqual(zero, again)
        self.assertEqual(set(zero), {name for name, _ in benchmark.ROUTES})
        self.assertEqual(set(sensitivity), {name for name, _ in benchmark.ROUTES})


class ReportTests(unittest.TestCase):
    def test_report_records_classifier_and_catalog_conditions(self):
        args = Namespace(seed=42, replicates=1, classifier_fp_rate=1.0, classifier_fn_rate=0.1)
        row = {
            "tier": 300, "seed": 42, "route": "governed (metadata layer)",
            "catalog_columns": 299, "answer_key_count": 5,
            "prompt_tokens": 10, "completion_tokens": 2, "reasoning_tokens": 0,
            "total_tokens": 12, "latency_s": 1.0, "precision": 1.0, "recall": 0.8, "f1": 0.889,
        }
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / "report.json"
            benchmark.write_report(report, "example-model", args, [row])
            data = json.loads(report.read_text())
        self.assertEqual(data["classifier_fn_rate"], 0.1)
        self.assertFalse(data["classifier_recall_assumed_perfect"])
        self.assertEqual(data["results"][0]["catalog_columns"], 299)
        self.assertEqual(data["results"][0]["answer_key_count"], 5)
        self.assertEqual(data["schema_version"], "1.0")
        self.assertIn("git_commit", data)
        self.assertIn("package_versions", data)

    def test_aggregate_records_raw_distribution_and_confidence_interval(self):
        rows = [
            {"tier": 300, "route": "test", "prompt_tokens": 10, "completion_tokens": 2,
             "reasoning_tokens": 0, "total_tokens": 12, "latency_s": 1, "precision": 0.5,
             "recall": 0.5, "f1": 0.5},
            {"tier": 300, "route": "test", "prompt_tokens": 20, "completion_tokens": 2,
             "reasoning_tokens": 0, "total_tokens": 22, "latency_s": 1, "precision": 1.0,
             "recall": 1.0, "f1": 1.0},
        ]
        summary = benchmark.aggregate(rows)[0]
        self.assertEqual(summary["prompt_tokens_values"], [10, 20])
        self.assertLess(summary["f1_ci95_low"], summary["f1_mean"])
        self.assertGreater(summary["f1_ci95_high"], summary["f1_mean"])

    def test_aggregate_separates_classifier_sensitivity_conditions(self):
        rows = [
            {"tier": 300, "route": "test", "classifier_fn_rate": 0.0, "prompt_tokens": 10,
             "completion_tokens": 2, "reasoning_tokens": 0, "total_tokens": 12, "latency_s": 1,
             "precision": 0.5, "recall": 0.5, "f1": 0.5},
            {"tier": 300, "route": "test", "classifier_fn_rate": 0.1, "prompt_tokens": 20,
             "completion_tokens": 2, "reasoning_tokens": 0, "total_tokens": 22, "latency_s": 1,
             "precision": 1.0, "recall": 1.0, "f1": 1.0},
        ]
        summary = benchmark.aggregate(rows)
        self.assertEqual(len(summary), 2)
        self.assertEqual({item["classifier_fn_rate"] for item in summary}, {0.0, 0.1})

    def test_r2_context_preflight_refuses_oversized_constructed_input(self):
        result = benchmark.preflight_context(
            [300], 42, 1.0, 0.0, context_window_tokens=100, max_tokens=10
        )
        self.assertFalse(result["passed"])
        self.assertTrue(result["failures"])
        self.assertEqual(result["rows"][0]["token_count_method"], "utf8_byte_upper_bound")

    def test_r2_runtime_context_guard_retains_a_failed_attempt_without_calling_provider(self):
        result = benchmark._call_route("x" * 101, context_window_tokens=100, max_tokens=1)
        self.assertFalse(result["success"])
        self.assertEqual(result["attempts"][0]["outcome"], "context_preflight_refused")
        self.assertIsNone(result["prompt_truncated_by_context"])

    def test_r2_ollama_context_probe_requires_live_context_at_budget(self):
        response = mock.MagicMock()
        response.read.return_value = json.dumps({"models": [{
            "name": "test-model", "context_length": 65536,
        }]}).encode()
        response.__enter__.return_value = response
        with mock.patch.dict("os.environ", {"OPENAI_MODEL": "test-model"}, clear=False), \
             mock.patch.object(benchmark, "call_model", return_value={
                 "success": True, "returned_model": "test-model"
             }), \
             mock.patch.object(benchmark.urllib.request, "urlopen", return_value=response):
            benchmark._REQUEST_OPTIONS = {"num_ctx": 65536}
            observed = benchmark.verify_ollama_runtime_context(65536)
        self.assertEqual(observed["observed_context_length"], 65536)
        self.assertEqual(observed["requested_num_ctx"], 65536)

    def test_r2_completion_cap_probe_requires_observed_cap(self):
        with mock.patch.object(benchmark, "call_model", return_value={
            "success": True, "completion_tokens": 8, "token_parameter": "max_tokens",
            "returned_model": "test-model",
        }):
            observed = benchmark.verify_completion_cap_enforcement(cap=8)
        self.assertTrue(observed["enforced"])
        self.assertEqual(observed["token_parameter"], "max_tokens")

    def test_r2_completion_cap_probe_fails_closed_if_server_exceeds_cap(self):
        with mock.patch.object(benchmark, "call_model", return_value={
            "success": True, "completion_tokens": 9, "token_parameter": "max_completion_tokens",
            "returned_model": "test-model",
        }):
            observed = benchmark.verify_completion_cap_enforcement(cap=8)
        self.assertFalse(observed["enforced"])

    def test_local_ollama_uses_max_tokens_not_accept_and_ignore_parameter(self):
        captured = []
        def fake_post(payload, _base, _key, timeout=None):
            captured.append(payload)
            return {"model": "test-model", "choices": [{"message": {"content": "OK"}}],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}}
        previous = benchmark._TOKEN_PARAM
        try:
            benchmark._TOKEN_PARAM = "max_tokens"
            with mock.patch.dict("os.environ", {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}, clear=False), \
                 mock.patch.object(benchmark, "_post", side_effect=fake_post):
                result = benchmark.call_model("test", max_tokens=8, retries=1)
        finally:
            benchmark._TOKEN_PARAM = previous
        self.assertTrue(result["success"])
        self.assertEqual(result["token_parameter"], "max_tokens")
        self.assertEqual(captured[0]["max_tokens"], 8)
        self.assertNotIn("max_completion_tokens", captured[0])

    def test_r2_persisted_row_retains_completion_cap_provenance(self):
        result = {
            "prompt_tokens": 10, "completion_tokens": 2, "reasoning_tokens": 0,
            "total_tokens": 12, "latency_s": 1.0, "route_preparation_ms": 0.1,
            "constructed_input_token_count": 20, "context_window_tokens": 100,
            "requested_completion_tokens": 8, "prompt_truncated_by_context": False,
            "token_parameter": "max_tokens", "completion_cap_enforced": True,
            "completion_cap_parameter": "max_tokens",
        }
        persisted = benchmark.persisted_route_fields(result)
        self.assertEqual(persisted["token_parameter"], "max_tokens")
        self.assertTrue(persisted["completion_cap_enforced"])
        self.assertEqual(persisted["completion_cap_parameter"], "max_tokens")


class ParsingTests(unittest.TestCase):
    def test_negated_column_is_not_scored_as_an_answer(self):
        found = benchmark.parse_answer("A.SSN\ndo not include A.TAX_ID", ["A.SSN", "A.TAX_ID"])
        self.assertEqual(found, {"A.SSN"})


if __name__ == "__main__":
    unittest.main()
