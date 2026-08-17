# Token-Bleed R4 protocol: when governed context earns its complexity

**Status:** preregistered design. No R4 trial may be collected until this exact contract is
merged, ACE-preflighted, and its SHA-256 is supplied to the collection operator.

## Why R4 exists

R3 answered two different questions. Selective context was much cheaper and more accurate than
raw context stuffing in the named configuration. But a cheap name-only filter beat the governed
route on the large R3 holdout. That was not a reason to change R3's rules. It was evidence that
the original synthetic task structurally favoured a lexical filter.

R4 tests the boundary directly. It does **not** retry R3, change R3's thresholds, or use its
seeds.

## Frozen task

The synthetic catalog uses opaque physical names such as `PERSON_REF` and `SUBJECT_KEY`; none
contains a Government-ID lexical cue. Each entry carries compact synthetic metadata:

- business glossary term
- source lineage
- access-policy state (`approved` or `restricted`)

The task asks for approved Government-ID fields for an identity-verification report. Restricted
Government-ID fields are intentionally present and are wrong answers. The frozen answer key is
created before model calls. The governed route receives classifier candidates with metadata and
false-positive decoys. It is not given the answer key. The lexical route sees physical names only.

This is still a synthetic, endpoint-specific runtime characterization. It does not prove a
production policy engine, data-governance control, or ROI.

## Claims tested independently

| Claim | Rule |
|---|---|
| Selective context lowers raw-context cost | Governed uses at least 50% fewer mean prompt tokens than full context on every split. |
| Governed quality holds against full context | Paired F1 CI lower bound is at least -0.02 on validation and holdout. |
| Governance earns added complexity | On holdout, governed-minus-lexical F1 paired-CI lower bound is greater than zero, while governed mean prompt tokens are no more than 3x lexical. |
| The benefit survives retrieval misses | The governed-versus-lexical rule holds at 5% and 10% classifier false-negative conditions. |

The 3x lexical token ceiling is intentional. R4 tests whether richer governed evidence buys a
quality advantage in a non-lexical task, not whether a zero-candidate lexical route can be
cheaper. Full context remains the cost baseline.

## Frozen collection design

- Tiers: 300 development, 800 validation, 1,200 holdout objects.
- Seeds: 82-101, all new.
- Routes: ungoverned full metadata context, lexical physical-name prefilter, governed metadata
  candidates.
- Conditions: 0%, 5%, and 10% classifier false negatives; fixed false-positive rate of 1.0
  decoy per eligible target.
- Rows: 3 tiers × 20 seeds × 3 routes × 3 conditions = **540 retained rows**.
- Runtime: named endpoint/model digest, 131,072 live context, one parallel slot, 1,800-second
  call timeout, and enforced `max_tokens` completion cap.

Missing pairs, model/provenance mismatch, truncation, an unenforced cap, or a changed scenario
makes the affected claim `INCONCLUSIVE`. Claims are reported separately even if generic ACE
accepts or rejects the experiment as a whole.
