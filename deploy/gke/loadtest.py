"""Step 6b's load test on GKE (operator), with the autoscaling record the k6 summary alone lacks. Standard library
and kubectl only; the k6 Job is deploy/loadtest/job.yaml.

    python3 deploy/gke/loadtest.py --out artifacts/milestone-4/loadtest-gke-1 --prices <price_check.py --out file>

It creates the ConfigMap (k6.js and the fixture input), starts the Job with STEPS and STEP_SECONDS (default
1,2,4,8,16 x 300 s), and every 15 s records the HPA's current and desired replicas and CPU, the Deployment's ready
replicas and the inference pool's Ready nodes, until the Job ends. Then it saves the k6 summary, the cluster's events
and the samples, and writes ``summary.json``:
- per step: p50/p95/p99 latency, diagnoses per second, error rate;
- scaling, from the samples: when the HPA first wanted 2 replicas, when the second pod was ready and the second node
  joined, and the seconds between them. These are null when the cluster had already scaled up before the test
  (``scaled_before_start``), as in session 1, where the first diagnosis (phase 6) drove the HPA to 2 replicas;
- timeline, from Kubernetes' own records (events, and the pod and node objects at the end): the HPA's rescale, the
  cluster autoscaler's trigger, the second node's creation and readiness, and the second pod's creation, scheduling,
  model download and readiness, in UTC and in seconds after the rescale. It holds whenever the scale-up happened,
  provided its events are still kept (GKE keeps events for about an hour);
- node-hours over the test, and the node cost per 1,000 diagnoses at the list price from the price check. That is
  the nodes only: NAT, disks and the GKE fee are in the session estimate.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import threading
import time


REPO_ROOT = Path(__file__).resolve().parents[2]
JOB = REPO_ROOT / "deploy/loadtest/job.yaml"
SCRIPT = REPO_ROOT / "deploy/loadtest/k6.js"
INPUTS = REPO_ROOT / "deploy/loadtest/inputs.json"
POOL_LABEL = "hetren/pool=inference"
SAMPLE_SECONDS = 15


def kubectl(*args: str, namespace: str | None = None, check: bool = True, stdin: str | None = None) -> str:
    command = ["kubectl", *(["-n", namespace] if namespace else []), *args]
    return subprocess.run(command, check=check, capture_output=True, text=True, input=stdin).stdout


def render_job(steps: str, step_seconds: int) -> str:
    text = JOB.read_text(encoding="utf-8")

    for old, new in (('value: "1,2,4,8,16"', f'value: "{steps}"'), ('value: "300"', f'value: "{step_seconds}"')):
        if text.count(old) != 1:
            raise ValueError(f"{JOB} no longer has exactly one {old!r}")
        text = text.replace(old, new)

    return text


def sample(namespace: str, release: str) -> dict:
    hpa = json.loads(kubectl("get", "hpa", release, "-o", "json", namespace=namespace))
    deployment = json.loads(kubectl("get", "deployment", release, "-o", "json", namespace=namespace))
    nodes = json.loads(kubectl("get", "nodes", "-l", POOL_LABEL, "-o", "json"))
    ready_nodes = sum(1 for n in nodes["items"]
                      if any(c["type"] == "Ready" and c["status"] == "True" for c in n["status"].get("conditions", [])))
    metrics = hpa.get("status", {}).get("currentMetrics") or [{}]
    cpu = metrics[0].get("resource", {}).get("current", {}).get("averageUtilization")
    return {"t": round(time.time(), 1), "hpa_current": hpa["status"].get("currentReplicas"),
            "hpa_desired": hpa["status"].get("desiredReplicas"), "cpu_percent": cpu,
            "ready_replicas": deployment["status"].get("readyReplicas", 0), "nodes": len(nodes["items"]),
            "ready_nodes": ready_nodes}


def node_hours(samples: list[dict]) -> float:
    """The inference pool's node count integrated over the samples' times (trapezoids)."""
    total = 0.0

    for a, b in zip(samples, samples[1:]):
        total += (b["t"] - a["t"]) * (a["nodes"] + b["nodes"]) / 2

    return total / 3600


def first(samples: list[dict], key: str, at_least: int) -> float | None:
    return next((s["t"] for s in samples if (s.get(key) or 0) >= at_least), None)


def scaled_up(entry: dict) -> bool:
    return any((entry.get(key) or 0) >= 2 for key in ("hpa_desired", "ready_replicas", "nodes"))


def scaling(samples: list[dict]) -> dict:
    start = samples[0]["t"] if samples else None
    before = bool(samples) and scaled_up(samples[0])
    wanted, pod, node = first(samples, "hpa_desired", 2), first(samples, "ready_replicas", 2), first(samples, "ready_nodes", 2)

    def since(t: float | None) -> float | None:
        return None if t is None or start is None or before else round(t - start, 1)

    return {"scaled_before_start": before,
            "hpa_wanted_2_at_s": since(wanted), "second_node_ready_at_s": since(node),
            "second_pod_ready_at_s": since(pod),
            "scale_up_seconds": None if wanted is None or pod is None or before else round(pod - wanted, 1),
            "max_nodes": max((s["nodes"] for s in samples), default=0),
            "max_ready_replicas": max((s["ready_replicas"] for s in samples), default=0)}


def _time(text: str | None) -> float | None:
    return None if not text else datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp()


def _condition(obj: dict, kind: str) -> str | None:
    return next((c.get("lastTransitionTime") for c in obj.get("status", {}).get("conditions", [])
                 if c.get("type") == kind and c.get("status") == "True"), None)


def timeline(events: list[dict], pods: list[dict], nodes: list[dict], release: str) -> dict:
    """The scale-up from 1 to 2, from Kubernetes' records: each moment in UTC, and in seconds after the rescale."""

    def event(reason: str, kind: str, name: str | None = None, text: str = "") -> str | None:
        times = sorted(e.get("firstTimestamp") or e.get("eventTime") or e["metadata"]["creationTimestamp"]
                       for e in events if e.get("reason") == reason and e["involvedObject"].get("kind") == kind
                       and (name is None or e["involvedObject"].get("name") == name) and text in e.get("message", ""))
        return times[0] if times else None

    def created(items: list[dict]) -> list[dict]:
        return sorted(items, key=lambda o: o["metadata"]["creationTimestamp"])

    node = (created(nodes)[1:] or [None])[0]
    pod = (created(pods)[1:] or [None])[0]
    fetch = {} if pod is None else next(
        (s.get("state", {}).get("terminated", {}) for s in pod.get("status", {}).get("initContainerStatuses", [])
         if s.get("name") == "fetch-model"), {})
    moments = {
        "hpa_rescaled_to_2": event("SuccessfulRescale", "HorizontalPodAutoscaler", release, "New size: 2"),
        "second_pod_created": pod and pod["metadata"]["creationTimestamp"],
        "scale_up_triggered": event("TriggeredScaleUp", "Pod", pod and pod["metadata"]["name"]),
        "second_node_created": node and node["metadata"]["creationTimestamp"],
        "second_node_ready": node and (event("NodeReady", "Node", node["metadata"]["name"]) or _condition(node, "Ready")),
        "second_pod_scheduled": pod and _condition(pod, "PodScheduled"),
        "fetch_model_started": fetch.get("startedAt"),
        "fetch_model_finished": fetch.get("finishedAt"),
        "second_pod_ready": pod and _condition(pod, "Ready"),
    }
    origin = _time(moments["hpa_rescaled_to_2"])
    return {"utc": moments, "seconds_after_rescale": {
        key: None if origin is None or _time(value) is None else round(_time(value) - origin, 1)
        for key, value in moments.items()}, "second_node": node and node["metadata"]["name"],
        "second_pod": pod and pod["metadata"]["name"]}


def summarize(k6: dict, samples: list[dict], node_hour_usd: float | None, scale_timeline: dict | None = None) -> dict:
    diagnoses = sum(step.get("diagnoses", 0) for step in k6.get("steps_summary", {}).values())
    hours = node_hours(samples)
    cost = None if node_hour_usd is None else hours * node_hour_usd
    return {"k6": k6, "scaling": scaling(samples), "timeline": scale_timeline,
            "node_hours": round(hours, 4), "diagnoses": diagnoses,
            "node_usd_per_hour": node_hour_usd, "node_cost_usd": None if cost is None else round(cost, 4),
            "node_cost_per_1000_diagnoses_usd": None if cost is None or not diagnoses else round(1000 * cost / diagnoses, 2),
            "samples": len(samples),
            "duration_s": round(samples[-1]["t"] - samples[0]["t"], 1) if len(samples) > 1 else 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", required=True, type=Path, help="an empty folder for the results")
    parser.add_argument("--prices", type=Path, help="price_check.py --out file (for the node cost)")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--release", default="hetren")
    parser.add_argument("--steps", default="1,2,4,8,16")
    parser.add_argument("--step-seconds", type=int, default=300)
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.out.exists() and any(args.out.iterdir()):
        print(f"STOP: {args.out} is not empty", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    price = None if args.prices is None else \
        json.loads(args.prices.read_text(encoding="utf-8"))["estimate"]["e2_standard_4_per_hour"]
    ns = args.namespace
    kubectl("delete", "job", "hetren-loadtest", "--ignore-not-found", namespace=ns)
    kubectl("delete", "configmap", "hetren-loadtest", "--ignore-not-found", namespace=ns)
    kubectl("create", "configmap", "hetren-loadtest", f"--from-file={SCRIPT}", f"--from-file=inputs.json={INPUTS}",
            namespace=ns)
    samples, done = [], threading.Event()

    def record() -> None:
        with open(args.out / "samples.jsonl", "a", encoding="utf-8") as handle:
            while not done.is_set():
                try:
                    entry = sample(ns, args.release)
                    samples.append(entry)
                    handle.write(json.dumps(entry, sort_keys=True) + "\n")
                    handle.flush()
                    print(f"{time.strftime('%H:%M:%S')}  replicas {entry['ready_replicas']} ready "
                          f"(HPA {entry['hpa_current']} -> {entry['hpa_desired']}, CPU {entry['cpu_percent']}%), "
                          f"nodes {entry['ready_nodes']}/{entry['nodes']}", flush=True)
                except subprocess.CalledProcessError as exc:
                    print(f"sample failed: {exc.stderr.strip()}", flush=True)

                done.wait(SAMPLE_SECONDS)

    try:
        if scaled_up(sample(ns, args.release)):
            print("NOTE: already scaled up before the test (HPA, replicas or nodes at 2): the sampled scale-up times "
                  "will be null; the timeline from Kubernetes' events still records it", flush=True)
    except subprocess.CalledProcessError as exc:
        print(f"sample failed: {exc.stderr.strip()}", flush=True)

    thread = threading.Thread(target=record, daemon=True)
    thread.start()
    started = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    kubectl("apply", "-f", "-", namespace=ns, stdin=render_job(args.steps, args.step_seconds))
    deadline = time.time() + len(args.steps.split(",")) * args.step_seconds + 900
    outcome = "timeout"

    while time.time() < deadline:
        status = json.loads(kubectl("get", "job", "hetren-loadtest", "-o", "json", namespace=ns)).get("status", {})

        if status.get("succeeded"):
            outcome = "succeeded"
            break

        if status.get("failed"):
            outcome = "failed"
            break

        time.sleep(10)

    time.sleep(SAMPLE_SECONDS)  # one more sample after the end
    done.set()
    thread.join(60)
    log = kubectl("logs", "job/hetren-loadtest", namespace=ns, check=False)
    (args.out / "k6.log").write_text(log, encoding="utf-8")
    records = {}

    for name, command in (("events", ("get", "events", "-A", "-o", "json")),
                          ("pods", ("get", "pods", "-n", ns, "-l", f"app.kubernetes.io/instance={args.release}",
                                    "-o", "json")),
                          ("nodes", ("get", "nodes", "-l", POOL_LABEL, "-o", "json"))):
        text = kubectl(*command, check=False)
        (args.out / f"{name}.json").write_text(text, encoding="utf-8")
        try:
            records[name] = json.loads(text).get("items", [])
        except json.JSONDecodeError:
            records[name] = []

    lines = [line for line in log.splitlines() if line.startswith("HETREN_LOADTEST ")]
    k6 = json.loads(lines[-1].split(" ", 1)[1]) if lines else {}
    scale_timeline = timeline(records["events"], records["pods"], records["nodes"], args.release)
    result = {"job": outcome, "started_utc": started, "finished_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "steps": args.steps, "step_seconds": args.step_seconds,
              **summarize(k6, samples, price, scale_timeline)}
    (args.out / "summary.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("job", "diagnoses", "node_hours", "node_cost_per_1000_diagnoses_usd",
                                             "scaling", "timeline")}, indent=2))
    return 0 if outcome == "succeeded" and k6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
