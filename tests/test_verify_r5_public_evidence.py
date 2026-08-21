import shutil
import subprocess
import sys
from pathlib import Path

import pytest


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


RAW_REPORT_ENTRY = (
    "report.json (retained raw evidence; not published because it embeds host identifiers)"
)
RAW_REPORT_R5_DIGEST = "051cafd6a2cc22cee700d33f049c221def334aa621e9c9f6431abcabf9daa18e"


@pytest.mark.skipif(shutil.which("sha256sum") is None, reason="GNU coreutils sha256sum not present")
@pytest.mark.parametrize("round_dir", ["token-bleed-mac-r3", "token-bleed-mac-r5"])
def test_sha256sums_verifies_cleanly_with_coreutils(round_dir):
    """A skeptic's first move is `sha256sum -c`; it must exit 0 on the published packet."""
    result = subprocess.run(
        ["sha256sum", "-c", "SHA256SUMS.txt"],
        cwd=ROOT / "evidence" / round_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_withheld_raw_report_digest_stays_committed():
    """Commenting the withheld entry must not drop the chain-of-custody digest."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from verify_r5_public_evidence import parse_manifest

    entries, commitments = parse_manifest(
        ROOT / "evidence" / "token-bleed-mac-r5" / "SHA256SUMS.txt"
    )
    assert RAW_REPORT_ENTRY not in entries, "withheld artifact must not be a checkable entry"
    assert commitments[RAW_REPORT_ENTRY] == RAW_REPORT_R5_DIGEST
