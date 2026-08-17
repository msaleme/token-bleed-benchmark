import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_r5_packet_is_internally_verifiable_without_private_raw_report():
    result = subprocess.run(
        [sys.executable, "scripts/verify_r5_public_evidence.py", "--skip-ace"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "passed" in result.stdout
