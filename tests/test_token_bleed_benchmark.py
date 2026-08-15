import json
import random
import tempfile
import unittest
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

    def test_route_order_is_seeded_and_preserves_every_route(self):
        first = [name for name, _ in benchmark.randomized_routes(42)]
        again = [name for name, _ in benchmark.randomized_routes(42)]
        other = [name for name, _ in benchmark.randomized_routes(43)]
        expected = {name for name, _ in benchmark.ROUTES}
        self.assertEqual(first, again)
        self.assertEqual(set(first), expected)
        self.assertEqual(set(other), expected)


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


class ParsingTests(unittest.TestCase):
    def test_negated_column_is_not_scored_as_an_answer(self):
        found = benchmark.parse_answer("A.SSN\ndo not include A.TAX_ID", ["A.SSN", "A.TAX_ID"])
        self.assertEqual(found, {"A.SSN"})


if __name__ == "__main__":
    unittest.main()
