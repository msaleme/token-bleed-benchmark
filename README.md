# Token-Bleed Benchmark

**Reproduce the "Stop the Token Bleed" finding yourself — on any model, in an afternoon.**

The route an AI agent takes to reach enterprise data — not just the model — drives both
**cost** and **accuracy**. This is a small, honest harness that measures it: same model, same
task, two ways of reaching the data (ungoverned "context stuffing" vs. a governed,
pre-classified metadata layer). It reports real token counts and a real F1 accuracy score for
each route, so you can see the gap on your own endpoint.

> **Background.** This reproduces the *structure* of McKnight Consulting Group's benchmark,
> **"Stop the Token Bleed: Benchmarking the Benefits of Governed Metadata for Enterprise AI"**
> (Jake Dolezal & William McKnight, August 2026; sponsored by Informatica, a Salesforce
> company). Their study held the model constant and found governed metadata access won on
> **both** cost (up to ~89× fewer tokens at scale) and accuracy (F1 1.000 vs 0.29–0.66
> ungoverned). Read the article for their full methodology and figures. **This repo does not
> reproduce their exact numbers** — it lets you generate *your own* on *your* model.

## What's real vs. synthetic (read this first)

- **The data is synthetic.** It's generated with the open-source [Faker](https://faker.readthedocs.io/)
  library — a financial-services-style metadata catalog with Government-ID columns (`SSN`,
  `SUBJECT_SSN`, `ID_DOC_NUMBER`, …) planted among look-alike decoys (`TAX_ID`, `LICENSE_NO`,
  `DOC_TYPE`, …). The correct answer key is **frozen by random seed before any model sees the
  data** — no tuning, no leakage.
- **The model calls, token counts, and F1 scores are real.** Every run makes live API calls to
  the endpoint you configure and reads the real `usage` block. Your numbers will differ from the
  article's (different model, endpoint, route implementation) — that's expected and the point.

## The task

> *"Show me all the assets needed to build a report that involves Government ID."*

Two routes answer it against the **same** synthetic catalog:

| Route | How it reaches the data |
|---|---|
| **Ungoverned** (context stuffing) | The entire raw column catalog is dumped into the prompt. |
| **Governed** (metadata layer) | Classification happened once, up front; only the pre-classified Government-ID columns are passed. |

Both are scored with Precision / Recall / F1 against the frozen key.

## Quick start (≈ 5 minutes)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install faker

export OPENAI_BASE_URL="https://api.openai.com/v1"   # or Azure OpenAI v1, or a gateway that proxies OpenAI-style calls
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"

python3 token_bleed_benchmark.py --tiers 300 1500 3000 --out report.json
```

Any endpoint that accepts an OpenAI-style `POST {OPENAI_BASE_URL}/chat/completions` and returns
a `usage` block works — OpenAI, Azure OpenAI (v1 path), Gemini OpenAI-compat, or a gateway in
front of them.

## Example output

Running against a `gemini-2.5-flash`-class model through a gateway (your numbers will vary):

```
Tier: 300 objects   (300 columns, 5 true Gov-ID)
  ungoverned (context-stuffing)    tokens=  5,540  F1=0.750
  governed (metadata layer)        tokens=    690  F1=0.889
  --> governed used 8.0x fewer tokens, F1 0.889 vs 0.750

Tier: 1500 objects  (1500 columns, 23 true Gov-ID)
  ungoverned (context-stuffing)    tokens= 22,897  F1=0.516
  governed (metadata layer)        tokens=  1,635  F1=0.878
  --> governed used 14.0x fewer tokens, F1 0.878 vs 0.516

Tier: 3000 objects  (3000 columns, 54 true Gov-ID)
  ungoverned (context-stuffing)    tokens= 43,911  F1=0.286
  governed (metadata layer)        tokens=  3,040  F1=0.898
  --> governed used 14.4x fewer tokens, F1 0.898 vs 0.286
```

The pattern to notice: as the catalog scales, the ungoverned route's accuracy **collapses**
(recall drops — it can't find the needles in a bigger haystack) *and* it burns far more tokens.
The governed route stays cheap and accurate. See `sample-report.json` for a full machine-readable
run.

## How it works

1. `build_catalog(n, seed)` — generates the synthetic catalog and freezes the answer key.
2. `route_ungoverned` — stuffs the full catalog into the prompt.
3. `route_governed` — passes only the pre-classified matches (the classification is the
   structural advantage a real governed catalog — e.g. Informatica CDGC surfaced via MCP —
   provides once at ingestion).
4. `score` — Precision / Recall / F1 vs. the frozen key.

## Interpreting your numbers honestly

- **Model non-determinism:** re-runs vary. Run each tier a few times; the *trend* (governed
  cheaper + more accurate as data scales) is the robust signal, not any single number.
- **This is a floor, not a ceiling:** a real governed catalog also handles freshness, lineage,
  and proprietary classifiers this toy harness doesn't model.
- **Cost:** multiply tokens by your provider's rate to get dollars. Small per-call gaps become
  large at production call volumes — that's the "token bleed."

## Credits

- Benchmark concept & original study: **McKnight Consulting Group** — *Stop the Token Bleed*
  (Dolezal & McKnight, 2026).
- Synthetic data: [Faker](https://faker.readthedocs.io/).

## License

MIT — see [LICENSE](LICENSE).
