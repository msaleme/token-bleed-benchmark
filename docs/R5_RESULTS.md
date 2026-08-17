# Token-Bleed R5 result

## Executive readout

R5 completes the raw full-context comparison that R4 intentionally left incomplete when one
holdout full-context request could not fit its declared completion budget. On the frozen local
configuration, compact governed selection was both materially lower-token and higher-F1 than
raw full-context stuffing. It did not meet the separately preregistered cost ceiling versus the
lexical prefilter.

This is a completed synthetic, named-endpoint runtime characterization. It is not a production
policy-engine test, a customer-data result, or an ROI claim.

## Frozen protocol and evidence status

- **Contract:** [`experiments/token-bleed-mac-r5.yaml`](../experiments/token-bleed-mac-r5.yaml),
  SHA-256 `a110afbf9158cde7f83a9a373917435ade655a91922c94ae22f57e6435f33982`.
- **Code revision:** `1df3e5c9446086c52077656791825c968fa581e3`.
- **Endpoint:** local Ollama OpenAI-compatible endpoint, `qwen3-coder:30b`, model digest
  `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`.
- **Design:** 20 fresh seeds (102-121), catalog sizes 300, 800, and 1,200, three routes, and
  classifier false-negative conditions of 0%, 5%, and 10%.
- **Completeness control:** before collection, the runner constructed every planned row using a
  fixed 1,024-token completion cap. All 540 rows passed context preflight; all 540 retained rows
  succeeded, with no reported truncation or completion-cap overrun.
- **Integrity:** the supplied Mac manifest digests matched the retained `preflight.json` and raw
  `report.json`. The original report remains private because its hardware provenance includes host
  identifiers. The public manifest retains its original SHA-256 and includes privacy-safe derived
  evidence and decisions.

## Decision

ACE v0.1.2's generic governed-versus-full contract assessment returned **ACCEPTED**, with no
evidence gaps or failed generic gates. The generic result does not collapse the independently
preregistered claim scopes:

| Claim | Comparator and condition | Verdict |
|---|---|---:|
| Selective context reduces cost | Governed vs. full context, 0% false negatives | **ACCEPTED** |
| Governed preserves quality vs. full context | Governed vs. full context, 0% false negatives | **ACCEPTED** |
| Governance earns its cost vs. lexical | Governed vs. lexical, 0% false negatives, holdout | **REJECTED** |
| Result earns its cost under routing misses | Governed vs. lexical, 5% and 10% false negatives, holdout | **REJECTED** |

## Results at the primary condition

The table uses the prespecified 0% false-negative condition and mean F1 across 20 seeds.

| Catalog size | Governed F1 | Full-context F1 | Lexical F1 | Governed prompt-token reduction vs. full |
|---:|---:|---:|---:|---:|
| 300 | 0.910 | 0.466 | 0.000 | 96.9% |
| 800 | 0.896 | 0.205 | 0.000 | 97.8% |
| 1,200 holdout | 0.893 | 0.212 | 0.000 | 97.9% |

For governed versus full context, the paired 95% F1-difference confidence interval was
`[0.616, 0.766]` at validation and `[0.616, 0.749]` at holdout. Both clear the preregistered
non-inferiority floor of -0.02.

At holdout, governed used 763.5 mean prompt tokens versus 37,045.6 for full context and 110.0
for lexical. Its governed-minus-lexical paired 95% F1 interval was `[0.858, 0.927]`, but its
mean prompt-token ratio was 6.94, above the frozen maximum of 3.0. At 5% and 10% false-negative
conditions, F1 continued to favor governed, but the prompt-token ratios were 6.73 and 6.66.
The governed-versus-lexical value and sensitivity claims therefore remain rejected.

## What this says, and does not say

R5 supports a bounded architecture claim: when opaque physical names make semantic selection
necessary, compact governed metadata can sharply reduce the cost and improve the answer quality
of a raw full-context strategy on this endpoint.

R5 does not support a broader claim that governed metadata is cost-effective against every
cheap selective-context baseline. In this synthetic opaque-schema task, the lexical route had
zero F1, so governance's quality advantage is clear, but the frozen 3x token ceiling still
controls the value verdict. Changing that ceiling after collection or selectively rerunning the
comparison would not be valid.

## Reproducibility boundary

The retained public artifacts are:

- [`preflight.json`](../evidence/token-bleed-mac-r5/preflight.json)
- [`ace-evidence.json`](../evidence/token-bleed-mac-r5/ace-evidence.json)
- [`ace-decision-pack.json`](../evidence/token-bleed-mac-r5/ace-decision-pack.json)
- [`SHA256SUMS.txt`](../evidence/token-bleed-mac-r5/SHA256SUMS.txt)

They allow inspection of the frozen contract hash, all-seed preflight, paired statistics, generic
ACE verdict, and independent claim-scope decisions. The raw report's original SHA-256 is retained
in the manifest, but the raw file is intentionally not published because it embeds host identifiers.
