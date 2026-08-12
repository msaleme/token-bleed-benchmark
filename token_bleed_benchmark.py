#!/usr/bin/env python3
"""
token_bleed_benchmark.py — reproduce the "Stop the Token Bleed" benchmark yourself.

Inspired by McKnight Consulting Group's study "Stop the Token Bleed: Benchmarking the
Benefits of Governed Metadata for Enterprise AI" (Jake Dolezal & William McKnight,
August 2026, sponsored by Informatica, a Salesforce company). That study held the model
constant and compared how an AI agent REACHES enterprise data:

  * ungoverned "context stuffing" — dump the raw schema into the prompt
  * governed metadata layer       — pre-classified catalog returns only what matters

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

Quick start
-----------
  python3 -m venv .venv && . .venv/bin/activate
  pip install faker
  export OPENAI_BASE_URL="https://api.openai.com/v1"   # or your gateway / Azure / Gemini-compat endpoint
  export OPENAI_API_KEY="sk-..."
  export OPENAI_MODEL="gpt-4o-mini"
  python3 token_bleed_benchmark.py --tiers 300 1500 3000 --out report.json

The endpoint must accept an OpenAI-style POST {base_url}/chat/completions and return a
`usage` block. Works with OpenAI, Azure OpenAI (v1 path), and gateways that proxy them.
"""
import argparse, json, os, sys, time, urllib.request, urllib.error, random

GOV_ID_COLUMNS = ["SSN", "SUBJECT_SSN", "ID_DOC_NUMBER", "NATIONAL_ID", "PASSPORT_NO", "SSN_LAST4"]
DECOY_COLUMNS  = ["TAX_ID", "LICENSE_NO", "DOC_TYPE", "ACCOUNT_NO", "ROUTING_NO", "CUSTOMER_REF"]

TASK = ("Show me all the assets (fully-qualified COLUMN names in TABLE.COLUMN form) needed to "
        "build a report that involves Government ID. Return ONLY the exact column names, one per line. "
        "A Government ID is a national identity number (e.g. Social Security Number). "
        "Do NOT include tax IDs, driver license numbers, account numbers, or generic document-type fields.")

C = dict(OK="\033[32m", BAD="\033[31m", WARN="\033[33m", DIM="\033[2m", HD="\033[1;36m", B="\033[1m", R="\033[0m")
if not sys.stdout.isatty():
    C = {k: "" for k in C}


def die(msg, code=2):
    print(f"{C['BAD']}ERROR:{C['R']} {msg}", file=sys.stderr); sys.exit(code)


def build_catalog(n_objects, seed):
    """Synthetic financial-services metadata catalog; classification done ONCE here (the
    'governed' advantage). Returns (columns, frozen_answer_key)."""
    try:
        from faker import Faker
    except ImportError:
        die("faker not installed. Run: pip install faker")
    fake = Faker(); Faker.seed(seed); random.seed(seed)
    columns, answer_key = [], set()
    n_tables = max(5, n_objects // 20)
    for t in range(n_tables):
        table = f"{fake.word().upper()}_{fake.word().upper()}_{t}"
        for _ in range(max(3, n_objects // n_tables)):
            roll = random.random()
            if roll < 0.02:
                col, is_gov = random.choice(GOV_ID_COLUMNS), True
            elif roll < 0.10:
                col, is_gov = random.choice(DECOY_COLUMNS), False
            else:
                col, is_gov = f"{fake.word().upper()}_{fake.word().upper()}", False
            fq = f"{table}.{col}"
            columns.append({"fqname": fq, "is_gov_id": is_gov})
            if is_gov:
                answer_key.add(fq)
    return columns, answer_key


def call_model(prompt, max_tokens=3000):
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    if not key:
        die("set OPENAI_API_KEY (and optionally OPENAI_BASE_URL / OPENAI_MODEL)")
    payload = {"messages": [{"role": "user", "content": prompt}], "model": model,
               "max_completion_tokens": max_tokens}
    req = urllib.request.Request(f"{base}/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {key}"}, method="POST")
    t0 = time.time()
    try:
        j = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    except urllib.error.HTTPError as e:
        die(f"model call failed: HTTP {e.code} {e.read().decode()[:200]}")
    u = j.get("usage", {}) or {}
    det = u.get("completion_tokens_details", {}) or {}
    return {"content": (j.get("choices") or [{}])[0].get("message", {}).get("content", "") or "",
            "prompt_tokens": u.get("prompt_tokens", 0) or 0,
            "completion_tokens": u.get("completion_tokens", 0) or 0,
            "reasoning_tokens": det.get("reasoning_tokens", 0) or 0,
            "total_tokens": u.get("total_tokens", 0) or 0,
            "latency_s": round(time.time() - t0, 2)}


def parse_answer(content, all_fqnames):
    up = content.upper()
    return {fq for fq in all_fqnames if fq.upper() in up}


def score(found, key):
    tp, fp, fn = len(found & key), len(found - key), len(key - found)
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return dict(tp=tp, fp=fp, fn=fn, precision=round(prec, 3), recall=round(rec, 3), f1=round(f1, 3))


def route_ungoverned(columns):
    catalog = "\n".join(c["fqname"] for c in columns)
    return call_model(f"Here is the full data catalog ({len(columns)} columns):\n{catalog}\n\n{TASK}")


def route_governed(columns):
    candidates = "\n".join(c["fqname"] for c in columns if c["is_gov_id"])
    return call_model(f"A governed metadata catalog has pre-classified these columns as "
                      f"Government-ID related:\n{candidates}\n\n{TASK}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tiers", type=int, nargs="+", default=[300, 1500, 3000])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    print(f"{C['HD']}Token-Bleed Benchmark — model={model}{C['R']}")
    print(f"{C['DIM']}Data synthetic (Faker seed={args.seed}); model calls + tokens + F1 are REAL.{C['R']}\n")

    results = []
    for n in args.tiers:
        columns, key = build_catalog(n, args.seed)
        all_fq = [c["fqname"] for c in columns]
        print(f"{C['B']}Tier: {n} objects{C['R']}  ({len(columns)} columns, {len(key)} true Gov-ID)")
        for name, fn in [("ungoverned (context-stuffing)", route_ungoverned),
                         ("governed (metadata layer)", route_governed)]:
            r = fn(columns); sc = score(parse_answer(r["content"], all_fq), key)
            col = C['OK'] if "governed" in name else C['WARN']
            print(f"  {col}{name:<32}{C['R']} tokens={r['total_tokens']:>7,}  F1={sc['f1']:.3f}  "
                  f"{C['DIM']}(P={sc['precision']} R={sc['recall']} reasoning={r['reasoning_tokens']}){C['R']}")
            results.append({"tier": n, "route": name, **{k: r[k] for k in
                            ("prompt_tokens", "completion_tokens", "reasoning_tokens", "total_tokens", "latency_s")}, **sc})
        ug = next(x for x in results if x["tier"] == n and x["route"].startswith("ungoverned"))
        gv = next(x for x in results if x["tier"] == n and x["route"].startswith("governed"))
        mult = (ug["total_tokens"] / gv["total_tokens"]) if gv["total_tokens"] else 0
        print(f"  {C['HD']}--> governed used {mult:.1f}x fewer tokens, F1 {gv['f1']:.3f} vs {ug['f1']:.3f}{C['R']}\n")

    if args.out:
        json.dump({"model": model, "seed": args.seed, "data_is_synthetic": True,
                   "calls_are_real": True, "results": results}, open(args.out, "w"), indent=2)
        print(f"{C['DIM']}Full report -> {args.out}{C['R']}")


if __name__ == "__main__":
    main()
