# Token-Bleed R5 Mac runbook

Do not modify, rerun, or replace any R4 artifact. R5 is authorized only after the controller
supplies the merged `main` commit and the SHA-256 of `experiments/token-bleed-mac-r5.yaml`.

On a fresh checkout at that commit, run these checks before any benchmark request:

```bash
git rev-parse HEAD
shasum -a 256 experiments/token-bleed-mac-r5.yaml
ace validate experiments/token-bleed-mac-r5.yaml
ace preflight experiments/token-bleed-mac-r5.yaml
```

Refuse collection unless every supplied value matches and ACE preflight says
`ready_to_measure: true` with no warnings. Preserve prior evidence unchanged.

Then run exactly this one command. It preflights all 20 seeds and all three false-negative
conditions before it makes a model call. If preflight, live context verification, or completion
cap verification fails, retain the failure artifact and stop. Do not add calibration rows,
substitute seeds, split the collection, or selectively rerun a condition.

```bash
mkdir -p evidence/token-bleed-mac-r5
python3 token_bleed_benchmark.py \
  --r5 --r2 --tiers 300 800 1200 --seed 102 --replicates 20 \
  --classifier-fp-rate 1.0 --classifier-fn-rates 0 0.05 0.10 \
  --timeout 1800 --context-window-tokens 131072 --max-completion-tokens 1024 \
  --endpoint-class local-openai-compatible \
  --model-digest "$TOKEN_BLEED_MODEL_DIGEST" \
  --runtime-version "$(ollama --version)" \
  --hardware "$(system_profiler SPHardwareDataType SPSoftwareDataType)" \
  --ollama-num-ctx 131072 --verify-ollama-context --retain-responses \
  --preflight-out evidence/token-bleed-mac-r5/preflight.json \
  --out evidence/token-bleed-mac-r5/report.json
shasum -a 256 evidence/token-bleed-mac-r5/preflight.json evidence/token-bleed-mac-r5/report.json \
  > evidence/token-bleed-mac-r5/SHA256SUMS.txt
```

The retained report must contain exactly 540 rows: 3 tiers × 20 seeds × 3 routes × 3 conditions.
Return only the unmodified `preflight.json`, `report.json`, `SHA256SUMS.txt`, and run log to the
controller. The controller will verify checksums and assess against the unchanged contract.
