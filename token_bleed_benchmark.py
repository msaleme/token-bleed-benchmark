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

  Stated assumption: classifier RECALL is perfect BY DEFAULT (every true Gov-ID column
  reaches the candidate set) and stops being so the moment you pass
  `--classifier-fn-rate`. The default is a floor on the governed route's difficulty and
  is the assumption most favorable to it, so run a nonzero false-negative case before
  making an accuracy claim, and say which setting produced the number you cite.

Quick start
-----------
  python3 -m venv .venv && . .venv/bin/activate
  pip install -r requirements.txt
  export OPENAI_BASE_URL="https://api.openai.com/v1"   # or your gateway / Azure / Gemini-compat endpoint
  export OPENAI_API_KEY="sk-..."
  export OPENAI_MODEL="gpt-4o-mini"
  python3 token_bleed_benchmark.py --tiers 300 1500 3000 --replicates 20 --out report.json --retain-responses

The endpoint must accept an OpenAI-style POST {base_url}/chat/completions and return a
`usage` block. Works with OpenAI, Azure OpenAI (v1 path), and gateways that proxy them.
"""
import argparse, datetime, hashlib, importlib.metadata, json, os, random, re, subprocess, sys, time, urllib.error, urllib.request
from urllib.parse import urlsplit, urlunsplit

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

# R2 does not treat a request field being accepted as evidence that a server enforced it.
# The commissioning probe below records observed cap behavior before any benchmark row runs.
_COMPLETION_CAP_PROBE = None

# Endpoint-specific request settings.  R2 uses this for Ollama's `options.num_ctx`;
# the value is retained separately, and must be verified from Ollama's runtime API
# before collection begins.
_REQUEST_OPTIONS = None

# Per-call HTTP timeout in seconds. Overridden by --timeout / OPENAI_TIMEOUT for slower
# local/self-hosted models (a large context-stuffing prompt on a local model can exceed the
# default). Env is read at import so it applies even if main() isn't the entry point.
_TIMEOUT = int(os.environ.get("OPENAI_TIMEOUT", "120"))

# This is the schema boundary between live route results and persisted report rows.  Keep every
# field the R2 adapter uses here, including the actual request parameter, not only its probe.
ROUTE_RESULT_FIELDS = (
    "prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens", "latency_s",
    "route_preparation_ms", "constructed_input_token_count", "context_window_tokens",
    "requested_completion_tokens", "prompt_truncated_by_context", "token_parameter",
    "completion_cap_enforced", "completion_cap_parameter",
)


def persisted_route_fields(result):
    """Select the complete route-result schema retained in every report row."""
    # Failed calls retain nulls rather than crashing report generation; the R2 adapter rejects
    # those rows fail-closed when a required provenance field is absent.
    return {field: result.get(field) for field in ROUTE_RESULT_FIELDS}


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
    attempts = []
    last = None
    for attempt in range(1, retries + 1):
        for param in candidates:
            payload = {"messages": [{"role": "user", "content": prompt}], "model": model,
                       param: max_tokens}
            if _REQUEST_OPTIONS:
                payload["options"] = _REQUEST_OPTIONS
            try:
                j = _post(payload, base, key)
                _TOKEN_PARAM = param
                u = j.get("usage", {}) or {}
                det = u.get("completion_tokens_details", {}) or {}
                attempts.append({"attempt": attempt, "token_parameter": param, "outcome": "success",
                                 "elapsed_s": round(time.time() - t0, 3)})
                return {"success": True,
                        "content": (j.get("choices") or [{}])[0].get("message", {}).get("content", "") or "",
                        "returned_model": j.get("model") or model,
                        "prompt_tokens": u.get("prompt_tokens", 0) or 0,
                        "completion_tokens": u.get("completion_tokens", 0) or 0,
                        "reasoning_tokens": det.get("reasoning_tokens", 0) or 0,
                        "total_tokens": u.get("total_tokens", 0) or 0,
                        "token_parameter": param,
                        "latency_s": round(time.time() - t0, 2),
                        "attempts": attempts}
            except urllib.error.HTTPError as e:
                body = e.read().decode()[:300]
                last = f"HTTP {e.code} {body}"
                attempts.append({"attempt": attempt, "token_parameter": param, "outcome": "error",
                                 "error_class": "HTTPError", "error_message": last,
                                 "elapsed_s": round(time.time() - t0, 3)})
                if e.code == 400 and param == "max_completion_tokens" and len(candidates) > 1:
                    continue          # try the other parameter name
                if e.code in (408, 409, 429) or e.code >= 500:
                    break             # retryable — fall through to backoff
                return {"success": False, "content": "", "returned_model": model,
                        "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0,
                        "total_tokens": 0, "latency_s": round(time.time() - t0, 2),
                        "attempts": attempts, "error_message": f"non-retryable model call failure: {last}"}
            except (urllib.error.URLError, TimeoutError) as e:
                last = str(e)
                attempts.append({"attempt": attempt, "token_parameter": param, "outcome": "error",
                                 "error_class": type(e).__name__, "error_message": last,
                                 "elapsed_s": round(time.time() - t0, 3)})
                break
        if attempt < retries:
            sleep = 2 ** (attempt - 1)
            print(f"{C['DIM']}  retry {attempt}/{retries} in {sleep}s ({last}){C['R']}", file=sys.stderr)
            time.sleep(sleep)
    return {"success": False, "content": "", "returned_model": model,
            "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0,
            "latency_s": round(time.time() - t0, 2), "attempts": attempts,
            "error_message": f"model call failed after {retries} attempts: {last}"}


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


def _call_route(prompt, *, preparation_ms=0, context_window_tokens=None, max_tokens=3000):
    constructed_input_token_count = len(prompt.encode("utf-8"))
    if context_window_tokens is not None and constructed_input_token_count + max_tokens > context_window_tokens:
        return {"success": False, "content": "", "returned_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "prompt_tokens": 0, "completion_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0,
                "latency_s": 0.0,
                "attempts": [{"attempt": 0, "outcome": "context_preflight_refused",
                              "error_class": "ContextBudgetExceeded",
                              "error_message": "constructed input plus completion budget exceeds declared context window"}],
                "error_message": "constructed input plus completion budget exceeds declared context window",
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "route_preparation_ms": round(preparation_ms, 3),
                "constructed_input_token_count": constructed_input_token_count,
                "token_count_method": "utf8_byte_upper_bound",
                "context_window_tokens": context_window_tokens,
                "requested_completion_tokens": max_tokens,
                "prompt_truncated_by_context": None}
    result = call_model(prompt, max_tokens=max_tokens)
    result["prompt_sha256"] = hashlib.sha256(prompt.encode()).hexdigest()
    result["route_preparation_ms"] = round(preparation_ms, 3)
    result["constructed_input_token_count"] = constructed_input_token_count
    result["token_count_method"] = "utf8_byte_upper_bound"
    result["context_window_tokens"] = context_window_tokens
    result["requested_completion_tokens"] = max_tokens
    result["prompt_truncated_by_context"] = False
    result["completion_cap_enforced"] = bool(_COMPLETION_CAP_PROBE and
                                               _COMPLETION_CAP_PROBE.get("enforced"))
    result["completion_cap_parameter"] = (_COMPLETION_CAP_PROBE or {}).get("token_parameter")
    return result


def route_ungoverned(columns, _key, _fp_rate, _fn_rate, _rng, **settings):
    started = time.perf_counter()
    catalog = "\n".join(c["fqname"] for c in columns)
    prompt = f"Here is the full data catalog ({len(columns)} columns):\n{catalog}\n\n{TASK}"
    return _call_route(prompt, preparation_ms=(time.perf_counter() - started) * 1000, **settings)


# A deliberately cheap non-governance baseline: name-only matching. It has no
# classifier, embeddings, lineage, or semantic metadata. It can win if labels
# alone explain the observed benefit.
LEXICAL_GOV_ID = re.compile(r"(?:^|_)(?:SSN|NATIONAL_ID|PASSPORT)(?:_|$)")


def lexical_candidates(columns):
    return [c["fqname"] for c in columns
            if LEXICAL_GOV_ID.search(c["fqname"].split(".", 1)[1])]


def route_lexical(columns, _key, _fp_rate, _fn_rate, _rng, **settings):
    started = time.perf_counter()
    candidates = lexical_candidates(columns)
    prompt = (f"A cheap name-only lexical prefilter selected these {len(candidates)} columns "
              f"as potentially Government-ID related:\n" + "\n".join(candidates) + f"\n\n{TASK}")
    return _call_route(prompt, preparation_ms=(time.perf_counter() - started) * 1000, **settings)


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


def route_governed(columns, key, fp_rate, fn_rate, rng, **settings):
    """Governed catalog returns classifier CANDIDATES, not ground truth.

    True Gov-ID columns plus decoys the classifier flagged in error. The model must still
    discriminate, so precision here is earned rather than assumed."""
    started = time.perf_counter()
    candidates = governed_candidates(columns, key, fp_rate, fn_rate, rng)
    prompt = (f"A governed metadata catalog classifier flagged these {len(candidates)} columns "
              f"as possibly Government-ID related (the classifier is imperfect — some are "
              f"false positives):\n" + "\n".join(candidates) + f"\n\n{TASK}")
    return _call_route(prompt, preparation_ms=(time.perf_counter() - started) * 1000, **settings)


ROUTES = [("ungoverned (context-stuffing)", route_ungoverned),
          ("lexical prefilter (cheap baseline)", route_lexical),
          ("governed (metadata layer)", route_governed)]


def randomized_routes(seed):
    """Return a deterministic but seed-randomized execution order for one replicate."""
    ordered = ROUTES[:]
    random.Random(seed + 200_000).shuffle(ordered)
    return ordered


def preflight_context(tiers, seed, classifier_fp_rate, classifier_fn_rate, context_window_tokens,
                      max_tokens):
    """Refuse R2 collection before a constructed route can exceed its declared context budget.

    The byte count is deliberately an upper bound rather than a provider usage value: a provider
    may silently truncate before reporting prompt usage.  A passing result is therefore a
    conservative fit proof for byte-oriented/BPE tokenizers, and the method is retained.
    """
    rows = []
    for tier in tiers:
        columns, key = build_catalog(tier, seed)
        for name, route in ROUTES:
            rng = random.Random(f"{seed}:{name}:candidate-set")
            if name.startswith("ungoverned"):
                prompt = f"Here is the full data catalog ({len(columns)} columns):\n" + \
                         "\n".join(c["fqname"] for c in columns) + f"\n\n{TASK}"
            elif name.startswith("lexical"):
                candidates = lexical_candidates(columns)
                prompt = (f"A cheap name-only lexical prefilter selected these {len(candidates)} columns "
                          f"as potentially Government-ID related:\n" + "\n".join(candidates) + f"\n\n{TASK}")
            else:
                candidates = governed_candidates(columns, key, classifier_fp_rate, classifier_fn_rate, rng)
                prompt = (f"A governed metadata catalog classifier flagged these {len(candidates)} columns "
                          f"as possibly Government-ID related (the classifier is imperfect — some are "
                          f"false positives):\n" + "\n".join(candidates) + f"\n\n{TASK}")
            upper_bound = len(prompt.encode("utf-8"))
            rows.append({"tier": tier, "seed": seed, "route": name,
                         "constructed_input_token_count": upper_bound,
                         "token_count_method": "utf8_byte_upper_bound",
                         "context_window_tokens": context_window_tokens,
                         "requested_completion_tokens": max_tokens,
                         "fits_context_budget": upper_bound + max_tokens <= context_window_tokens})
    failures = [row for row in rows if not row["fits_context_budget"]]
    return {"schema_version": "1.0", "artifact_type": "token-bleed-context-preflight",
            "rows": rows, "passed": not failures, "failures": failures}


def verify_ollama_runtime_context(required_context_tokens):
    """Load the configured model with `num_ctx`, then verify Ollama's live context length.

    A declared context budget is not evidence by itself: Ollama can serve a model at a lower
    default.  This one-token configuration probe is not a benchmark trial.  It makes the model
    resident with the requested option and reads `/api/ps`, whose `context_length` describes the
    live runner.  Any unavailable or undersized value is a commissioning failure.
    """
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    probe = call_model("Reply only: OK", max_tokens=1, retries=1)
    if not probe["success"]:
        die("R2 Ollama context probe failed; no benchmark trials were run")
    base = os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    parts = urlsplit(base)
    api_path = parts.path[:-3] if parts.path.endswith("/v1") else parts.path
    ps_url = urlunsplit((parts.scheme, parts.netloc, f"{api_path}/api/ps", "", ""))
    try:
        with urllib.request.urlopen(ps_url, timeout=_TIMEOUT) as response:
            running = json.loads(response.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        die(f"cannot verify R2 Ollama runtime context through /api/ps: {exc}")
    matches = [entry for entry in running.get("models", [])
               if entry.get("name") == model or entry.get("model") == model]
    context_length = matches[0].get("context_length") if matches else None
    if not isinstance(context_length, int) or context_length < required_context_tokens:
        die("R2 Ollama runtime context is missing or below the declared context budget "
            f"(required={required_context_tokens}, actual={context_length!r})")
    return {"probe_prompt": "Reply only: OK", "returned_model": probe["returned_model"],
            "requested_num_ctx": _REQUEST_OPTIONS.get("num_ctx") if _REQUEST_OPTIONS else None,
            "observed_context_length": context_length, "api": "/api/ps"}


def verify_completion_cap_enforcement(cap=8):
    """Prove the server enforces a small requested completion cap before R2 collection.

    Some OpenAI-compatible endpoints accept an unknown max-token field and silently ignore it.
    This non-benchmark probe demands a long response, requires measured completion usage, and
    fails closed unless the observed completion count is within the cap.
    """
    if cap <= 0:
        raise ValueError("completion-cap probe requires a positive cap")
    probe = call_model(
        "Write at least two hundred distinct words explaining why exact output limits matter. "
        "Do not stop early.", max_tokens=cap, retries=1)
    completion_tokens = probe.get("completion_tokens")
    token_parameter = probe.get("token_parameter")
    enforced = (probe.get("success") is True and isinstance(completion_tokens, int) and
                completion_tokens > 0 and completion_tokens <= cap and bool(token_parameter))
    return {"probe_prompt": "long-output completion-cap probe", "requested_completion_tokens": cap,
            "observed_completion_tokens": completion_tokens,
            "token_parameter": token_parameter, "returned_model": probe.get("returned_model"),
            "enforced": enforced, "failure_reason": None if enforced else
            "endpoint did not return a positive measured completion count within the requested cap"}


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
        json.dump({"schema_version": "2.0" if getattr(args, "r2", False) else "1.0", "requested_model": model, "seed": args.seed,
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
                   "r2_context_window_tokens": getattr(args, "context_window_tokens", None),
                   "requested_completion_tokens": getattr(args, "max_completion_tokens", 3000),
                   "r2_execution": {"per_call_timeout_s": _TIMEOUT,
                                    "ollama_num_ctx_requested": getattr(args, "ollama_num_ctx", None),
                                    "runtime_context_probe": getattr(args, "runtime_context_probe", None),
                                    "completion_cap_probe": getattr(args, "completion_cap_probe", None),
                                    "completion_cap_enforced": bool((getattr(args, "completion_cap_probe", None) or {}).get("enforced")),
                                    "completion_cap_parameter": (getattr(args, "completion_cap_probe", None) or {}).get("token_parameter")},
                   "r2_provenance": {"endpoint_class": getattr(args, "endpoint_class", None),
                                     "model_digest": getattr(args, "model_digest", None),
                                     "runtime_version": getattr(args, "runtime_version", None),
                                     "hardware": getattr(args, "hardware", None)},
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
    ap.add_argument("--r2", action="store_true",
                    help="enable the R2 fail-closed evidence schema and context preflight")
    ap.add_argument("--context-window-tokens", type=int,
                    help="declared runtime context budget; required with --r2")
    ap.add_argument("--max-completion-tokens", type=int, default=3000,
                    help="requested completion budget, included in R2 context proof")
    ap.add_argument("--preflight-out", default=None,
                    help="write R2 context-budget preflight JSON before any model call")
    ap.add_argument("--preflight-only", action="store_true",
                    help="write and validate the R2 context proof, then exit before model calls")
    ap.add_argument("--endpoint-class", help="R2 endpoint class, e.g. local-openai-compatible")
    ap.add_argument("--model-digest", help="R2 immutable model digest from the serving runtime")
    ap.add_argument("--runtime-version", help="R2 serving-runtime version, e.g. Ollama version")
    ap.add_argument("--hardware", help="R2 hardware/OS identifier retained in report provenance")
    ap.add_argument("--ollama-num-ctx", type=int,
                    help="R2 local-Ollama context setting sent as options.num_ctx on every request")
    ap.add_argument("--verify-ollama-context", action="store_true",
                    help="R2-only: configuration-probe Ollama and require /api/ps to confirm its live context")
    args = ap.parse_args()

    if args.classifier_fp_rate < 0:
        die("--classifier-fp-rate must be non-negative")
    if not 0 <= args.classifier_fn_rate <= 1:
        die("--classifier-fn-rate must be between 0 and 1")
    if args.r2 and (not args.context_window_tokens or args.context_window_tokens <= 0):
        die("--r2 requires a positive --context-window-tokens")
    if args.r2 and not all((args.endpoint_class, args.model_digest, args.runtime_version, args.hardware)):
        die("--r2 requires --endpoint-class, --model-digest, --runtime-version, and --hardware")
    if args.r2 and args.timeout is None:
        die("--r2 requires an explicit --timeout so its execution policy is frozen")
    if args.r2 and (not args.ollama_num_ctx or args.ollama_num_ctx < args.context_window_tokens):
        die("--r2 requires --ollama-num-ctx at least as large as --context-window-tokens")
    if args.r2 and not args.verify_ollama_context:
        die("--r2 requires --verify-ollama-context to confirm the live Ollama context setting")
    if args.max_completion_tokens <= 0:
        die("--max-completion-tokens must be positive")

    global _TIMEOUT, _REQUEST_OPTIONS, _TOKEN_PARAM, _COMPLETION_CAP_PROBE
    if args.timeout is not None:
        _TIMEOUT = args.timeout
    if args.r2:
        _REQUEST_OPTIONS = {"num_ctx": args.ollama_num_ctx}
        # Ollama's OpenAI-compatible endpoint honors max_tokens but accepts and ignores
        # max_completion_tokens. Force the known field, then prove it is actually enforced.
        if args.endpoint_class == "local-openai-compatible":
            _TOKEN_PARAM = "max_tokens"

    if args.classifier_fp_rate == 0:
        print(f"{C['WARN']}WARNING: --classifier-fp-rate 0 gives the governed route the exact answer "
              f"key. It measures transcription, not retrieval. Do not publish this as a benchmark."
              f"{C['R']}\n", file=sys.stderr)

    if args.r2:
        preflight = preflight_context(args.tiers, args.seed, args.classifier_fp_rate,
                                      args.classifier_fn_rate, args.context_window_tokens,
                                      args.max_completion_tokens)
        if not preflight["passed"]:
            if args.preflight_out:
                with open(args.preflight_out, "w") as fh:
                    json.dump(preflight, fh, indent=2)
            die("R2 context preflight failed; no model calls were made")
        args.runtime_context_probe = verify_ollama_runtime_context(args.context_window_tokens)
        args.completion_cap_probe = verify_completion_cap_enforcement()
        _COMPLETION_CAP_PROBE = args.completion_cap_probe
        preflight["runtime_context_probe"] = args.runtime_context_probe
        preflight["completion_cap_probe"] = args.completion_cap_probe
        if args.preflight_out:
            with open(args.preflight_out, "w") as fh:
                json.dump(preflight, fh, indent=2)
        if not args.completion_cap_probe["enforced"]:
            die("R2 completion-cap probe failed; no benchmark trials were run")
        if args.preflight_only:
            print(f"{C['OK']}R2 context preflight passed; no model calls were made.{C['R']}")
            return

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
                r = fn(columns, key, args.classifier_fp_rate, args.classifier_fn_rate, route_rng,
                       context_window_tokens=args.context_window_tokens if args.r2 else None,
                       max_tokens=args.max_completion_tokens)
                parsed = parse_answer(r["content"], all_fq) if r["success"] else set()
                sc = score(parsed, key) if r["success"] else dict(tp=0, fp=0, fn=len(key), precision=0.0, recall=0.0, f1=0.0)
                col = C['OK'] if name.startswith("governed") else C['WARN']
                print(f"    {col}{name:<32}{C['R']} prompt={r['prompt_tokens']:>7,} total={r['total_tokens']:>7,}  F1={sc['f1']:.3f}  "
                      f"{C['DIM']}(P={sc['precision']} R={sc['recall']}){C['R']}")
                rows.append({"tier": n, "seed": seed, "route": name,
                             "catalog_columns": len(columns), "answer_key_count": len(key),
                             "route_position": position, "route_order": route_order,
                             "requested_model": model, "returned_model": r["returned_model"],
                             "prompt_sha256": r["prompt_sha256"],
                             "response_sha256": hashlib.sha256(r["content"].encode()).hexdigest(),
                             "success": r["success"], "attempts": r["attempts"],
                             "error_message": r.get("error_message"),
                             "scorer_audit": {"parsed_answers": sorted(parsed),
                                              "answer_key": sorted(key)},
                             **persisted_route_fields(r),
                             "token_count_method": r["token_count_method"],
                             **sc})
                if args.retain_responses:
                    rows[-1]["model_response"] = r["content"]
                write_report(args.out, model, args, rows)   # incremental: a 429 later keeps this
        agg = {a["route"]: a for a in aggregate([r for r in rows if r["tier"] == n and r["success"]])}
        if set(agg) != {name for name, _ in ROUTES}:
            print(f"{C['BAD']}  incomplete route results at tier {n}; retained failures prevent a comparative summary{C['R']}")
            continue
        ug, gv = agg["ungoverned (context-stuffing)"], agg["governed (metadata layer)"]
        mult = (ug["prompt_tokens_mean"] / gv["prompt_tokens_mean"]) if gv["prompt_tokens_mean"] else 0
        print(f"  {C['HD']}--> governed used {mult:.1f}x fewer prompt tokens (mean of {ug['replicates']}), "
              f"F1 {gv['f1_mean']:.3f} [{gv['f1_min']:.3f}-{gv['f1_max']:.3f}] vs "
              f"{ug['f1_mean']:.3f} [{ug['f1_min']:.3f}-{ug['f1_max']:.3f}]{C['R']}\n")

    if args.out:
        print(f"{C['DIM']}Full report -> {args.out}{C['R']}")


if __name__ == "__main__":
    main()
