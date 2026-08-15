# Token-Bleed Mac R2: publishable-evidence runbook

## Objective

Produce a retained, auditable result for one explicitly named local endpoint. The run is
publishable only if its complete evidence bundle passes the R2 contract through ACE. It must
not be presented as a general model, production, security, or vendor claim.

An `INCONCLUSIVE` or `REJECTED` ACE result is still a useful completed experiment, but it is not
a basis for a comparative performance claim.

## The R1 defects R2 must close

R1 is preserved as audit evidence. Do not overwrite, edit, or selectively rerun it.

| R1 issue | R2 acceptance condition |
| --- | --- |
| The 3000-object ungoverned prompt was truncated. | Every included split has a retained context-budget proof and `prompt_truncated_by_context: false` for both compared routes. A truncation makes that paired trial invalid and prevents an accepted comparative verdict. |
| Timeout retries only appeared in a text log. | Each route row retains an `attempts` array with attempt number, timestamps or elapsed time, outcome, error class/message, and final selected attempt. Failed pairs remain as failed ACE trials. |
| ACE had no p-value or confidence interval. | The adapter computes the predeclared paired analysis from the retained seed pairs and retains the method, alternative, statistic, p-value, CI, resampling seed, and all paired values or their immutable references. |
| ACE had no complexity metric. | The runner retains online route-preparation timing per paired seed as diagnostic provenance. It is not assumed to be zero and it is not substituted with model latency, but it is not an acceptance gate. |
| Endpoint identity was incomplete. | A run manifest retains the model identifier and digest, Ollama version, context limit, Mac hardware/OS, runner commit, ACE package version, and all command-line settings. |

## Commissioning gate

Do not start collection until the checked-out `main` contains the R2 implementation and its
commissioning fixes. The implementation must provide all of the following, with tests:

1. A versioned R2 contract, `experiments/token-bleed-mac-r2.yaml`.
2. A report schema revision that records `context_window_tokens`, requested completion budget,
   constructed-input token count, provider-reported prompt tokens, and a per-row
   `prompt_truncated_by_context` boolean.
3. A hard preflight refusal when constructed input plus completion budget exceeds the declared
   context window. Provider-reported usage alone is not proof that the full prompt was accepted.
4. Structured attempt retention for every request, including unsuccessful attempts and the final
   terminal failure. A retry is evidence, not disposable noise.
5. Direct measurement of route-preparation time around only the local route-building work.
   Store `route_preparation_ms` for both routes and derive `complexity_overhead` as diagnostic
   provenance. Retain the raw timings, formula, epsilon, and clock source. Do not label model
   latency as complexity overhead or treat microsecond-scale string-building time as a real
   governance-cost acceptance gate.
6. An adapter that emits `f1`, `ecd_improvement`, and diagnostic route-preparation evidence for each
   paired ACE trial, and marks any pair with truncation or terminal route failure as
   `success: false` with a specific error message.
7. A deterministic statistical-analysis module. It must use the exact paired seed records,
   never an aggregate mean reconstructed from the console log.
8. A test that proves: one truncated row, one failed attempt sequence, or missing statistical evidence
   each result in `INCONCLUSIVE` rather than an accepted result.

Do not solve these gaps by adding constants, hand-editing JSON, omitting a failed seed, or changing
the contract after calibration.

## R2 prespecification

Freeze this before calibration and record its SHA-256 in every output.

- **Endpoint scope:** one named Mac-local Ollama endpoint and one exact model digest. State the
  model's context window as configured by the serving runtime, not just a marketing context size.
- **Compared routes:** governed metadata layer versus ungoverned context stuffing. The lexical
  prefilter remains a disclosed cheap baseline, not the ACE baseline.
- **Splits:** development, validation, and holdout must all fit the endpoint context budget. If the
  3000-object raw prompt does not fit, either use a model/runtime with a verified budget sufficient
  for it, or declare new, smaller R2 tiers before collection. Do not rename a truncated tier as a
  holdout.
- **Calibration seed:** use seed `41`, which is outside the analysis seeds, only to test endpoint
  configuration and context fit. It is not part of the 20-seed analysis.
- **Analysis seeds:** `42` through `61`, fixed and complete on every split.
- **Primary quality metric:** F1, scored from retained raw model responses and retained answer keys.
- **Primary efficiency metric:** per-seed `ecd_improvement = 1 - governed_prompt_tokens /
  ungoverned_prompt_tokens`, using provider-reported prompt-token usage after the context proof
  passes.
- **Primary inference:** a two-sided, paired permutation test of the governed-minus-ungoverned F1
  difference across the 20 matched seeds on the development split. Retain the exact implementation,
  number of permutations, and random seed. The threshold is `p < 0.05`.
- **Uncertainty rule:** a 95% paired bootstrap percentile confidence interval for development
  `ecd_improvement`, resampling matched seed pairs. Retain bootstrap count, random seed, and CI.
  It must exclude zero in the favorable direction.
- **Transfer rule:** validation and holdout must each have all 20 valid matched pairs, mean F1 at
  least the ungoverned baseline, and mean ECD improvement above zero. Their role is confirmation,
  not a second search for a favorable result.
- **Route-preparation diagnostic:** retain online route-preparation measurements, but do not make a
  comparative claim or pass/fail judgment from microsecond-scale local string-building timing. It is
  not a defensible proxy for operating governance cost.

The R2 manuscript may report descriptive CIs for F1 and tokens on all splits. It must name the
development inference as the prespecified test and avoid treating multiple split checks as
independent discoveries.

## Mac operator procedure

### 1. Freeze source and environment

After the R2 implementation PR merges:

```bash
cd <token-bleed-benchmark>
git checkout main
git pull --ff-only
git rev-parse HEAD

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install 'ace-experiment-framework==0.1.0'

mkdir -p evidence/token-bleed-mac-r2
```

Record the exact commands, `git status --short`, `ollama --version`, the model manifest/digest,
`system_profiler`, Python version, and `ace --version` in
`evidence/token-bleed-mac-r2/run-manifest.json`. The working tree must be clean except for the new
evidence directory.

### 2. Configure the endpoint

```bash
export OPENAI_BASE_URL='http://localhost:11434/v1'
export OPENAI_API_KEY='<non-secret local placeholder>'
export OPENAI_MODEL='<exact model identifier pinned in the R2 contract>'
```

Use a model/runtime whose verified context budget accommodates the largest declared ungoverned
input **plus** its requested completion budget. For the existing 3000-object design, treat a
64k-or-larger verified usable context as the minimum planning target. The R2 preflight, not this
rule of thumb, decides whether the actual constructed prompts fit.

For local Ollama, advertised model capacity is not proof of the serving context. R2 sends
`options.num_ctx` on every call, makes a one-token non-benchmark configuration probe, and requires
Ollama's live `/api/ps` record to confirm the requested context before calibration begins.

### 3. Run the preflight and calibration gate

Run the R2 preflight command supplied by the merged implementation. It must write a JSON result
and exit nonzero if any compared route exceeds context budget or if endpoint/model provenance is
missing.

The current implementation uses this form. Substitute values only with values recorded from the
Mac runtime; do not guess the model digest or context window.

```bash
python3 token_bleed_benchmark.py --r2 \
  --tiers 300 1500 3000 --replicates 1 --seed 41 \
  --context-window-tokens '<verified-runtime-context-window>' \
  --ollama-num-ctx '<verified-runtime-context-window>' \
  --max-completion-tokens 3000 \
  --timeout 1800 \
  --endpoint-class local-openai-compatible \
  --model-digest '<ollama-model-digest>' \
  --runtime-version "$(ollama --version)" \
  --hardware '<Mac model and macOS version>' \
  --verify-ollama-context \
  --retain-responses \
  --preflight-only \
  --preflight-out evidence/token-bleed-mac-r2/calibration-preflight.json \
  --out evidence/token-bleed-mac-r2/calibration.json
```

The runner uses a deliberately conservative UTF-8-byte upper bound for its constructed-input
token count. This is a fit proof, not a provider usage value. If it refuses a tier, change the
endpoint/context budget or freeze smaller R2 tiers in a new contract - never bypass the guard.
The configuration probe is not a benchmark trial. After that command passes, remove `--preflight-only` and run the identical frozen command once
to collect the calibration artifact.

Then run exactly one calibration seed, `41`, across every declared split and route. Preserve the
complete calibration report. Continue only if all of the following are true:

- All declared routes complete without terminal failure.
- No compared row is truncated.
- Every row includes structured attempts and nonempty retained response/audit fields.
- Provider-reported model ID matches the R2 contract.
- The calibration does not change tiers, timeout, model, statistics, or acceptance thresholds.

If calibration fails, stop. Preserve it and open a remediation issue. Do not tune the contract from
the partial outcome.

### 4. Execute the frozen 20-seed contract

Use the exact R2 command emitted by preflight. It must be equivalent to this specification:

```text
tiers = the frozen development, validation, and holdout tiers
seeds = 42..61
replicates = 20
retain_responses = true
timeout = the prespecified endpoint timeout
context budget enforcement = enabled
structured attempt retention = enabled
route-preparation timing = enabled
```

The runner may retry transient requests under the prespecified retry policy, but it must retain all
attempts. A terminal failure remains in the final report and makes the paired ACE trial unsuccessful.
Never rerun one seed to replace an unfavorable or failed result. A full fresh rerun is permitted
only after a new versioned contract is created and the original failed bundle is retained.

### 5. Build ACE evidence and assess

Run the merged R2 adapter and ACE assessment against the exact frozen contract. The adapter must
emit:

- 60 paired ACE trials: 3 splits × 20 declared seeds.
- F1 and ECD improvement for every valid trial, plus retained route-preparation timing as
  diagnostic provenance.
- Failed trials for any incomplete route pair, context breach, truncation, or irreconcilable
  provenance record.
- Development statistical evidence with method metadata, p-value, ECD CI, analysis seed, and
  retained paired values or immutable references.

The only acceptable publishing gate is:

```text
ace assess experiments/token-bleed-mac-r2.yaml \
  evidence/token-bleed-mac-r2/ace-evidence.json \
  --output evidence/token-bleed-mac-r2/ace-assessment
```

Do not publish a governed-versus-ungoverned claim unless the resulting decision pack is
`ACCEPTED`. If it is `REJECTED` or `INCONCLUSIVE`, publish only the methods limitation if there is
a reason to publish at all.

### 6. Package the evidence

Before sharing results, produce `SHA256SUMS.txt` over these immutable files:

- frozen R2 contract and its SHA-256
- `run-manifest.json`
- calibration report
- full final `report.json` with raw responses and attempts
- complete runner log
- adapter source and its source revision
- `ace-evidence.json`
- ACE decision pack and Markdown assessment
- statistical-analysis output, including the paired values and resampling settings

Do not include API keys, local paths that reveal private data, or unrelated system files.

## Publication rule

An accepted R2 result supports only this form of statement:

> On the named Mac-local endpoint and exact model/runtime configuration, across the declared
> synthetic catalog sizes and retained seed set, the governed route met the prespecified evidence
> and acceptance rules relative to the ungoverned context-stuffing baseline.

It does not establish production ROI, a general property of all models, security efficacy,
classifier recall in production, or replication of another study. A second independently configured
model family may support a broader replication statement, but only as a separately retained R2
bundle assessed against its own frozen contract.
