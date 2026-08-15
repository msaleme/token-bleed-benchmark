#!/usr/bin/env python3
"""
token_bleed_benchmark.py — reproduce the "Stop the Token Bleed" benchmark yourself.

Inspired by McKnight Consulting Group's study "Stop the Token Bleed: Benchmarking the
Benefits of Governed Metadata for Enterprise AI" (Jake Dolezal & William McKnight,
August 2026, sponsored by Informatica, a Salesforce company). That study held the model
constant and compared how an AI agent REACHES enterprise data:

  * ungoverned "context stuffing" — dump the raw schema into the prompt
  * cheap lexical prefilter       — name-only regex returns candidates
  * governed metadata layer       — pre-classified catalog returns candidates

Their finding: governed access won on BOTH cost (up to ~89x fewer tokens at scale) and
accuracy (F1 1.000 vs 0.29-0.66 ungoverned). See the article for their full methodology.

THIS SCRIPT lets you reproduce that structure against ANY OpenAI-compatible endpoint and
generate YOUR OWN numbers, so you don't have to take anyone's word for it.

What's real vs. synthetic
--------------------------
  * The DATA is synthetic — generated with the open-source Faker library, modeled on a
    financial-services catalog, with fixed per-tier quotas of Government-ID columns and
    decoys. The answer key is FROZEN by seed before any model sees the data — no tuning,
    no leakage.
  * The MODEL CALLS, TOKEN COUNTS, and F1 SCORES are REAL. Your numbers will differ from
    the article's (different model, endpoint, and route implementation) — that is the
    point. Cite the article for their figures; cite your run for yours.

The governed route is NOT given the answer key
----------------------------------------------
  A governed catalog in the real world returns CANDIDATES from a classifier, and the
  classifier is imperfect. So `route_governed` passes the true Government-ID columns
  MIXED WITH decoy columns the classifier flagged by mistake (`--classifier-fp-rate`,
  default 1.0 = one false positive per true positive). `--classifier-fn-rate` can also
  omit true positives to model imperfect recall. The model still has to discriminate;
  it can and does lose precision. If the governed route were handed only the true
  positives it would be transcribing an answer key, not retrieving.

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
import argparse, datetime, hashlib, importlib.metadata, json, os, random, re, subprocess, sys, time, urllib.error, urllib.request

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

# Per-call HTTP timeout in seconds. Overridden by --timeout / OPENAI_TIMEOUT for slower
# local/self-hosted models (a large context-stuffing prompt on a local model can exceed the
# default). Env is read at import so it applies even if main() isn't the entry point.
_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT", "120"))


def die(msg, code=2):
    print(f"{C['BAD']}ERROR:{C['R']} {msg}", file=sys.stderr); sys.exit(code)


def build_catalog(n_objects, seed, gov_id_rate=0.02, decoy_rate=0.08):
    """Synthetic financial-services metadata catalog. Returns (columns, frozen_answer_key).

    Columns are deduplicated: the raw generator can emit the same TABLE.COLUMN twice
    (small name pools), which would otherwise overstate catalog size and bill you for
    duplicate prompt lines."""
    try:
        from faker import Faker
    except ImportError:
        die("faker not installed. Run: pip install -r requirements.txt")
    fake = Faker(); Faker.seed(seed); rng = random.Random(seed)
    columns, answer_key = [], set()
    n_tables = max(5, n_objects // 20)
    # Fixed quotas make every replicate within a tier equally class-imbalanced.
    # The old Bernoulli draw could produce very different positive counts per seed,
    # especially at the 300-object tier, making F1 comparisons needlessly noisy.
    n_gov = max(1, round(n_objects * gov_id_rate))
    n_decoy = min(round(n_objects * decoy_rate), n_objects - n_gov)
    labels = ([True] * n_gov) + ([False] * (n_objects - n_gov))
    rng.shuffle(labels)
    object_index = 0
    for t in range(n_tables):
        table = f"{fake.word().upper()}_{fake.word().upper()}_{t}"
        for _ in range(max(3, n_objects // n_tables)):
            if object_index >= n_objects:
                break
            is_gov = labels[object_index]
            if is_gov:
                col = rng.choice(GOV_ID_COLUMNS)
            elif n_decoy > 0:
                # Assign a fixed number of lexical look-alikes, independent of seed.
                # Removing one each time avoids another Bernoulli source of variance.
                col = rng.choice(DECOY_COLUMNS) if n_decoy else f"{fake.word().upper()}_{fake.word().upper()}"
                n_decoy -= 1
            else:
                col, is_gov = rng.choice(DECOY_COLUMNS), False
                # Non-look-alike background fields deliberately cannot match the lexical baseline.
                col = f"{fake.word().upper()}_{fake.word().upper()}_{object_index}"
            fq = f"{table}.{col}_{object_index}" if col in GOV_ID_COLUMNS + DECOY_COLUMNS else f"{table}.{col}"
            columns.append({"fqname": fq, "is_gov_id": is_gov})
            if is_gov:
                answer_key.add(fq)
            object_index += 1
    return columns, answer_key


def _post(payload, base, key, timeout=None):
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout or _TIMEOUT).read().decode())


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
                        "returned_model": j.get("model") or model,
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
    hint = ""
    if last and "timed out" in last.lower():
        hint = (f" — every attempt hit the {_TIMEOUT}s per-call timeout; a large prompt on a slower "
                f"local/self-hosted model can exceed it. Raise it with --timeout or OPENAI_TIMEOUT.")
    die(f"model call failed after {retries} attempts: {last}{hint}")


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


def _call_route(prompt):
    result = call_model(prompt)
    result["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
    return result


def route_ungoverned(columns, _key, _fp_rate, _fn_rate, _rng):
    catalog = "\n".join(c["fqname"] for c in columns)
    return _call_route(f"Here is the full data catalog ({len(columns)} columns):\n{catalog}\n\n{TASK}")


# A deliberately cheap non-governance baseline: name-only matching. It has no
# classifier, embeddings, lineage, or semantic metadata. It can win if labels
# alone explain the observed benefit.
LEXICAL_GOV_ID = re.compile(r"(?:^|_)(?:SSN|NATIONAL_ID|PASSPORT)(?:_|$)")


def lexical_candidates(columns):
    return [c["fqname"] for c in columns
            if LEXICAL_GOV_ID.search(c["fqname"].split(".", 1)[1])]


def route_lexical(columns, _key, _fp_rate, _fn_rate, _rng):
    candidates = lexical_candidates(columns)
    return _call_route(f"A cheap name-only lexical prefilter selected these {len(candidates)} columns "
                       f"as potentially Government-ID related:\n" + "\n".join(candidates) + f"\n\n{TASK}")


def governed_candidates(columns, key, fp_rate, fn_rate, rng):
    """Return the synthetic classifier's candidate set.

    `fn_rate` deliberately removes true Government-ID fields before the model sees the
    candidate set. It is a sensitivity control, not a calibrated model of a particular
    classifier. Keeping it explicit prevents a perfect-recall assumption from hiding in
    the benchmark implementation.
    """
    gov = sorted(key)
    n_fn = min(int(round(len(gov) * fn_rate)), len(gov))
    omitted = set(rng.sample(gov, n_fn)) if n_fn else set()
    visible_gov = [fq for fq in gov if fq not in omitted]
    def is_decoy(fqname):
        field = fqname.split(".", 1)[1]
        return field in DECOY_COLUMNS or any(field.startswith(f"{name}_") for name in DECOY_COLUMNS)
    decoys = sorted(c["fqname"] for c in columns if not c["is_gov_id"] and is_decoy(c["fqname"]))
    n_fp = min(int(round(len(gov) * fp_rate)), len(decoys))
    candidates = visible_gov + rng.sample(decoys, n_fp)
    rng.shuffle(candidates)
    return candidates


def route_governed(columns, key, fp_rate, fn_rate, rng):
    """Governed catalog returns classifier CANDIDATES, not ground truth.

    True Gov-ID columns plus decoys the classifier flagged in error. The model must still
    discriminate, so precision here is earned rather than assumed."""
    candidates = governed_candidates(columns, key, fp_rate, fn_rate, rng)
    return _call_route(f"A governed metadata catalog classifier flagged these {len(candidates)} columns "
                      f"as possibly Government-ID related (the classifier is imperfect — some are "
                      f"false positives):\n" + "\n".join(candidates) + f"\n\n{TASK}")


ROUTES = [("ungoverned (context-stuffing)", route_ungoverned),
          ("lexical prefilter (cheap baseline)", route_lexical),
          ("governed (metadata layer)", route_governed)]


def randomized_routes(seed):
    """Return a deterministic but seed-randomized execution order for one replicate."""
    ordered = ROUTES[:]
    random.Random(seed + 200_000).shuffle(ordered)
    return ordered


def aggregate(rows):
    """Collapse replicate rows into distributions and normal-approximation 95% CIs."""
    out = {}
    for r in rows:
        out.setdefault((r["tier"], r["route"]), []).append(r)
    agg = []
    for (tier, route), rs in out.items():
        entry = {"tier": tier, "route": route, "replicates": len(rs)}
        for m in ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens",
                  "latency_s", "precision", "recall", "f1"):
            vals = [x[m] for x in rs]
            mean = sum(vals) / len(vals)
            variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1) if len(vals) > 1 else 0
            margin = 1.96 * (variance ** 0.5) / (len(vals) ** 0.5) if len(vals) > 1 else 0
            entry[f"{m}_values"] = vals
            entry[f"{m}_mean"] = round(mean, 3)
            entry[f"{m}_min"], entry[f"{m}_max"] = round(min(vals), 3), round(max(vals), 3)
            entry[f"{m}_ci95_low"] = round(mean - margin, 3)
            entry[f"{m}_ci95_high"] = round(mean + margin, 3)
        agg.append(entry)
    return agg


def _git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _package_versions():
    versions = {"python": sys.version.split()[0]}
    for package in ("Faker",):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def write_report(path, model, args, rows):
    if not path:
        return
    with open(path, "w") as fh:
        json.dump({"schema_version": "1.0", "requested_model": model, "seed": args.seed,
                   "replicates": args.replicates,
                   "classifier_fp_rate": args.classifier_fp_rate,
                   "classifier_fn_rate": args.classifier_fn_rate,
                   "git_commit": _git_commit(), "package_versions": _package_versions(),
                   "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "data_is_synthetic": True, "calls_are_real": True,
                   "governed_route_sees_answer_key": False,
                   "classifier_recall_assumed_perfect": args.classifier_fn_rate == 0,
                   "token_param_used": _TOKEN_PARAM,   # which max-token name the endpoint accepted
                   "call_timeout_s": _TIMEOUT,
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
    ap.add_argument("--classifier-fn-rate", type=float, default=0.0,
                    help="fraction of true Government-ID columns omitted by the synthetic classifier "
                         "(default 0.0). This is a sensitivity control, not a calibrated classifier.")
    ap.add_argument("--timeout", type=int, default=None,
                    help="per-call HTTP timeout in seconds (default 120, or OPENAI_TIMEOUT). "
                         "Raise it for slower local/self-hosted models — a large context-stuffing "
                         "prompt on e.g. a local Ollama model can exceed 120s.")
    ap.add_argument("--retain-responses", action="store_true",
                    help="store raw model responses in the report for a full scorer audit. "
                         "Without this, reports retain response hashes, parsed answers, and answer keys.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.classifier_fp_rate < 0:
        die("--classifier-fp-rate must be non-negative")
    if not 0 <= args.classifier_fn_rate <= 1:
        die("--classifier-fn-rate must be between 0 and 1")

    global _TIMEOUT
    if args.timeout is not None:
        _TIMEOUT = args.timeout

    if args.classifier_fp_rate == 0:
        print(f"{C['WARN']}WARNING: --classifier-fp-rate 0 gives the governed route the exact answer "
              f"key. It measures transcription, not retrieval. Do not publish this as a benchmark."
              f"{C['R']}\n", file=sys.stderr)

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    print(f"{C['HD']}Token-Bleed Benchmark — model={model}{C['R']}")
    print(f"{C['DIM']}Data synthetic (Faker, fixed class quotas, seeds {args.seed}..{args.seed + args.replicates - 1}); "
          f"model calls + tokens + F1 are REAL. Governed route sees classifier candidates "
          f"(fp-rate {args.classifier_fp_rate}, fn-rate {args.classifier_fn_rate}), not the answer key.{C['R']}\n")

    rows = []
    for n in args.tiers:
        print(f"{C['B']}Tier: {n} objects{C['R']}")
        for rep in range(args.replicates):
            seed = args.seed + rep
            columns, key = build_catalog(n, seed)
            all_fq = [c["fqname"] for c in columns]
            tag = f"  {C['DIM']}[seed {seed}] {len(columns)} cols, {len(key)} true Gov-ID{C['R']}"
            print(tag)
            ordered_routes = randomized_routes(seed)
            route_order = [name for name, _ in ordered_routes]
            for position, (name, fn) in enumerate(ordered_routes, start=1):
                # Candidate sampling is route-specific so execution order cannot perturb it.
                route_rng = random.Random(f"{seed}:{name}:candidate-set")
                r = fn(columns, key, args.classifier_fp_rate, args.classifier_fn_rate, route_rng)
                parsed = parse_answer(r["content"], all_fq)
                sc = score(parsed, key)
                col = C['OK'] if name.startswith("governed") else C['WARN']
                print(f"    {col}{name:<32}{C['R']} prompt={r['prompt_tokens']:>7,} total={r['total_tokens']:>7,}  F1={sc['f1']:.3f}  "
                      f"{C['DIM']}(P={sc['precision']} R={sc['recall']}){C['R']}")
                rows.append({"tier": n, "seed": seed, "route": name,
                             "catalog_columns": len(columns), "answer_key_count": len(key),
                             "route_position": position, "route_order": route_order,
                             "requested_model": model, "returned_model": r["returned_model"],
                             "prompt_sha256": r["prompt_sha256"],
                             "response_sha256": hashlib.sha256(r["content"].encode()).hexdigest(),
                             "scorer_audit": {"parsed_answers": sorted(parsed),
                                              "answer_key": sorted(key)},
                             **{k: r[k] for k in ("prompt_tokens", "completion_tokens",
                                                  "reasoning_tokens", "total_tokens", "latency_s")},
                             **sc})
                if args.retain_responses:
                    rows[-1]["model_response"] = r["content"]
                write_report(args.out, model, args, rows)   # incremental: a 429 later keeps this
        agg = {a["route"]: a for a in aggregate([r for r in rows if r["tier"] == n])}
        ug, gv = agg["ungoverned (context-stuffing)"], agg["governed (metadata layer)"]
        mult = (ug["prompt_tokens_mean"] / gv["prompt_tokens_mean"]) if gv["prompt_tokens_mean"] else 0
        print(f"  {C['HD']}--> governed used {mult:.1f}x fewer prompt tokens (mean of {ug['replicates']}), "
              f"F1 {gv['f1_mean']:.3f} [{gv['f1_min']:.3f}-{gv['f1_max']:.3f}] vs "
              f"{ug['f1_mean']:.3f} [{ug['f1_min']:.3f}-{ug['f1_max']:.3f}]{C['R']}\n")

    if args.out:
        print(f"{C['DIM']}Full report -> {args.out}{C['R']}")


if __name__ == "__main__":
    main()
