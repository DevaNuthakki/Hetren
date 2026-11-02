"""The live test split: plan, neutral world specs, and a token estimate.

``live_plan`` draws cases balanced over every case kind (held-out families
included) and their variants, on world seeds from ``LIVE_SEED_RANGE``, which
never overlaps the dataset's seed range, so no live world appears in any
other split. The behaviour is ``live``: the live model is the agent.

``export_live`` writes what the live recording script may see and what only
the evaluator may see, in separate places:

- ``specs/run-NNNN.json``: one world spec payload and ticket ID per run, in
  shuffled order with neutral run IDs (no kind, variant or truth);
- ``evaluator/live_plan.jsonl``: run ID -> planned case and truth.

``estimate_live_tokens`` runs every scripted behaviour on every exported
world through a counting model and applies the calibrated per-call input
estimate (``packages.integrations.openai_agents.budget``). Output tokens use
the Milestone 1 live measurement per call.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from functools import partial
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from agents import Model, ModelResponse

from environments.support.fixtures import SupportEnvironment, WorldSpec
from environments.support.generator import generate_world
from environments.support.tools import SUPPORT_TOOL_DESCRIPTIONS, SUPPORT_TOOL_SCHEMAS, SUPPORT_TOOLS
from packages.action_gateway import AllowListPolicy, GatedTool, ToolGateway
from packages.contracts import ContractError
from packages.integrations.openai_agents import RunProvenance, gateway_function_tools, run_agent
from packages.integrations.openai_agents.budget import estimate_input_tokens
from packages.support_agent import (
    BEHAVIOURS,
    LIVE_TEST_MODEL_SETTINGS,
    ScriptedSupportModel,
    build_support_agent,
    task_message,
)
from packages.support_evaluator.injectors import INJECTORS, inject
from packages.support_evaluator.plan import DEFAULT_PLAN_KINDS, PlannedCase, planned_payload


LIVE_FORMAT = "hetren-support-live-test"
LIVE_FORMAT_VERSION = 1
LIVE_BEHAVIOUR = "live"
LIVE_SEED_RANGE = (1_000_000, 2_000_000)
LIVE_MAX_TURNS = 10
# Milestone 1 live runs (gpt-4.1-mini, 20 calls): 19-28 output tokens per call.
OUTPUT_TOKENS_PER_CALL_MEAN = 22.6
OUTPUT_TOKENS_PER_CALL_MAX = 28


def live_plan(per_kind: int, seed: int) -> tuple[tuple[PlannedCase, Any], ...]:
    """Balanced planned cases with their injected worlds; redraws seeds an injector rejects."""
    rng = random.Random(seed)
    plan = []

    for kind in DEFAULT_PLAN_KINDS:
        variants = INJECTORS[kind][1]

        for index in range(per_kind):
            variant = variants[index % len(variants)]

            while True:
                planned = PlannedCase(
                    case_kind=kind, case_variant=variant, behaviour=LIVE_BEHAVIOUR,
                    world_seed=rng.randrange(*LIVE_SEED_RANGE), case_seed=rng.randrange(1_000_000),
                )
                try:
                    case = inject(kind, generate_world(planned.world_seed), random.Random(planned.case_seed), variant)
                except ContractError:
                    continue

                plan.append((planned, case))
                break

    return tuple(plan)


def _line(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"


def export_live(out_dir: Path, *, per_kind: int, seed: int) -> dict[str, object]:
    out_dir = Path(out_dir)

    if out_dir.exists() and any(out_dir.iterdir()):
        raise FileExistsError(f"{out_dir} must be empty or new")

    plan = list(live_plan(per_kind, seed))
    random.Random(f"{seed}:order").shuffle(plan)
    (out_dir / "specs").mkdir(parents=True)
    (out_dir / "evaluator").mkdir()
    spec_hashes, evaluator_lines = {}, []

    for number, (planned, case) in enumerate(plan, start=1):
        run_id = f"run-{number:04d}"
        spec = _line({"run_id": run_id, "ticket_id": case.truth.target_ticket_id, "world": case.spec.canonical_payload()})
        (out_dir / "specs" / f"{run_id}.json").write_text(spec, encoding="utf-8")
        spec_hashes[run_id] = hashlib.sha256(spec.encode("utf-8")).hexdigest()
        evaluator_lines.append(_line({"run_id": run_id, "planned": planned_payload(planned), "truth": case.truth.canonical_payload()}))

    evaluator_text = "".join(evaluator_lines)
    (out_dir / "evaluator" / "live_plan.jsonl").write_text(evaluator_text, encoding="utf-8")
    composition = Counter((p.case_kind, p.case_variant) for p, _ in plan)
    manifest = {
        "format": LIVE_FORMAT,
        "format_version": LIVE_FORMAT_VERSION,
        "parameters": {"per_kind": per_kind, "seed": seed, "seed_range": list(LIVE_SEED_RANGE)},
        "runs": len(plan),
        "composition": {f"{kind}/{variant}": n for (kind, variant), n in sorted(composition.items())},
        "files": {
            "specs": hashlib.sha256("".join(f"{k} {v}\n" for k, v in sorted(spec_hashes.items())).encode()).hexdigest(),
            "evaluator/live_plan.jsonl": hashlib.sha256(evaluator_text.encode("utf-8")).hexdigest(),
        },
        "regenerate": f"python -m packages.support_evaluator.live --out {out_dir.as_posix()} --per-kind {per_kind} --seed {seed}",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


# Token estimate


@dataclass
class _CountingModel(Model):
    inner: ScriptedSupportModel
    encoding: Any
    estimates: list[int] = field(default_factory=list)

    @property
    def hetren_provenance(self):
        return self.inner.hetren_provenance

    @property
    def hetren_model_id(self):
        return self.inner.hetren_model_id

    async def get_response(self, system_instructions, input, *args, **kwargs) -> ModelResponse:
        self.estimates.append(estimate_input_tokens(system_instructions, input, self.encoding))
        return await self.inner.get_response(system_instructions, input, *args, **kwargs)

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError


def estimate_run(spec_payload: dict, behaviour: str, encoding) -> list[int]:
    """Estimated input tokens per model call for one scripted behaviour on one exported world."""
    environment = SupportEnvironment(WorldSpec.from_payload(spec_payload["world"]))
    gateway = ToolGateway(
        tools=[
            GatedTool(name, partial(f, environment), SUPPORT_TOOL_SCHEMAS[name], SUPPORT_TOOL_DESCRIPTIONS[name])
            for name, f in SUPPORT_TOOLS.items()
        ],
        policy=AllowListPolicy(SUPPORT_TOOLS),
        state_sha256=environment.state_sha256,
    )
    model = _CountingModel(ScriptedSupportModel(behaviour), encoding)
    run_agent(
        agent=build_support_agent(
            environment=environment, tools=gateway_function_tools(gateway),
            model=model, model_settings=LIVE_TEST_MODEL_SETTINGS,
        ),
        task_input=task_message(spec_payload["ticket_id"]), gateway=gateway,
        run_id="run-0001", provenance=RunProvenance.SCRIPTED, max_turns=LIVE_MAX_TURNS,
    )
    return model.estimates


def estimate_live_tokens(out_dir: Path, encoding) -> dict[str, object]:
    out_dir = Path(out_dir)
    plans = {
        row["run_id"]: row["planned"]
        for row in map(json.loads, (out_dir / "evaluator" / "live_plan.jsonl").open(encoding="utf-8"))
    }
    per_behaviour: dict[str, list[tuple[str, list[int]]]] = {b: [] for b in BEHAVIOURS}

    for path in sorted((out_dir / "specs").glob("run-*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))

        for behaviour in BEHAVIOURS:
            per_behaviour[behaviour].append((plans[spec["run_id"]]["case_kind"], estimate_run(spec, behaviour, encoding)))

    summary = {}

    for behaviour, runs in per_behaviour.items():
        calls = [len(c) for _, c in runs]
        inputs = [sum(c) for _, c in runs]
        summary[behaviour] = {
            "runs": len(runs),
            "calls_per_run_mean": sum(calls) / len(calls),
            "input_tokens_per_run_mean": sum(inputs) / len(inputs),
            "input_tokens_per_run_max": max(inputs),
            "input_tokens_total": sum(inputs),
            "output_tokens_total_mean": sum(calls) * OUTPUT_TOKENS_PER_CALL_MEAN,
            "output_tokens_total_max": sum(calls) * OUTPUT_TOKENS_PER_CALL_MAX,
            "input_tokens_per_run_mean_by_kind": {
                kind: round(sum(sum(c) for k, c in runs if k == kind) / sum(k == kind for k, _ in runs), 1)
                for kind in sorted({k for k, _ in runs})
            },
        }

    return summary


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Export the live test split's world specs.")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--per-kind", required=True, type=int)
    parser.add_argument("--seed", required=True, type=int)
    args = parser.parse_args(argv)
    print(json.dumps(export_live(args.out, per_kind=args.per_kind, seed=args.seed), indent=2, sort_keys=True))
    return 0


__all__ = [
    "LIVE_BEHAVIOUR",
    "LIVE_FORMAT",
    "LIVE_FORMAT_VERSION",
    "LIVE_MAX_TURNS",
    "LIVE_SEED_RANGE",
    "estimate_live_tokens",
    "estimate_run",
    "export_live",
    "live_plan",
]


if __name__ == "__main__":
    raise SystemExit(main())
