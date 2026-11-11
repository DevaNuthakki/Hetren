"""Acceptance check of a GGUF variant against fp16 (EVAL_PROTOCOL.md, Amendment 2, "Validation check").

Committed before any GGUF validation result exists (2026-11-08); it is run only
after the validation run is logged in ``docs/milestone-4/EXPORT_LOG.md``.

``check --variant V`` reads the variant's validation run
(``<runs>/<variant>/tier<N>/``, written by ``gguf_validation``) and the fp16
comparator (``artifacts/milestone-3/validation-run-1/qlora-validation``):

- **inputs are verified first:** the fp16 rows have Amendment 2's sha256
  (``acee9594…`` tier 1, ``51e1f821…`` tier 2) and the fp16 call logs the
  hashes recorded in ``validation-tier<N>.json``; every file of the GGUF run
  has the hash its completion record lists, the run is the declared one (the
  variant's GGUF sha256 from the committed export manifest, the Mac, 6
  threads, prompt caching on, the pinned llama.cpp commit), and each tier has
  every validation case once, the same cases as fp16;
- **acceptance**, with ``metrics.paired_bootstrap`` (10,000 resamples, seed
  2026), GGUF − fp16; accepted only if all three hold:

  1. pooled over both tiers (800 cases, each paired by tier and case ID), the
     95% interval of the decision-accuracy difference has a lower bound of at
     least −2.0 percentage points;
  2. in each tier, the point estimate of that difference is at least −2.0
     percentage points;
  3. in each tier, the 95% interval of the difference in wrong interventions
     on healthy runs does not lie entirely above zero;

- **reported, not used for acceptance:** the protocol metrics per tier for
  both systems, the per-tier intervals, the episode-agreement rate (cases
  whose full action sequence, probes included, equals fp16's: each call's
  parsed action in order), invalid actions, calls and seconds per call, and
  the calls whose generation ended on a token other than ``<|im_end|>`` or
  ``<|endoftext|>`` (for example llama.cpp's added ``</s>``), with their cases.

``ship`` applies the shipping rule to both variants' checks: the smaller
accepted variant (Q4_K_M before Q8_0); if neither is accepted, Q8_0, with its
measured differences stated.

Commands::

    python -m packages.support_evaluator.gguf_check check --variant Q4_K_M --runs <root> --out <check-Q4_K_M.json>
    python -m packages.support_evaluator.gguf_check ship --checks <check-Q4_K_M.json> <check-Q8_0.json> --out <ship.json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from packages.support_evaluator.checkpoint_selection import VALIDATION_SIZES
from packages.support_evaluator.metrics import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, decision_metrics, paired_bootstrap
from packages.support_evaluator.selection_subset import REPO_ROOT


FP16_DIR = Path("artifacts/milestone-3/validation-run-1/qlora-validation")
# Amendment 2, "Comparator": the fp16 rows of the full validation run of checkpoint-0792.
FP16_ROWS_SHA256 = {1: "acee959428a94ad35ad3af4d6acd518195e79ee369f3e37abb7a30ae93f5a680",
                    2: "51e1f821b9e649dd791bf59552d9912ea8f402e9b836c087b33192b3a236b34b"}
MANIFEST = Path("docs/milestone-4/export.manifest.json")
# The pilot's choice (EXPORT_LOG.md, "Pilot choices", 2026-11-08).
DECLARED = {"platform": "mac", "threads": 6, "cache_prompt": True}
THRESHOLD = -0.02  # 2.0 percentage points
SHIPPING_ORDER = ("Q4_K_M", "Q8_0")  # the smaller accepted variant first
END_OF_GENERATION = {151645: "<|im_end|>", 151643: "<|endoftext|>"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)

    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def run_name(tier: int) -> str:
    return f"tier{tier}-validation"


# --- inputs ---------------------------------------------------------------------------------------------------

def load_fp16(root: Path = REPO_ROOT, rows_sha256: dict[int, str] = FP16_ROWS_SHA256) -> dict[int, dict]:
    """The fp16 rows and calls of each tier, after checking them against the pinned and recorded hashes."""
    found = {}

    for tier in (1, 2):
        directory = Path(root) / FP16_DIR / f"tier{tier}"
        rows_path = directory / f"rows-{run_name(tier)}.jsonl"
        record = json.loads((directory / f"validation-tier{tier}.json").read_text(encoding="utf-8"))

        if sha256_file(rows_path) != rows_sha256[tier] or record["files"][rows_path.name] != rows_sha256[tier]:
            raise ValueError(f"{rows_path} is not the fp16 comparator (Amendment 2: {rows_sha256[tier]})")

        if sha256_file(directory / "calls.jsonl") != record["files"]["calls.jsonl"]:
            raise ValueError(f"{directory / 'calls.jsonl'} does not have the hash its validation record lists")

        found[tier] = {"rows": read_jsonl(rows_path), "calls": read_jsonl(directory / "calls.jsonl")}

    return found


def load_gguf(runs: Path, variant: str, manifest: dict, root: Path = REPO_ROOT) -> dict[int, dict]:
    """The variant's rows, calls and metadata per tier, after checking the run is complete and the declared one."""
    from packages.hetren_serving.export import LLAMA_CPP_COMMIT, STEM

    gguf_sha256 = manifest["gguf"][f"{STEM}-{variant.lower()}.gguf"]["sha256"]
    found = {}

    for tier in (1, 2):
        directory = Path(runs) / variant / f"tier{tier}"
        record_path = directory / f"validation-{variant}-tier{tier}.json"

        if not record_path.exists():
            raise ValueError(f"{record_path} is missing: the {variant} tier {tier} run is not complete")

        record = json.loads(record_path.read_text(encoding="utf-8"))

        for name, digest in record["files"].items():
            if sha256_file(directory / name) != digest:
                raise ValueError(f"{directory / name} does not have the hash its completion record lists")

        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        declared = {"variant": variant, "gguf_sha256": gguf_sha256, "platform": DECLARED["platform"],
                    "threads": DECLARED["threads"], "cache_prompt": DECLARED["cache_prompt"],
                    "llama_cpp_commit": LLAMA_CPP_COMMIT, "tier": tier}
        wrong = {k: metadata.get(k) for k, v in declared.items() if metadata.get(k) != v}

        if wrong:
            raise ValueError(f"{directory} is not the declared run: {wrong} (expected {declared})")

        rows = read_jsonl(directory / f"rows-{run_name(tier)}.jsonl")
        ids = [r["case_id"] for r in rows]

        if len(ids) != VALIDATION_SIZES[tier] or len(set(ids)) != len(ids):
            raise ValueError(f"{directory}: expected {VALIDATION_SIZES[tier]} cases once each, found {len(ids)}")

        found[tier] = {"rows": rows, "calls": read_jsonl(directory / "calls.jsonl"), "metadata": metadata,
                       "record_sha256": sha256_file(record_path)}

    return found


# --- measures -------------------------------------------------------------------------------------------------

def action_sequences(calls: list[dict]) -> dict[str, list]:
    """Each case's parsed actions, call by call (discarded calls excluded); an unparsable reply is kept as text."""
    from packages.action_space import parse_action
    from packages.hetren_baselines.prompt import action_text

    sequences: dict[str, list] = {}

    for call in sorted((c for c in calls if not c.get("discarded")), key=lambda c: (c["case_id"], c["call"])):
        try:
            action = parse_action(action_text(call["text"])).canonical_payload()
        except Exception:
            action = {"unparsable": call["text"].strip()}

        sequences.setdefault(call["case_id"], []).append(action)

    return sequences


def episode_agreement(gguf_calls: list[dict], fp16_calls: list[dict], case_ids: list[str]) -> dict[str, object]:
    a, b = action_sequences(gguf_calls), action_sequences(fp16_calls)
    agree = [c for c in case_ids if a.get(c, []) == b.get(c, [])]
    return {"cases": len(case_ids), "agree": len(agree), "rate": round(len(agree) / len(case_ids), 4) if case_ids else None,
            "differing": sorted(set(case_ids) - set(agree))}


def unexpected_stops(calls: list[dict], tier: int) -> dict[str, object]:
    """Calls whose generated IDs do not end on <|im_end|> or <|endoftext|> (an empty generation counts)."""
    found = [c for c in calls if not c.get("discarded")
             and (not c.get("token_ids") or c["token_ids"][-1] not in END_OF_GENERATION)]
    return {"calls": len(found), "cases": sorted({f"tier {tier} {c['case_id']}" for c in found}),
            "last_tokens": sorted({c["token_ids"][-1] if c.get("token_ids") else None for c in found}, key=str)}


def call_stats(calls: list[dict]) -> dict[str, object]:
    kept = [c for c in calls if not c.get("discarded")]
    return {"calls": len(kept), "seconds_per_call": round(sum(c["seconds"] for c in kept) / len(kept), 3) if kept else None,
            "at_token_limit": sum(c["at_limit"] for c in kept), "non_finite": sum(not c["finite"] for c in kept)}


def keyed(rows: list[dict], tier: int) -> list[dict]:
    """Rows keyed by tier and case ID, for the pooled pairing (84 case IDs occur in both tiers)."""
    return [{**r, "case_id": f"tier{tier}:{r['case_id']}"} for r in rows]


def check_variant(variant: str, gguf: dict[int, dict], fp16: dict[int, dict],
                  resamples: int = BOOTSTRAP_RESAMPLES, seed: int = BOOTSTRAP_SEED) -> dict[str, object]:
    """Amendment 2's three acceptance criteria and the reported measures for one variant."""
    tiers = {}

    for tier in (1, 2):
        g, f = gguf[tier]["rows"], fp16[tier]["rows"]

        if sorted(r["case_id"] for r in g) != sorted(r["case_id"] for r in f):
            raise ValueError(f"tier {tier}: the GGUF and fp16 runs did not score the same cases")

        tiers[tier] = {
            "bootstrap": paired_bootstrap(g, f, resamples=resamples, seed=seed),
            "gguf": decision_metrics(g), "fp16": decision_metrics(f),
            "episode_agreement": episode_agreement(gguf[tier]["calls"], fp16[tier]["calls"], [r["case_id"] for r in g]),
            "calls": {"gguf": call_stats(gguf[tier]["calls"]), "fp16": call_stats(fp16[tier]["calls"])},
            "unexpected_stops": unexpected_stops(gguf[tier]["calls"], tier),
        }

    pooled = paired_bootstrap(keyed(gguf[1]["rows"], 1) + keyed(gguf[2]["rows"], 2),
                              keyed(fp16[1]["rows"], 1) + keyed(fp16[2]["rows"], 2), resamples=resamples, seed=seed)
    accuracy = {t: tiers[t]["bootstrap"]["decision_accuracy"] for t in (1, 2)}
    wrong = {t: tiers[t]["bootstrap"]["wrong_interventions_on_healthy"] for t in (1, 2)}
    criteria = {
        "pooled_accuracy_lower_bound": {"value": pooled["decision_accuracy"]["ci95"][0], "threshold": THRESHOLD,
                                        "holds": pooled["decision_accuracy"]["ci95"][0] >= THRESHOLD},
        **{f"tier{t}_accuracy_point_estimate": {"value": accuracy[t]["difference"], "threshold": THRESHOLD,
                                                "holds": accuracy[t]["difference"] >= THRESHOLD} for t in (1, 2)},
        **{f"tier{t}_wrong_interventions_not_worse": {
            "ci95": wrong[t]["ci95"], "n": wrong[t]["n"],
            "holds": wrong[t]["ci95"] is None or not wrong[t]["ci95"][0] > 0} for t in (1, 2)},
    }
    agreement = [tiers[t]["episode_agreement"] for t in (1, 2)]
    return {
        "amendment": "EVAL_PROTOCOL.md, Amendment 2, Validation check",
        "variant": variant, "resamples": resamples, "seed": seed,
        "accepted": all(c["holds"] for c in criteria.values()), "criteria": criteria,
        "pooled": {"cases": pooled["decision_accuracy"]["n"], "bootstrap": pooled},
        "episode_agreement": {"agree": sum(a["agree"] for a in agreement), "cases": sum(a["cases"] for a in agreement),
                              "rate": round(sum(a["agree"] for a in agreement) / sum(a["cases"] for a in agreement), 4)},
        "unexpected_stops": sum(tiers[t]["unexpected_stops"]["calls"] for t in (1, 2)),
        "tiers": {f"tier{t}": tiers[t] for t in (1, 2)},
        "inputs": {"fp16_rows_sha256": FP16_ROWS_SHA256,
                   "gguf_records_sha256": {f"tier{t}": gguf[t].get("record_sha256") for t in (1, 2)}},
    }


def ship(checks: dict[str, dict]) -> dict[str, object]:
    """The smaller accepted variant (Q4_K_M before Q8_0); if neither, Q8_0 with its measured differences."""
    if sorted(checks) != sorted(SHIPPING_ORDER):
        raise ValueError(f"expected checks for {sorted(SHIPPING_ORDER)}, found {sorted(checks)}")

    accepted = [v for v in SHIPPING_ORDER if checks[v]["accepted"]]
    chosen = accepted[0] if accepted else "Q8_0"
    differences = {f"tier{t}": checks[chosen]["tiers"][f"tier{t}"]["bootstrap"] for t in (1, 2)}
    return {"shipped": chosen, "accepted": accepted, "state_differences": not accepted,
            "differences": {**differences, "pooled": checks[chosen]["pooled"]["bootstrap"]},
            "rule": "the smaller accepted variant (Q4_K_M before Q8_0); if neither is accepted, Q8_0 with its "
                    "measured differences stated in the model card and in the CLI's output"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("check", help="acceptance of one variant (after its validation run is logged)")
    one.add_argument("--variant", required=True, choices=SHIPPING_ORDER)
    one.add_argument("--runs", required=True, type=Path, help="the validation runs' root (<root>/<variant>/tier<N>/)")
    one.add_argument("--out", required=True, type=Path)
    both = commands.add_parser("ship", help="the shipping rule over both variants' checks")
    both.add_argument("--checks", required=True, type=Path, nargs=2)
    both.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        if args.command == "check":
            manifest = json.loads((REPO_ROOT / MANIFEST).read_text(encoding="utf-8"))
            result = check_variant(args.variant, load_gguf(args.runs, args.variant, manifest), load_fp16())
        else:
            checks = {}

            for path in args.checks:
                check = json.loads(path.read_text(encoding="utf-8"))
                checks[check["variant"]] = check

            result = ship(checks)
    except ValueError as exc:
        print(f"STOP: {exc}", file=sys.stderr)
        return 2

    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    keys = ("variant", "accepted", "criteria", "episode_agreement", "unexpected_stops") if args.command == "check" else \
        ("shipped", "accepted", "state_differences")
    print(json.dumps({k: result[k] for k in keys}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
