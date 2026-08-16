# Token-Bleed R3 protocol

**Status:** preregistration draft. No R3 trial has been run under this protocol.

## Decision the experiment is meant to answer

When a model must select relevant metadata from a large catalog, does a governed metadata route
provide value beyond a cheap lexical prefilter, while still reducing the cost of raw context
stuffing?

R3 is not designed to rescue R2.1. It starts with new seeds, frozen rules, and explicit ways for
each part of the broader claim to succeed or fail.

## Claims tested separately

| Claim | Comparator | What counts as support |
|---|---|---|
| Selective routing reduces query context | Governed vs. full context | Governed uses at least 50% fewer mean prompt tokens on each split, with no context truncation. |
| Governed routing preserves quality against raw context | Governed vs. full context | The lower bound of the paired 95% bootstrap CI for F1 difference is at least -0.02 on validation and holdout. |
| Governance earns its added complexity | Governed vs. lexical | Governed's paired 95% bootstrap CI for F1 difference excludes zero in its favor on the holdout, while its mean prompt tokens are no more than 10% above lexical. |
| The result survives routing misses | Governed vs. lexical under sensitivity | The preceding quality result holds at both 5% and 10% classifier false-negative settings. |

The first two claims can succeed even if the third fails. If lexical wins, R3 must report that the
simple route is the preferred result for this configuration.

## Frozen design

- **Endpoint scope:** one named endpoint and exact model digest per completed run. Results may not
  be generalized across models, providers, or deployments.
- **Task and data:** the existing synthetic Government-ID metadata-selection task, with the task
  text, generator revision, scorer, and route implementations pinned by commit hash.
- **Routes:** ungoverned full context, lexical prefilter, governed metadata candidates.
- **Splits:** 300 objects (development), 1,500 (validation), and 3,000 (holdout).
- **Seeds:** 62 through 81. These are new seeds and must not be replaced selectively.
- **Route order:** randomized independently for each seed and retained in the trial record.
- **Classifier conditions:** false-negative rates of 0%, 5%, and 10%; false-positive rate fixed
  before collection and reported for every run.
- **Runtime controls:** preflight the live context window and completion-cap enforcement; retain
  the returned model identifier, model digest, timeout, token parameter, prompt/response hashes,
  attempts, truncation flag, and scorer audit for every row.

## Analysis plan

1. Analyze each split separately. Do not pool a 300-object result into the holdout threshold.
2. For every seed and route pair, calculate F1 difference and prompt-token ratio.
3. Use a two-sided paired exact permutation test for F1 differences and a paired bootstrap 95%
   confidence interval. Retain the method, seed, statistic, p-value, and interval in the evidence.
4. Use the 3,000-object holdout as the primary decision split. Development is diagnostic; validation
   tests transfer; neither can override a holdout failure.
5. Report all completed and failed attempts. A missing row, unverified cap, context truncation,
   model mismatch, or missing statistical artifact makes the affected claim inconclusive.

## Publication rules

- Preflight the final contract with ACE before collection and publish its digest alongside the
  results.
- Assess the retained evidence against that unchanged contract after collection.
- Publish the result as `ACCEPTED`, `REJECTED`, or `INCONCLUSIVE` exactly as assessed.
- Do not alter a threshold, replace a seed, or rerun only unfavorable rows after results are known.
- Use claim-scoped language: a supported token claim does not imply a supported quality claim, and
  a synthetic endpoint-specific result does not imply production ROI.

## Expected outputs

- Versioned ACE contract and preflight decision pack.
- Raw retained trial report plus SHA-256 manifest.
- Per-split tables for F1, prompt tokens, latency, failures, and classifier sensitivity.
- Paired statistical evidence for governed-versus-full-context and governed-versus-lexical tests.
- An ACE decision pack and a plain-language executive summary that states which claims held and
  which did not.
