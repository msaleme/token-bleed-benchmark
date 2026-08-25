# Selective Context Under a Claim-Scoped Evidence Contract

## A synthetic runtime characterization of Token-Bleed R5

**Michael K. Saleme**  
ORCID: https://orcid.org/0009-0003-6736-1900

## Abstract

Agent systems often select a subset of available context before producing an answer or taking an action. This study distinguishes whether compact selection improves on raw full-context stuffing from whether it meets a prespecified prompt-token-efficiency rule against a cheap selective comparator. Token-Bleed R5 is a synthetic runtime characterization on a named local endpoint. It evaluates raw full-context stuffing, a compact governed metadata route, and a deliberately name-only lexical control across 20 seeds, catalog sizes of 300, 800, and 1,200 items, and injected classifier false-negative conditions of 0%, 5%, and 10%.

At the prespecified 0% false-negative condition, the bundled compact governed route used 96.9% to 97.9% fewer mean prompt tokens than the verbose full-catalog route and produced higher mean F1 at each catalog size. At the 1,200-item holdout, mean prompt tokens were 763.5 for the bundled route and 37,045.6 for verbose full context; the paired bundled-minus-full F1 95% bootstrap interval was [0.616, 0.749]. The separately prespecified bundled-versus-lexical claim was rejected: the bundled route used 6.94 times the lexical route's mean prompt tokens, above the frozen 3.0 ceiling, despite a favorable F1 interval.

The result supports a bounded finding about compact governed selection relative to raw full-context stuffing in this synthetic opaque-schema task. It does not establish an economic advantage, a production result, or superiority over general inexpensive selective-context baselines. The accompanying public files are an **auditable derived-evidence package**: they support inspection of the frozen contract, retained derived trial evidence, and decision rules, but not independent inspection or recalculation from the private raw report.

## 1. Scope and provenance

The study tests a synthetic identity-data selection task with access-policy constraints. Each generated catalog contains opaque physical column names, synthetic business-term, lineage, and access-policy metadata, plus a frozen answer key. A valid answer is a fully qualified column name representing an approved government-issued identity number. Restricted identity fields and non-identity decoys are invalid answers. F1 is the harmonic mean of precision and recall after parsing exact fully qualified names from the model response against that frozen key.

The protocol was **prespecified in a frozen, pre-collection experiment contract**. This document intentionally does not use “preregistered” in the sense of an externally registered study protocol. The source lineage is explicit: collection revision [`1df3e5c`](https://github.com/msaleme/token-bleed-benchmark/commit/1df3e5c9446086c52077656791825c968fa581e3) → privacy-safe result release [`25e24e0`](https://github.com/msaleme/token-bleed-benchmark/commit/25e24e0212b53bcb0f1497c80919c9223caaab26) → preprint candidate [`c207ef7`](https://github.com/msaleme/token-bleed-benchmark/commit/c207ef72bb6b5946343619653cffdf9f88b28d19). The middle commit is a descendant of collection and adds public result artifacts without changing the collection source.

## 2. Methods

### 2.1 Frozen configuration and design

Collection used a local Ollama OpenAI-compatible endpoint with `qwen3-coder:30b`, model digest `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`. The immutable [R5 contract](https://github.com/msaleme/token-bleed-benchmark/blob/1df3e5c9446086c52077656791825c968fa581e3/experiments/token-bleed-mac-r5.yaml) has SHA-256 `a110afbf9158cde7f83a9a373917435ade655a91922c94ae22f57e6435f33982`.

The design has 20 seeds (102 through 121), catalog sizes of 300, 800, and 1,200, three routes, and injected candidate-generator false-negative rates of 0%, 5%, and 10%. The contract designates the 1,200-item condition as holdout before collection; the public derived package does not independently establish a non-inspection history beyond that frozen contract. Those factors yield 540 prespecified route rows. Before the first model call, the runner constructed every row and rejected any row that could not fit the verified 131,072-token context window with a 1,024-token completion cap. All 540 prespecified rows completed and were analyzed. No retained row records input truncation, a completion-cap enforcement failure, or completion tokens above the requested cap. The actual enforced parameter was `max_tokens`; it is retained per row. The retained runtime record contains the requested model, context probe, timeout, and completion-cap probe, but not Ollama version, temperature, top-p, or model seed behavior. This result is not generalized to another endpoint, runtime version, or decoding configuration.

### 2.2 Task, routes, and injected misses

Catalog physical names deliberately carry no government-identity lexical cue. Each entry has synthetic business-term, lineage, and access-policy metadata. The answer key admits only approved government-identity fields. The three routes receive the same task instruction but different context:

| Route | Context supplied to the model | Purpose and limit |
| --- | --- | --- |
| Full context | Every catalog entry with readable synthetic term, lineage, and access metadata | Raw-context comparator, not a retrieval baseline. |
| Bundled compact governed route | Oracle-controlled candidate set rendered with compact `t` (term), `l` (lineage), and `p` (policy) codes | Changes both candidate membership and representation relative to full context; includes decoys, so the model must reject them. |
| Lexical control | Only names matching a government-ID regular expression | Deliberately cheap, name-only negative control with no semantic metadata, lineage, access policy, embeddings, or classifier. |

The candidate generator uses the frozen answer key to construct experimental candidate sets, then perturbs them with decoys and controlled misses. It is an oracle-controlled experimental mechanism, not an evaluated metadata-driven classifier. R5 therefore characterizes downstream model behavior under controlled candidate-set errors; it does not measure retrieval or classifier performance. The decoy-to-true-candidate load multiplier is fixed at 1.0, adding up to one decoy per true candidate. For the 5% and 10% sensitivity conditions, the runner randomly removes the corresponding rounded number of true candidates before the bundled route is constructed. Route order is independently randomized for each seed and false-negative condition.

### 2.3 Metrics, statistical unit, and decision rules

The statistical unit is the seed-matched route pair within a catalog size and false-negative condition. Mean F1 and mean prompt-token values are reported across 20 seeds. Prompt-token reduction is calculated per pair as `1 − governed_prompt_tokens / full_prompt_tokens`, then averaged. The lexical comparison uses the mean of the matched per-seed `governed_prompt_tokens / lexical_prompt_tokens` ratios.

For paired F1 differences, the analysis uses a deterministic paired percentile bootstrap: 10,000 resamples, 95% interval, random seed `20260815`, and mean paired difference as the statistic. Prompt-token values are endpoint usage telemetry, not monetary cost, latency, energy, or end-to-end operating economics.

| Claim | Comparator and condition | Frozen decision rule |
| --- | --- | --- |
| Bundled compact route reduces prompt-token use | Bundled route versus verbose full catalog, 0% misses | Mean paired reduction at least 0.50 on development, validation, and holdout |
| Bundled compact route preserves quality | Bundled route versus verbose full catalog, 0% misses | Paired F1 interval lower bound at least -0.02 on validation and holdout |
| Bundled compact route meets the token-efficiency rule | Bundled route versus lexical, 0% misses, holdout | Paired bundled-minus-lexical F1 interval lower bound > 0 and mean paired token ratio no greater than 3.0 |
| Bundled compact route meets the rule under routing misses | Bundled route versus lexical, 5% and 10% misses, holdout | Same F1 and token-ratio rules |

## 3. Results

The primary condition is 0% injected false negatives. All values below are means over 20 seeds. The lexical route's F1 is zero at every size because the opaque physical names are intentionally incompatible with its name-only rule. It is a negative control, not a strong semantic retrieval comparator.

| Catalog size | Governed prompt tokens | Full-context prompt tokens | Lexical prompt tokens | Governed F1 | Full-context F1 | Lexical F1 | Governed reduction versus full |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 300 | 281.9 | 9,026.9 | 110.0 | 0.910 | 0.466 | 0.000 | 96.9% |
| 800 | 535.4 | 24,473.1 | 110.0 | 0.896 | 0.205 | 0.000 | 97.8% |
| 1,200 holdout | 763.5 | 37,045.6 | 110.0 | 0.893 | 0.212 | 0.000 | 97.9% |

For governed versus full context, the paired F1-difference 95% interval was [0.616, 0.766] at validation and [0.616, 0.749] at holdout. Both clear the frozen -0.02 quality boundary. The full-context F1 decrease at larger catalog sizes is an observed result, not a diagnosed mechanism: the privacy-safe derived package does not retain response-error labels sufficient to attribute it to attention dilution, formatting, position, or false-positive behavior.

At the 1,200-item holdout, the bundled-minus-lexical F1 interval was [0.858, 0.927], but the bundled-to-lexical mean prompt-token ratio was 6.94, above the frozen maximum of 3.0. At 5% misses, bundled-route mean F1 was 0.801 and the paired bundled-minus-lexical interval was [0.710, 0.874]; at 10% misses, mean F1 was 0.868 and the interval was [0.842, 0.892]. Prompt-token ratios were 6.73 and 6.66, respectively. The token-efficiency and routing-sensitivity claims are therefore rejected. A quality advantage does not override the prespecified token-efficiency rule.

## 4. Interpretation and limitations

R5 supports a narrow route-level finding: on this named local endpoint and synthetic opaque-schema task, the bundled compact governed route used fewer prompt tokens and achieved higher F1 than the verbose full-catalog route. Because membership and representation change together, it cannot attribute that difference to selection alone. Full catalog with compact encoding and selected candidates with readable metadata are necessary future controls to isolate those effects. The result does not show monetary savings, business value, production-policy performance, customer-data behavior, cross-model behavior, or a general advantage over inexpensive selective-context baselines. Embedding retrieval, BM25 over descriptions, compact semantic search without governance metadata, and budget-matched random selection are future comparators, not R5 results.

The public package is an auditable derived-evidence package. It includes a frozen contract, complete all-row preflight, seed-level derived evidence, paired statistics, and claim-scoped decisions. The original raw report remains private because it includes host-identifying provenance. Its digest permits future identity comparison but cannot establish raw-report completeness or permit independent recomputation from raw outputs. No claim of independent replication or full independent reproducibility is made.

## 5. Related work

R5 is a narrow synthetic experiment, not a replication or substitute for long-context, retrieval-augmented generation, or schema-linking research. Prior work documents that long-context models can show position-sensitive degradation in retrieval-style tasks, motivates explicit retrieval over non-parametric memory, and treats schema linking as a distinct technical problem. Those literatures motivate the task structure but do not validate this endpoint-specific result. See Liu et al., *Lost in the Middle* (2023), Lewis et al., *Retrieval-Augmented Generation* (2020), and Lei et al., *Re-examining the Role of Schema Linking in Text-to-SQL* (2020).

## 6. Public artifacts

- [Frozen R5 contract](https://github.com/msaleme/token-bleed-benchmark/blob/1df3e5c9446086c52077656791825c968fa581e3/experiments/token-bleed-mac-r5.yaml)
- [Privacy-safe R5 results](https://github.com/msaleme/token-bleed-benchmark/blob/25e24e0212b53bcb0f1497c80919c9223caaab26/docs/R5_RESULTS.md)
- [R3-R5 commissioning reconciliation](https://github.com/msaleme/token-bleed-benchmark/blob/c207ef72bb6b5946343619653cffdf9f88b28d19/docs/R3_R4_R5_RECONCILIATION.md)
- [Public evidence verifier](https://github.com/msaleme/token-bleed-benchmark/blob/c207ef72bb6b5946343619653cffdf9f88b28d19/scripts/verify_r5_public_evidence.py)
- [ACE reference-application boundary](https://github.com/msaleme/ace-experiment-framework/blob/a2dc79d48987cb2bcd6e946bb04afe746b77fd61/docs/REFERENCE_APPLICATION_TOKEN_BLEED_R5.md)
