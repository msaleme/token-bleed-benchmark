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


class ParsingTests(unittest.TestCase):
    def test_negated_column_is_not_scored_as_an_answer(self):
        found = benchmark.parse_answer("A.SSN\ndo not include A.TAX_ID", ["A.SSN", "A.TAX_ID"])
        self.assertEqual(found, {"A.SSN"})


if __name__ == "__main__":
    unittest.main()
