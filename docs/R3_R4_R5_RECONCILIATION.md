# Token-Bleed R3, R4, and R5 commissioning reconciliation

Date: 2026-08-17

## Purpose and scope

This record answers the commissioning checklist against the exact retained artifacts and frozen
contracts. It separates original Mac evidence from derived ACE artifacts. It does not reproduce
any collection, change a contract, replace a source artifact, or expand a model-scoped result into
a cross-model claim.

All three rounds are scoped to the named local endpoint and retained model identity,
`qwen3-coder:30b`. They are synthetic benchmark characterizations, not reproductions of McKnight
figures, production governance validation, ROI proof, or a general statement that governance
always earns its complexity.

## Chain of custody

| Round | Preflight SHA-256 | Report SHA-256 | Result |
|---|---|---|---|
| R3 | `82269e0fdab01217c3b585f86f479eda3862267ffa32a51b1f74646ef926ddcd` | `68856a3338ad28bf16b0dd7ad242bab8af9a7bec3c4ebee2c57f7c893397c575` | matches the Mac manifest and independent recomputation |
| R4 | `513b5a8fde4b4b41ca1a6adcc5d8bf898a13cb6d50e79ad007d5e072379941d2` | `8efdcc4eba5a0884be8757f111d513c5eb6a9ed29613d6b0758b69b46a70dd4c` | matches the Mac manifest and independent recomputation |
| R5 | `66be0a103a994d99f2f505e605c626f5808caf63549fa55e7ceb30440a3266c1` | `051cafd6a2cc22cee700d33f049c221def334aa621e9c9f6431abcabf9daa18e` | matches the Mac manifest and independent recomputation |

The R3 raw archive SHA-256 is
`cd1504499457783d45d7470caa78abc0d979f2ea9c7e48034cf9bc17240140f4`.
The R5 raw archive SHA-256 is
`2b1049316ac2ee79125bbd189af8eb4f8c256ff90166190724825db16005b6b7`.
R4 was assessed directly from its retained ZIP without executing any archive member.

## Frozen contracts and ACE decision packs

| Round | Frozen source revision | Contract SHA-256 | Generic ACE verdict | Decision-pack SHA-256 |
|---|---|---|---|---|
| R3 | `76ef98c11824da62337694ad71f0f08aebc0e63b` | `22d426ac1b0e0bced39e3af82d6ac6d7310a51a3581049874f59b01adc9e5354` | `ACCEPTED` | `47e162ca5b134fe83cdb476912ca83ba336c29772d435fa359bd06c42bc9b050` |
| R4 | `49ec98128fd33f661262070ffc8da9126bed5732` | `3b4216d8c27b4dc9f0bd6fde16fc4714351d179297f06527c168f58da0f8d3e8` | `INCONCLUSIVE` | `642737eec102e59d255d122ea121e28ea29441c043ccebb3d2f6e845ecfe3673` |
| R5 | `1df3e5c9446086c52077656791825c968fa581e3` | `a110afbf9158cde7f83a9a373917435ade655a91922c94ae22f57e6435f33982` | `ACCEPTED` | `9bdb75a42f6eb637594d322b0e890e31f45137d958f621080e438e7b1f7abd9d` |

R3 and R5 decision packs are the retained/public ACE 0.1.2 artifacts. R4 had no retained
decision-pack file. Its pack was derived on 2026-08-17 from the immutable archived report and the
exact R4 contract using ACE 0.1.2. It is clearly labeled derived and does not alter the archive.

## Claim-scoped verdicts and failed rules

### R3

- `selective_context_cost_vs_full`: `ACCEPTED`.
- `governed_quality_vs_full`: `ACCEPTED`.
- `governed_value_vs_lexical`: `REJECTED`.
  - Failed quality rule at tier 3,000: paired F1 CI `[-0.37135875, 0.0000525]` did not have a
    lower bound above zero.
  - Failed cost rule: governed/lexical mean prompt-token ratio `2.1093927367x` exceeded the
    frozen `1.1x` ceiling.
- `governed_sensitivity_vs_lexical`: `REJECTED`.
  - At 5% misses, F1 CI `[-0.3412525, -0.08255]` failed and cost was `2.0568897472x` versus
    `1.1x`.
  - At 10% misses, F1 CI `[-0.3886525, 0.006905]` failed and cost was `2.0009456709x` versus
    `1.1x`.

There were no failed generic ACE gates and no evidence gaps in R3.

### R4

- `selective_context_cost_vs_full`: `INCONCLUSIVE`.
- `governed_quality_vs_full`: `INCONCLUSIVE`.
  - Each requires the tier-1,200 seed-95 ungoverned/full-context pair at 0% classifier misses.
    That row was retained as a terminal `ContextBudgetExceeded` preflight refusal. It was not
    silently dropped and it does not invalidate unrelated claims.
- `governed_value_vs_lexical`: `REJECTED`.
  - Quality passed: tier-1,200 paired F1 CI `[0.86254625, 0.93685125]`.
  - Cost failed: governed/lexical mean prompt-token ratio `9.8591954023x` exceeded the frozen
    `3x` ceiling.
- `governed_sensitivity_vs_lexical`: `REJECTED`.
  - At 5% misses, quality passed, but cost was `9.6178160920x` versus `3x`.
  - At 10% misses, quality passed, but cost was `9.3982758621x` versus `3x`.

The sole generic ACE failure is `holdout_trial_coverage`: 19 successful trials, with declared
seed 95 missing from the successful full-context holdout pair. This produces a generic
`INCONCLUSIVE` verdict and affects only full-context-dependent claims.

### R5

- `selective_context_cost_vs_full`: `ACCEPTED`.
  - Mean prompt-token reductions: 96.8773% at tier 300, 97.8118% at tier 800, and 97.9389% at
    tier 1,200, all above the frozen 50% requirement.
- `governed_quality_vs_full`: `ACCEPTED`.
  - Paired F1 CI lower bounds: 0.61564875 at tier 800 and 0.61579875 at tier 1,200, both above
    the allowed -0.02 boundary.
- `governed_value_vs_lexical`: `REJECTED`.
  - Quality passed: holdout paired F1 CI `[0.85834875, 0.92735125]`.
  - Cost failed: `6.9409090909x` governed/lexical mean prompt tokens exceeded the immutable
    `3x` ceiling.
- `governed_sensitivity_vs_lexical`: `REJECTED`.
  - At 5% misses, quality passed but cost was `6.7345454545x` versus `3x`.
  - At 10% misses, quality passed but cost was `6.6581818182x` versus `3x`.

There were no failed generic ACE gates and no evidence gaps in R5.

## R4 seed-95 scoring rule

The three R4 failures are retained preflight refusals for the same holdout seed, tier, and route
under 0%, 5%, and 10% classifier misses. The ungoverned route constructed 128,256 input tokens;
with its 3,000-token completion budget it exceeded the verified 131,072-token window. It made no
model call and recorded zero prompt/completion tokens.

At 0% misses, the missing full-context pair makes only the full-context cost and quality claims
`INCONCLUSIVE`. The lexical route and governed route both completed, so their 0% lexical claim is
complete and is `REJECTED` only on the 3x cost ceiling. At 5% and 10%, the sensitivity claims do
not use the ungoverned comparator, so they remain complete and are `REJECTED` only on their stated
cost rule. This is fail-closed pair handling, not silent row deletion or a whole-holdout failure.

## R5 contract-digest confirmation

Confirmed: R5's intended frozen contract is
`experiments/token-bleed-mac-r5.yaml` at revision
`1df3e5c9446086c52077656791825c968fa581e3`, SHA-256
`a110afbf9158cde7f83a9a373917435ade655a91922c94ae22f57e6435f33982`.
The retained report and the ACE R5 decision pack both carry that digest.

## Publication intent and hard boundary

| Round | Publication status | Permitted statement | Prohibited statement |
|---|---|---|---|
| R3 | Technical record released | In this named synthetic endpoint configuration, governed selection was cheaper and higher quality than raw full-context stuffing. | Governance beats lexical filtering, a general model claim, or a McKnight replication. |
| R4 | Preserve as a methodological boundary | Full-context comparability was incomplete at seed 95 because the frozen request exceeded the context window; lexical-value claims failed the predeclared cost rule. | Any favorable governed-versus-full conclusion or whole-holdout result. |
| R5 | Privacy-safe technical record released | In this named synthetic endpoint configuration, compact governed selection was 96.9%-97.9% lower prompt cost and higher quality than raw full-context stuffing, but did not clear the 3x lexical-cost ceiling. | Governance is universally economically superior, governance beats lexical filtering, or a McKnight replication. |

R2.1 remains visibly `REJECTED`; it is part of the methodological record and will not be buried.

## Second-model replication decision

**Decision: do not commission a second-model run yet.** R5 establishes a complete, useful
model-scoped boundary and the next value is converting it into a sector demonstration, not
collecting another bundle before a clearly defined cross-model claim exists. No cross-model or
general “governance earns its complexity” statement is authorized.

If that claim becomes strategically necessary, commission a new preregistered round on a genuinely
different model family after selecting an available model and hardware target. It must retain a new
contract SHA, exact model digest, fresh seeds, all three routes, all miss conditions, the unchanged
3x lexical ceiling, and its own ACE decision pack. Do not reuse R3-R5 evidence or choose a target
after seeing a favorable result.

## Complexity-overhead rule

`complexity_overhead` does **not** gate R3, R4, or R5 generic or claim-scoped verdicts. None of
their frozen contracts declares a maximum complexity-overhead acceptance rule, and none of the
decision packs includes it as a failed or passed gate. Do not retroactively use local route-
preparation microseconds to qualify these results.

For a future contract, if operational cost is material, replace that narrow microbenchmark with a
separately preregistered end-to-end measure: selector latency, retrieval/classifier cost, prompt
tokens, model latency, retries, and approval/human-review work. It must be measured under the same
load and endpoint conditions as the quality claim.

## Next actions

1. Keep R3 and R5 public packets immutable and raw Mac reports private.
2. Keep R4's derived decision pack private unless there is a specific methods publication need.
3. Use the R5 accepted-versus-rejected boundary in the planned Energy/Utilities context-plane
   demonstration and the held executive article.
4. Do not start R6 or a second-model collection without a separate approved frozen contract.
