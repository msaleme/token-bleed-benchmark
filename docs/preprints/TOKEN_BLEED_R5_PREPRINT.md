# Selective Context Under a Claim-Scoped Evidence Contract

## A synthetic runtime characterization of Token-Bleed R5

**Michael K. Saleme**  
ORCID: https://orcid.org/0009-0003-6736-1900

**Status:** Preprint candidate. Draft for authorial, packaging, and deposit review. This document is not yet a Zenodo deposit or DOI record.

## Abstract

Agent systems often choose among candidate context items before an action or answer is generated. That choice can be evaluated against a raw full-context baseline and against a cheap selective baseline, but the comparisons answer different questions. This paper reports Token-Bleed R5, a synthetic, named-endpoint runtime characterization that holds those claim scopes apart. Across 20 seeds, catalog sizes of 300, 800, and 1,200, and three routing conditions, compact governed selection used 96.9% to 97.9% fewer prompt tokens and achieved higher mean F1 than raw full-context stuffing at the prespecified zero-false-negative condition. At the 1,200-item holdout, governed selection used 763.5 mean prompt tokens, compared with 37,045.6 for full context. The paired governed-minus-full F1 confidence interval was [0.616, 0.749] at holdout. The same evidence did not satisfy the separately preregistered value claim against a lexical prefilter: governed selection used 6.94 times as many prompt tokens as lexical, above the frozen 3.0 ceiling, despite higher F1. The contribution is therefore a bounded evidence record, not a claim that governance is universally economically superior. The study is synthetic, endpoint-specific, and not a production policy-engine or customer-data result.

## 1. Introduction

Context selection is often framed as a binary choice between supplying all available material and supplying less. That framing obscures the different risks of a raw full-context route, a compact governed route, and a cheap lexical route. A raw full-context route can increase prompt cost and introduce irrelevant material. A lexical route can be inexpensive yet fail when the relevant physical names are deliberately opaque. A governed route can represent compact coded term, lineage, and access information, but must demonstrate both quality and cost boundaries.

Token-Bleed R5 treats these as distinct, preregistered claim scopes. The first asks whether compact governed selection reduces prompt cost relative to raw full-context stuffing while preserving answer quality. The second asks whether that governed route earns its higher cost relative to a lexical prefilter. Those claims must not be collapsed into a single headline.

## 2. Methods

### 2.1 Frozen configuration

The experiment used a local Ollama OpenAI-compatible endpoint with model qwen3-coder:30b, model digest 06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca. The source code revision was 1df3e5c9446086c52077656791825c968fa581e3. The experiment contract is experiments/token-bleed-mac-r5.yaml with SHA-256 a110afbf9158cde7f83a9a373917435ade655a91922c94ae22f57e6435f33982.

The design used 20 fresh seeds, numbered 102 through 121; catalog sizes of 300, 800, and 1,200; three routes; and classifier false-negative conditions of 0%, 5%, and 10%. Every planned row was constructed before collection with a fixed 1,024-token completion cap. All 540 retained rows passed context preflight and completed without reported truncation or completion-cap overrun.

### 2.2 Routes and measurements

The routes were raw full-context stuffing, compact governed metadata selection, and a lexical prefilter. Quality was measured as F1. Prompt-token counts were measured telemetry. The primary condition was zero classifier false negatives. Development, validation, and holdout catalogs were 300, 800, and 1,200 items respectively.

### 2.3 Claim scopes

| Claim | Comparator and condition | Frozen decision rule |
|---|---|---|
| Selective context reduces cost | Governed versus full, 0% false negatives | Mean prompt-token reduction of at least 0.5 across required splits |
| Governed preserves quality versus full | Governed versus full, 0% false negatives | Paired F1 confidence-interval lower bound at least -0.02 on validation and holdout |
| Governance earns its cost versus lexical | Governed versus lexical, 0% false negatives, holdout | F1 confidence interval favors governed and mean prompt-token ratio no greater than 3.0 |
| Result earns its cost under routing misses | Governed versus lexical, 5% and 10% false negatives, holdout | Same quality and token rules as the lexical value claim |

The assessor may return a generic governed-versus-full result, but that result does not override independently declared claim scopes.

## 3. Results

At the primary condition, compact governed selection reduced prompt tokens by 96.9% to 97.9% relative to raw full-context stuffing and achieved higher F1 at all three catalog sizes.

| Catalog size | Governed F1 | Full-context F1 | Lexical F1 | Governed prompt-token reduction versus full |
|---:|---:|---:|---:|---:|
| 300 | 0.910 | 0.466 | 0.000 | 96.9% |
| 800 | 0.896 | 0.205 | 0.000 | 97.8% |
| 1,200 holdout | 0.893 | 0.212 | 0.000 | 97.9% |

For governed versus full context, the paired 95% F1-difference confidence interval was [0.616, 0.766] at validation and [0.616, 0.749] at holdout. Both clear the preregistered non-inferiority floor of -0.02.

At holdout, governed selection used 763.5 mean prompt tokens, full context used 37,045.6, and lexical used 110.0. The governed-minus-lexical paired 95% F1 interval was [0.858, 0.927]. The governed-to-lexical mean prompt-token ratio was 6.94, exceeding the frozen maximum of 3.0. Under 5% and 10% false-negative conditions, F1 continued to favor governed selection, while token ratios were 6.73 and 6.66. The governed-versus-lexical value claim and the routing-sensitivity claim were therefore rejected.

## 4. Discussion

The evidence supports a narrow architectural result. When physical names are opaque and semantic selection is necessary, compact governed metadata can sharply reduce the cost and improve the answer quality of a raw full-context strategy on this endpoint.

The evidence does not establish that governed metadata is cost-effective against every cheap selective-context baseline. The lexical route had zero F1 in this synthetic opaque-schema task, but the frozen token ceiling still controls the value verdict. That negative result is part of the contribution. It prevents a quality advantage from being promoted into a universal economic claim.

## 5. Limitations

This is a completed synthetic runtime characterization on one named local endpoint. It is not a production policy-engine test, a customer-data result, an ROI claim, a cross-model result, or a replication of another study. The raw report is intentionally not public because its hardware provenance contains host identifiers. The public evidence packet retains the original raw-report SHA-256 and privacy-safe derived evidence, but it does not permit independent inspection of the raw report itself.

## 6. Reproducibility and evidence boundary

The public release includes the frozen contract, all-seed preflight, paired statistics, a generic ACE decision, independent claim-scope decisions, and SHA-256 manifests. The privacy-safe artifacts are:

- evidence/token-bleed-mac-r5/preflight.json
- evidence/token-bleed-mac-r5/ace-evidence.json
- evidence/token-bleed-mac-r5/ace-decision-pack.json
- evidence/token-bleed-mac-r5/SHA256SUMS.txt

The raw report's original SHA-256 is retained in the public manifest, while the raw file remains private for the limitation stated above.

## 7. Pre-deposit checklist

Before a DOI is minted, the deposit must include a rendered and reviewed PDF, the final metadata record, a citation file, the public artifact manifest with fresh hashes, the explicit private-raw-data boundary, an appropriate license, and a final consistency review against the source release. No claim wording may extend beyond the accepted claim scopes.

## References and primary artifacts

- Token-Bleed R5 result: docs/R5_RESULTS.md in the accompanying source release.
- R3, R4, R5 reconciliation: docs/R3_R4_R5_RECONCILIATION.md in the accompanying source release.
- Frozen R5 contract: experiments/token-bleed-mac-r5.yaml in the accompanying source release.
- Public research map: https://pubpoint.com/research-map/
- ACE reference application boundary: https://github.com/msaleme/ace-experiment-framework/blob/main/docs/REFERENCE_APPLICATION_TOKEN_BLEED_R5.md
