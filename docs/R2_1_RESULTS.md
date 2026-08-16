# Token-Bleed R2.1 result

## Executive readout

Selective context was dramatically cheaper than sending the full catalog to the model. On this
named local configuration, however, the governed route did not establish a dependable accuracy
advantage at the largest test size. A simple lexical prefilter performed better there.

This is a useful result, not a failed experiment. It separates the cost-reduction mechanism from
the stronger claim that governed metadata is always the best quality-preserving route.

## What was tested

- **Task:** identify Government-ID fields in a synthetic metadata catalog.
- **Routes:** full-catalog context stuffing (ungoverned), name-only lexical prefilter, and a
  governed metadata candidate route.
- **Endpoint:** local Ollama OpenAI-compatible endpoint running `qwen3-coder:30b`.
- **Protocol:** 20 frozen seeds at catalog sizes 300, 1,500, and 3,000; all three routes ran for
  each seed.
- **Evidence controls:** retained trial evidence, verified no context truncation, verified
  `max_tokens` completion cap, and a checksum-verified bundle. The run contained 180 successful
  trial rows and one recovered retry.
- **Assessment:** ACE returned `REJECTED` under the frozen R2.1 contract. This was a substantive
  result, not an evidence-gap failure: the holdout governed F1 missed its prespecified floor.

The synthetic data, local endpoint, model digest, route implementation, and classifier assumptions
bound every result below. They do not establish a production outcome, a general model result, or a
replication of McKnight Consulting Group's sponsored study.

## Results

| Catalog size | Governed F1 | Full-context F1 | Lexical F1 | Governed prompt-token reduction vs. full context |
|---:|---:|---:|---:|---:|
| 300 | 0.758 | 0.268 | 0.686 | 16.9x fewer |
| 1,500 | 0.558 | 0.229 | 0.731 | 25.2x fewer |
| 3,000 holdout | 0.24065 | 0.23930 | 0.588 | 26.6x fewer |

At the 3,000-object holdout, governed routing was essentially tied with full-context stuffing
on F1. It fell below the frozen quality floor of 0.245533, so the contract correctly rejected the
overall comparative claim.

## What the result supports

1. **The token-saving mechanism held.** Sending a focused candidate set used far fewer prompt
   tokens than sending the complete catalog at every tested size.
2. **The governed route beat raw stuffing at smaller sizes.** This happened at 300 and 1,500
   objects in this configuration.
3. **The stronger accuracy claim did not transfer cleanly to the largest holdout.** Governed
   routing did not establish an accuracy advantage over full context at 3,000 objects.
4. **A cheap baseline matters.** The lexical prefilter beat governed routing at 1,500 and 3,000
   objects while also using fewer prompt tokens.

## What this says about the McKnight claim

The benchmark was designed to reproduce the structure of the McKnight study, not its data,
endpoint, or exact implementation. R2.1 therefore does not adjudicate whether that study is right
or wrong.

It does show a boundary condition for the broader mechanism:

> Reducing raw context can improve AI economics, but a governed metadata route must be compared
> with inexpensive filtering baselines before claiming it is the best route for answer quality.

## Decision and next test

Do not revise R2.1's frozen acceptance floor after seeing this result. The next experiment is R3,
specified before collection in [`R3_PROTOCOL.md`](R3_PROTOCOL.md). It evaluates separately:

- whether selective routing retains a cost advantage over raw context;
- whether governed routing adds value beyond a lexical prefilter; and
- whether any observed advantage survives nonzero classifier false negatives.

## Evidence boundary

R2.1 is a retained, checksum-verified, synthetic local-model observation. It is not a claim about
customer data, production savings, metadata-catalog total cost of ownership, security, freshness,
lineage, or any third-party product. The R2.1 result remains `REJECTED` under its original ACE
contract.
