# Token-Bleed R3 Mac runbook

Do not run this document until the pull request that introduces it is merged. R3 is a new,
prospective experiment. R1, R2, and R2.1 evidence must remain unchanged.

## Immutable collection command

From a fresh checkout of the merged `main`, confirm the commit and contract checksum before any
benchmark request:

```bash
git rev-parse HEAD
shasum -a 256 experiments/token-bleed-mac-r3.yaml
ace preflight experiments/token-bleed-mac-r3.yaml
```

The controller will supply the required merged commit and resulting SHA-256. Refuse collection if
either differs from the supplied values.

Then run exactly one command. It retains all 540 rows: 3 tiers × 20 seeds × 3 routes × 3
classifier false-negative conditions. It must not be split, shortened, or selectively rerun.

```bash
mkdir -p evidence/token-bleed-mac-r3
python3 token_bleed_benchmark.py \
  --r3 --r2 --tiers 300 1500 3000 --seed 62 --replicates 20 \
  --classifier-fp-rate 1.0 --classifier-fn-rates 0 0.05 0.10 \
  --timeout 1800 --context-window-tokens 131072 --max-completion-tokens 3000 \
  --endpoint-class local-openai-compatible \
  --model-digest "$TOKEN_BLEED_MODEL_DIGEST" \
  --runtime-version "$(ollama --version)" \
  --hardware "$(system_profiler SPHardwareDataType SPSoftwareDataType)" \
  --ollama-num-ctx 131072 --verify-ollama-context --retain-responses \
  --preflight-out evidence/token-bleed-mac-r3/preflight.json \
  --out evidence/token-bleed-mac-r3/report.json
shasum -a 256 evidence/token-bleed-mac-r3/preflight.json evidence/token-bleed-mac-r3/report.json \
  > evidence/token-bleed-mac-r3/SHA256SUMS.txt
```

`TOKEN_BLEED_MODEL_DIGEST` must be set to the immutable digest recorded by the environment probe,
not a mutable tag. If preflight, context verification, or the completion-cap probe fails, the
command exits before collecting benchmark rows. Retain that failure artifact and stop.

After a completed run, send the three files unmodified: `preflight.json`, `report.json`, and
`SHA256SUMS.txt`. Do not interpret the results or rerun only unfavorable conditions. The controller
will verify hashes and assess the claim-scoped evidence against the unchanged contract.
