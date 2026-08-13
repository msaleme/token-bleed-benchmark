#!/usr/bin/env python3
"""
token_bleed_benchmark.py — reproduce the "Stop the Token Bleed" benchmark yourself.

Inspired by McKnight Consulting Group's study "Stop the Token Bleed: Benchmarking the
Benefits of Governed Metadata for Enterprise AI" (Jake Dolezal & William McKnight,
August 2026, sponsored by Informatica, a Salesforce company). That study held the model
constant and compared how an AI agent REACHES enterprise data:

  * ungoverned "context stuffing" — dump the raw schema into the prompt
  * governed metadata layer       — pre-classified catalog returns only candidates

Their finding: governed access won on BOTH cost (up to ~89x fewer tokens at scale) and
accuracy (F1 1.000 vs 0.29-0.66 ungoverned). See the article for their full methodology.

THIS SCRIPT lets you reproduce that structure against ANY OpenAI-compatible endpoint and
generate YOUR OWN numbers, so you don't have to take anyone's word for it.

What's real vs. synthetic
--------------------------
  * The DATA is synthetic — generated with the open-source Faker library, modeled on a
    financial-services catalog, with Government-ID columns planted among decoys. This is
    disclosed and matches the article's approach. The answer key is FROZEN by seed before
    any model sees the data — no tuning, no leakage.
  * The MODEL CALLS, TOKEN COUNTS, and F1 SCORES are REAL. Your numbers will differ from
    the article's (different model, endpoint, and route implementation) — that is the
    point. Cite the article for their figures; cite your run for yours.

The governed route is NOT given the answer key
----------------------------------------------
  A governed catalog in the real world returns CANDIDATES from a classifier, and the
  classifier is imperfect. So `route_governed` passes the true Government-ID columns
  MIXED WITH decoy columns the classifier flagged by mistake (`--classifier-fp-rate`,
  default 1.0 = one false positive per true positive). The model still has to
  discriminate; it can and does lose precision here. If the governed route were handed
  only the true positives it would be transcribing an answer key, not retrieving.

  Stated assumption: classifier RECALL is modeled as perfect (every true Gov-ID column
  reaches the candidate set). That makes this a floor on the governed route's difficulty,
  and it is the assumption most favorable to the governed route. Say so when you cite it.

Quick start
-----------
  python3 -m venv .venv && . .venv/bin/activate
  pip install -r requirements.txt
  export OPENAI_BASE_URL="https://api.openai.com/v1"   # or your gateway / Azure / Gemini-compat endpoint
  export OPENAI_API_KEY="sk-..."
  export OPENAI_MODEL="gpt-4o-mini"
  python3 token_bleed_benchmark.py --tiers 300 1500 3000 --replicates 3 --out report.json

The endpoint must accept an OpenAI-style POST {base_url}/chat/completions and return a
`usage` block. Works with OpenAI, Azure OpenAI (v1 path), and gateways that proxy them.
"""
import argparse, json, os, re, sys, time, urllib.request, urllib.error, random

GOV_ID_COLUMNS = ["SSN", "SUBJECT_SSN", "ID_DOC_NUMBER", "NATIONAL_ID", "PASSPORT_NO", "SSN_LAST4"]
DECOY_COLUMNS  = ["TAX_ID", "LICENSE_NO", "DOC_TYPE", "ACCOUNT_NO", "ROUTING_NO", "CUSTOMER_REF"]

TASK = ("Show me all the assets (fully-qualified COLUMN names in TABLE.COLUMN form) needed to "
        "build a report that involves Government ID. Return ONLY the exact column names, one per line. "
        "A Government ID is a national identity number (e.g. Social Security Number). "
        "Do NOT include tax IDs, driver license numbers, account numbers, or generic document-type fields.")

# A line that negates is not an answer. Models routinely restate the exclusion list.
NEGATION = re.compile(
    r"\b(?:not|no|non|exclude[sd]?|excluding|exclusion|omit(?:ted|ting)?|ignore[sd]?|"
    r"ignoring|skip(?:ped|ping)?|avoid(?:ed|ing)?|reject(?:ed|ing)?|shouldn'?t|don'?t|"
    r"doesn'?t|isn'?t|aren'?t|without)\b", re.IGNORECASE)
FQNAME = re.compile(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+")

C = dict(OK="\033[32m", BAD="\033[31m", WARN="\033[33m", DIM="\033[2m", HD="\033[1;36m", B="\033[1m", R="\033[0m")
if not sys.stdout.isatty():
    C = {k: "" for k in C}

# Which max-token parameter this endpoint accepts. Probed once, then cached.
_TOKEN_PARAM = None


def die(msg, code=2):
    print(f"{C['BAD']}ERROR:{C['R']} {msg}", file=sys.stderr); sys.exit(code)


def build_catalog(n_objects, seed):
    """Synthetic financial-services metadata catalog. Returns (columns, frozen_answer_key).

    Columns are deduplicated: the raw generator can emit the same TABLE.COLUMN twice
    (small name pools), which would otherwise overstate catalog size and bill you for
    duplicate prompt lines."""
    try:
        from faker import Faker
    except ImportError:
        die("faker not installed. Run: pip install -r requirements.txt")
    fake = Faker(); Faker.seed(seed); rng = random.Random(seed)
    seen, columns, answer_key = set(), [], set()
    n_tables = max(5, n_objects // 20)
    for t in range(n_tables):
        table = f"{fake.word().upper()}_{fake.word().upper()}_{t}"
        for _ in range(max(3, n_objects // n_tables)):
            roll = rng.random()
            if roll < 0.02:
                col, is_gov = rng.choice(GOV_ID_COLUMNS), True
            elif roll < 0.10:
                col, is_gov = rng.choice(DECOY_COLUMNS), False
            else:
                col, is_gov = f"{fake.word().upper()}_{fake.word().upper()}", False
            fq = f"{table}.{col}"
            if fq in seen:
                continue
            seen.add(fq)
            columns.append({"fqname": fq, "is_gov_id": is_gov})
            if is_gov:
                answer_key.add(fq)
    return columns, answer_key


def _post(payload, base, key, timeout=120):
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


def call_model(prompt, max_tokens=3000, retries=4):
    """POST to an OpenAI-compatible endpoint.

    Handles the two incompatible max-token parameter names in the wild: OpenAI's newer
    `max_completion_tokens` and the `max_tokens` that Azure (older api-versions), vLLM,
    Ollama and the Gemini OpenAI-compat layer still require. Retries 429/5xx with backoff
    instead of aborting the whole run."""
    global _TOKEN_PARAM
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if not key:
        die("set OPENAI_API_KEY (and optionally OPENAI_BASE_URL / OPENAI_MODEL)")

    candidates = [_TOKEN_PARAM] if _TOKEN_PARAM else ["max_completion_tokens", "max_tokens"]
    t0 = time.time()
    last = None
    for attempt in range(retries):
        for param in candidates:
            payload = {"messages": [{"role": "user", "content": prompt}], "model": model,
                       param: max_tokens}
            try:
                j = _post(payload, base, key)
                _TOKEN_PARAM = param
                u = j.get("usage", {}) or {}
                det = u.get("completion_tokens_details", {}) or {}
                return {"content": (j.get("choices") or [{}])[0].get("message", {}).get("content", "") or "",
                        "prompt_tokens": u.get("prompt_tokens", 0) or 0,
                        "completion_tokens": u.get("completion_tokens", 0) or 0,
                        "reasoning_tokens": det.get("reasoning_tokens", 0) or 0,
                        "total_tokens": u.get("total_tokens", 0) or 0,
                        "latency_s": round(time.time() - t0, 2)}
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:300]
                last = f"HTTP {e.code} {body}"
                if e.code == 400 and param == "max_completion_tokens" and len(candidates) > 1:
                    continue          # try the other parameter name
                if e.code in (408, 409, 429) or e.code >= 500:
                    break             # retryable — fall through to backoff
                die(f"model call failed: {last}")
            except (urllib.error.URLError, TimeoutError) as e:
                last = str(e); break
        sleep = 2 ** attempt
        print(f"{C['DIM']}  retry {attempt+1}/{retries} in {sleep}s ({last}){C['R']}", file=sys.stderr)
        time.sleep(sleep)
    die(f"model call failed after {retries} attempts: {last}")


def parse_answer(content, all_fqnames):
    """Extract answers as whole TABLE.COLUMN tokens, line by line.

    Two bugs this avoids, both of which silently corrupt scores:
      * substring matching over the whole response counts a column the model explicitly
        EXCLUDED ("do not include X.TAX_ID") as if the model had answered it;
      * substring matching also makes `X.SSN` match inside `X.SSN_LAST4`."""
    valid = {fq.upper() for fq in all_fqnames}
    hits = set()
    for line in content.splitlines():
        if NEGATION.search(line):
            continue
        for tok in FQNAME.findall(line):
            if tok.upper() in valid:
                hits.add(tok.upper())
    return {fq for fq in all_fqnames if fq.upper() in hits}


def score(found, key):
    tp, fp, fn = len(found & key), len(found - key), len(key - found)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=round(prec, 3), recall=round(rec, 3), f1=round(f1, 3))


def route_ungoverned(columns, _key, _fp_rate, _rng):
    catalog = "\n".join(c["fqname"] for c in columns)
    return call_model(f"Here is the full data catalog ({len(columns)} columns):\n{catalog}\n\n{TASK}")


def route_governed(columns, key, fp_rate, rng):
    """Governed catalog returns classifier CANDIDATES, not ground truth.

    True Gov-ID columns plus decoys the classifier flagged in error. The model must still
    discriminate, so precision here is earned rather than assumed."""
    gov = sorted(key)
    decoys = sorted(c["fqname"] for c in columns
                    if not c["is_gov_id"] and c["fqname"].split(".", 1)[1] in DECOY_COLUMNS)
    n_fp = min(int(round(len(gov) * fp_rate)), len(decoys))
    candidates = gov + rng.sample(decoys, n_fp)
    rng.shuffle(candidates)
    return call_model(f"A governed metadata catalog classifier flagged these {len(candidates)} columns "
                      f"as possibly Government-ID related (the classifier is imperfect — some are "
                      f"false positives):\n" + "\n".join(candidates) + f"\n\n{TASK}")


ROUTES = [("ungoverned (context-stuffing)", route_ungoverned),
          ("governed (metadata layer)", route_governed)]


def aggregate(rows):
    """Collapse replicate rows into mean + min/max per (tier, route)."""
    out = {}
    for r in rows:
        out.setdefault((r["tier"], r["route"]), []).append(r)
    agg = []
    for (tier, route), rs in out.items():
        entry = {"tier": tier, "route": route, "replicates": len(rs)}
        for m in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens",
                  "latency_s", "precision", "recall", "f1"):
            vals = [x[m] for x in rs]
            entry[f"{m}_mean"] = round(sum(vals) / len(vals), 3)
            entry[f"{m}_min"], entry[f"{m}_max"] = round(min(vals), 3), round(max(vals), 3)
        agg.append(entry)
    return agg


def write_report(path, model, args, rows):
    if not path:
        return
    with open(path, "w") as fh:
        json.dump({"model": model, "seed": args.seed, "replicates": args.replicates,
                   "classifier_fp_rate": args.classifier_fp_rate,
                   "data_is_synthetic": True, "calls_are_real": True,
                   "governed_route_sees_answer_key": False,
                   "classifier_recall_assumed_perfect": True,
                   "results": rows, "aggregate": aggregate(rows)}, fh, indent=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiers", type=int, nargs="+", default=[300, 1500, 3000])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--replicates", type=int, default=1,
                    help="runs per tier, each with a DIFFERENT catalog seed (seed, seed+1, ...). "
                         "F1 on a few dozen true positives is noisy; re-running one frozen catalog "
                         "only varies model output, not the data.")
    ap.add_argument("--classifier-fp-rate", type=float, default=1.0,
                    help="decoys the governed classifier flags per true positive (default 1.0). "
                         "0.0 hands the governed route the answer key — not a real benchmark.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.classifier_fp_rate == 0:
        print(f"{C['WARN']}WARNING: --classifier-fp-rate 0 gives the governed route the exact answer "
              f"key. It measures transcription, not retrieval. Do not publish this as a benchmark."
              f"{C['R']}\n", file=sys.stderr)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    print(f"{C['HD']}Token-Bleed Benchmark — model={model}{C['R']}")
    print(f"{C['DIM']}Data synthetic (Faker, seeds {args.seed}..{args.seed + args.replicates - 1}); "
          f"model calls + tokens + F1 are REAL. Governed route sees classifier candidates "
          f"(fp-rate {args.classifier_fp_rate}), not the answer key.{C['R']}\n")

    rows = []
    for n in args.tiers:
        print(f"{C['B']}Tier: {n} objects{C['R']}")
        for rep in range(args.replicates):
            seed = args.seed + rep
            columns, key = build_catalog(n, seed)
            all_fq = [c["fqname"] for c in columns]
            rng = random.Random(seed + 100_000)
            tag = f"  {C['DIM']}[seed {seed}] {len(columns)} cols, {len(key)} true Gov-ID{C['R']}"
            print(tag)
            for name, fn in ROUTES:
                r = fn(columns, key, args.classifier_fp_rate, rng)
                sc = score(parse_answer(r["content"], all_fq), key)
                col = C['OK'] if name.startswith("governed") else C['WARN']
                print(f"    {col}{name:<32}{C['R']} tokens={r['total_tokens']:>7,}  F1={sc['f1']:.3f}  "
                      f"{C['DIM']}(P={sc['precision']} R={sc['recall']}){C['R']}")
                rows.append({"tier": n, "seed": seed, "route": name,
                             **{k: r[k] for k in ("prompt_tokens", "completion_tokens",
                                                  "reasoning_tokens", "total_tokens", "latency_s")},
                             **sc})
                write_report(args.out, model, args, rows)   # incremental: a 429 later keeps this
        agg = {a["route"]: a for a in aggregate([r for r in rows if r["tier"] == n])}
        ug, gv = agg["ungoverned (context-stuffing)"], agg["governed (metadata layer)"]
        mult = (ug["total_tokens_mean"] / gv["total_tokens_mean"]) if gv["total_tokens_mean"] else 0
        print(f"  {C['HD']}--> governed used {mult:.1f}x fewer tokens (mean of {ug['replicates']}), "
              f"F1 {gv['f1_mean']:.3f} [{gv['f1_min']:.3f}-{gv['f1_max']:.3f}] vs "
              f"{ug['f1_mean']:.3f} [{ug['f1_min']:.3f}-{ug['f1_max']:.3f}]{C['R']}\n")

    if args.out:
        print(f"{C['DIM']}Full report -> {args.out}{C['R']}")


if __name__ == "__main__":
    main()
