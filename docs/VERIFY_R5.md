# Verify the public R5 evidence packet

The public R5 packet is intentionally privacy-safe. It contains the frozen contract, complete
preflight, ACE trial evidence, ACE decision pack, and hashes. It does not contain the raw Mac
report because that report embeds host identifiers.

From a clean checkout:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install ace-experiment-framework==0.1.2
python3 scripts/verify_r5_public_evidence.py
```

The command verifies the published SHA-256 entries, the complete 540-row R5 preflight matrix, the
frozen contract digest, the generic and claim-scoped verdicts, and regenerates an ACE decision
pack from the public trial evidence. It cannot independently reproduce the original model calls,
attest to the Mac collection, or inspect the private raw report.

For a local artifact-only check when ACE is intentionally unavailable:

```bash
python3 scripts/verify_r5_public_evidence.py --skip-ace
```

The published digests also verify with stock coreutils, from either evidence directory:

```bash
cd evidence/token-bleed-mac-r5 && sha256sum -c SHA256SUMS.txt
```

The withheld raw report is recorded on a `#` comment line, so this check exits 0 over the files
that are actually published while its digest stays committed for chain of custody.
