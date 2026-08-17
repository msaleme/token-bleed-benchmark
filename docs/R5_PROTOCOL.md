# Token-Bleed R5 protocol: compact governance under a complete full-context comparator

**Status:** preregistered design. Do not collect until this contract is merged, its commit and
SHA-256 are supplied to the Mac operator, and the all-seed preflight passes.

## Why R5 exists

R4 retained an honest boundary. Its governed route improved selection quality against lexical
filtering, but used more than three times lexical prompt tokens. Its full-context comparator
also correctly refused one holdout seed because the declared completion budget could not fit.

R5 is a new experiment, not a repair of R4. It uses new seeds and preserves R4's 3x lexical
ceiling. It tests whether a compact, coded representation of the same glossary, lineage, and
access-policy evidence can earn the added complexity while leaving the answer key hidden.

## Frozen task and representation

Physical names remain opaque. The answer key remains approved Government-ID fields only;
restricted Government-ID fields are wrong answers. The lexical route sees physical names only.

The governed route receives classifier candidates in a fixed compact representation:
`TABLE.COLUMN|t=GID|l=IDV|p=A`, where `GID` means Government-ID term, `IDV` means
identity-vault lineage, and `A`/`R` mean approved/restricted. The ungoverned route receives
the full synthetic metadata catalog. The governed route never receives the answer key.

## Completeness safeguard

R5 fixes the R4 comparability failure prospectively. Before any model call, the runner builds
every route for every tier, seed, and false-negative condition and refuses collection if any
constructed input plus the fixed 1,024-token completion budget exceeds 131,072 tokens.

## Claims tested independently

The R4 claim rules are retained unchanged: at least 50% prompt-token reduction versus full
context on every split; governed-minus-full paired F1 lower bound of at least -0.02 on validation
and holdout; and, versus lexical on holdout, a strictly positive paired F1 lower bound plus no
more than 3x mean lexical prompt tokens. The last rule must also hold at 5% and 10% retrieval
miss conditions.

This remains a synthetic, named-endpoint runtime characterization. It does not prove a
production policy engine, data-governance control, or ROI.
