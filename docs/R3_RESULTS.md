# Token-Bleed R3 result

## Executive readout

R3 separates two claims that R2.1 could not support as one statement. On this named local
configuration, governed routing was decisively cheaper and more accurate than sending the full
catalog as prompt context. It did **not** outperform the much cheaper lexical prefilter at the
large holdout, either with perfect synthetic classifier recall or under the prespecified
false-negative sensitivity conditions.

This is a completed synthetic endpoint-specific result. It is not a production ROI claim, a
customer-data result, or a replication of the sponsored McKnight Consulting Group study.

## Frozen protocol and evidence status

- **Contract:** [`experiments/token-bleed-mac-r3.yaml`](../experiments/token-bleed-mac-r3.yaml),
  SHA-256 `22d426ac1b0e0bced39e3af82d6ac6d7310a51a3581049874f59b01adc9e5354`.
- **Code revision:** `76ef98c11824da62337694ad71f0f08aebc0e63b`.
- **Endpoint:** local Ollama OpenAI-compatible endpoint, `qwen3-coder:30b`, model digest
  `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`.
- **Design:** 20 new seeds (62-81), three catalog sizes, three routes, and classifier
  false-negative conditions of 0%, 5%, and 10%.
- **Collection:** 540 of 540 retained rows succeeded. Live 131,072-token context and the
  `max_tokens` completion cap were verified before collection. No retained row reports context
  truncation or a completion-cap overrun.
- **Integrity:** the retained preflight and report SHA-256 values are recorded in
  [`evidence/token-bleed-mac-r3/SHA256SUMS.txt`](../evidence/token-bleed-mac-r3/SHA256SUMS.txt).
  The raw report is retained unchanged outside the public repository because its Mac-generated
  hardware field includes host identifiers. The public evidence set includes the preflight,
  ACE-ready derived evidence, and ACE decision pack.

## Decision

ACE's generic contract assessment returned **ACCEPTED**, with no evidence gaps and no failed
generic rule checks. The public decision pack was regenerated with ACE v0.1.2, which retains the
generic verdict and every contract-declared claim scope without collapsing them. That generic
assessment concerns governed routing against full-context stuffing. R3's preregistered
claim-scoped decisions must be read separately:

| Claim | Comparator and condition | Verdict |
|---|---|---:|
| Selective context reduces cost | Governed vs. full context, 0% false negatives | **ACCEPTED** |
| Governed preserves quality vs. full context | Governed vs. full context, 0% false negatives | **ACCEPTED** |
| Governance earns added complexity | Governed vs. lexical, 0% false negatives, holdout | **REJECTED** |
| Result survives routing misses | Governed vs. lexical, 5% and 10% false negatives, holdout | **REJECTED** |

## Results at the primary condition

The table below uses the prespecified 0% false-negative condition and mean F1 across 20 seeds.

| Catalog size | Governed F1 | Full-context F1 | Lexical F1 | Governed prompt-token reduction vs. full |
|---:|---:|---:|---:|---:|
| 300 | 0.780 | 0.261 | 0.660 | 94.2% |
| 1,500 | 0.632 | 0.253 | 0.737 | 96.0% |
| 3,000 holdout | 0.447 | 0.177 | 0.631 | 96.2% |

For the governed-versus-full comparison, the paired 95% F1-difference confidence interval was
`[0.254, 0.506]` at validation and `[0.138, 0.411]` at holdout. Both clear the preregistered
non-inferiority floor of -0.02.

For the governed-versus-lexical holdout comparison, the paired 95% F1-difference confidence
interval was `[-0.371, 0.00005]`, so it did not exclude zero in governance's favor. Governed
also used 2.11 times the lexical route's mean prompt tokens, above the frozen 1.10 maximum.

At 5% false negatives, the governed-minus-lexical F1 interval was `[-0.341, -0.083]` and the
prompt-token ratio was 2.06. At 10%, the interval was `[-0.389, 0.0069]` and the ratio was 2.00.
Both sensitivity conditions therefore reject the claim that governance adds value beyond lexical
filtering for this configuration.

## What this says about the McKnight mechanism

R3 supports the core mechanism: indiscriminately putting a large catalog into a prompt is an
expensive and lower-quality choice on this endpoint. Selective context, including governed
routing, can avoid that failure mode.

R3 does not support the broader assertion that a governed metadata route is necessarily the best
selective-context route. The lexical baseline won the R3 holdout on both F1 and prompt-token use.
The result therefore identifies the decision boundary: compare governance with cheap baselines,
not only with raw context stuffing.

## Reproducibility boundary

The retained public artifacts are:

- [`preflight.json`](../evidence/token-bleed-mac-r3/preflight.json)
- [`ace-evidence.json`](../evidence/token-bleed-mac-r3/ace-evidence.json)
- [`ace-decision-pack.json`](../evidence/token-bleed-mac-r3/ace-decision-pack.json)
- [`SHA256SUMS.txt`](../evidence/token-bleed-mac-r3/SHA256SUMS.txt)

They allow an independent reader to inspect the frozen contract hash, collection gates, derived
paired statistics, and decisions. The raw report's original SHA-256 is included in the manifest,
but the raw file itself is deliberately withheld pending a privacy-safe release artifact.
