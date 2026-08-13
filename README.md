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

> **Disclosure.** The study reproduced here was sponsored by Informatica, a Salesforce company.
> The author of this repository is employed by Salesforce. That is a reason to run this harness
> yourself rather than take its output on trust — which is the entire point of publishing it.
> Contradicting results are welcome; open an issue with your `report.json`.

## What's real vs. synthetic (read this first)

- **The data is synthetic.** It's generated with the open-source [Faker](https://faker.readthedocs.io/)
  library — a financial-services-style metadata catalog with Government-ID columns (`SSN`,
  `SUBJECT_SSN`, `ID_DOC_NUMBER`, …) planted among look-alike decoys (`TAX_ID`, `LICENSE_NO`,
  `DOC_TYPE`, …). The correct answer key is **frozen by random seed before any model sees the
  data** — no tuning, no leakage.
- **The model calls, token counts, and F1 scores are real.** Every run makes live API calls to
  the endpoint you configure and reads the real `usage` block. Your numbers will differ from the
  article's (different model, endpoint, route implementation) — that's expected and the point.
- **The governed route is not given the answer key.** See below. This is the design decision
  that determines whether the benchmark means anything.

## The task

> *"Show me all the assets needed to build a report that involves Government ID."*

Two routes answer it against the **same** synthetic catalog:

| Route | How it reaches the data |
|---|---|
| **Ungoverned** (context stuffing) | The entire raw column catalog is dumped into the prompt. |
| **Governed** (metadata layer) | A classifier ran once, up front. The model receives its **candidate** set — true Gov-ID columns **mixed with decoys the classifier flagged in error** — and must still discriminate. |

Both are scored with Precision / Recall / F1 against the frozen key.

### Why the governed route gets decoys

If the governed route were handed only the true positives, it would be transcribing an answer
key, not retrieving anything — it could not lose, and the benchmark would prove nothing. So
`--classifier-fp-rate` (default `1.0`) injects one flagged decoy per true positive. The
governed route can and does lose precision. Setting it to `0` restores the answer-key
behaviour and prints a warning; do not publish numbers produced that way.

## Quick start (≈ 5 minutes)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

export OPENAI_BASE_URL="https://api.openai.com/v1"   # or Azure OpenAI v1, or a gateway that proxies OpenAI-style calls
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-4o-mini"

python3 token_bleed_benchmark.py --tiers 300 1500 3000 --replicates 3 --out report.json
```

Any endpoint that accepts an OpenAI-style `POST {OPENAI_BASE_URL}/chat/completions` and returns
a `usage` block works — OpenAI, Azure OpenAI (v1 path), Gemini OpenAI-compat, or a gateway in
front of them. The script probes both `max_completion_tokens` and `max_tokens` so it works
across providers that disagree about the parameter name, retries 429/5xx with backoff, and
writes `--out` incrementally so a late rate-limit doesn't discard completed tiers.

### Flags that matter

| Flag | Default | Why |
|---|---|---|
| `--replicates N` | `1` | Runs each tier against **N different catalog seeds**. F1 over a few dozen true positives is noisy — at 300 objects there are ~5, so one miss moves F1 by ~0.15. Re-running a single frozen catalog only varies model output, not the data. Use ≥3 before quoting anything. |
| `--classifier-fp-rate R` | `1.0` | Decoys the governed classifier flags per true positive. Raise it to model a worse classifier. |
| `--tiers`, `--seed`, `--out` | `300 1500 3000`, `42`, none | — |

Results print mean and \[min–max\] across replicates; `report.json` carries both the per-run
rows and an `aggregate` block.

## How it works

1. `build_catalog(n, seed)` — generates the synthetic catalog (deduplicated) and freezes the
   answer key.
2. `route_ungoverned` — stuffs the full catalog into the prompt.
3. `route_governed` — passes the classifier's candidate set: true positives plus flagged
   decoys. Classification happening once at ingestion is the structural advantage a real
   governed catalog provides.
4. `score` — Precision / Recall / F1 vs. the frozen key. Answers are parsed as whole
   `TABLE.COLUMN` tokens, line by line, skipping lines that negate — otherwise a model that
   restates "do not include X.TAX_ID" gets scored as having answered `X.TAX_ID`.

## Interpreting your numbers honestly

- **Model non-determinism:** re-runs vary. Use `--replicates 3` or more; the *trend* (governed
  cheaper and more accurate as data scales) is the robust signal, not any single number.
- **Classifier recall is assumed perfect.** Every true Gov-ID column reaches the governed
  candidate set. Real classifiers miss things, and a miss is unrecoverable because the model
  never sees the raw catalog. This assumption is the one most favourable to the governed route
  — state it when you cite your numbers.
- **The governed token count is a marginal query cost, not total cost of ownership.** It
  excludes building and maintaining the catalog. The honest question for a buyer is the payback
  volume: at what query rate does classification amortise? This harness does not answer that.
- **This is a floor, not a ceiling:** a real governed catalog also handles freshness, lineage,
  and proprietary classifiers this toy harness doesn't model.
- **Two routes is not the whole space.** Context stuffing is a weak baseline. A competitive
  comparison would add embedding retrieval over the catalog, or a plain regex prefilter — if a
  ten-line heuristic captures most of the benefit, that is the more interesting result.
- **Cost:** multiply tokens by your provider's rate to get dollars. Small per-call gaps become
  large at production call volumes — that's the "token bleed."

## Credits

- Benchmark concept & original study: **McKnight Consulting Group** — *Stop the Token Bleed*
  (Dolezal & McKnight, 2026).
- Synthetic data: [Faker](https://faker.readthedocs.io/).

## License

MIT — see [LICENSE](LICENSE).
