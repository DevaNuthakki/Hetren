// Hetren load test (step 6): stepped concurrency against POST /diagnose, run inside the cluster as a Job
// (deploy/loadtest/job.yaml), so no load balancer or egress is needed.
//
// STEPS: concurrency levels, held STEP_SECONDS each, one after another (default 1,2,4,8,16 x 300 s on GKE;
// the kind smoke test uses 1,2 x 60 s). A diagnosis can queue behind others for minutes at high concurrency, so
// the timeout is 10 minutes.
//
// Inputs: the requests cycle through the distinct inputs in inputs.json (16 training-split examples,
// deploy/loadtest/inputs.json), one after another across all virtual users. So consecutive requests to a replica
// carry different evidence, and llama-server's prompt cache can reuse only what all prompts share (the system
// prompt), as with real traffic. Session 1 sent one input every time, so its latencies are a cached best case.
//
// Rejections: a 503 (the replica's queue is full) is counted as a rejection, not an error. The virtual user then
// waits the Retry-After the API sends before trying again, as a well-behaved client would.
//
// The summary (stdout, JSON) has per step: p50/p95/p99 latency of the accepted requests, diagnoses per second,
// rejections, and the error rate of the accepted requests.
import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { Trend, Rate, Counter } from 'k6/metrics';

const target = __ENV.TARGET || 'http://hetren:8000';
const steps = (__ENV.STEPS || '1,2,4,8,16').split(',').map(Number);
const stepSeconds = Number(__ENV.STEP_SECONDS || 300);
const inputs = JSON.parse(open('/loadtest/inputs.json')).inputs;
const bodies = inputs.map((compact) => JSON.stringify({ compact }));
const DEFAULT_RETRY_SECONDS = 30;  // the API's Retry-After (packages/hetren_cli/api.py)

const latency = {};
const errors = {};
const ok = {};
const rejected = {};
const scenarios = {};
const thresholds = {};

steps.forEach((vus, i) => {
  const name = `c${String(vus).padStart(2, '0')}`;
  latency[name] = new Trend(`latency_${name}`, true);
  errors[name] = new Rate(`errors_${name}`);
  ok[name] = new Counter(`diagnoses_${name}`);
  rejected[name] = new Counter(`rejected_${name}`);
  scenarios[name] = {
    executor: 'constant-vus',
    vus,
    duration: `${stepSeconds}s`,
    startTime: `${i * stepSeconds}s`,
    gracefulStop: '600s',
    exec: 'diagnose',
    env: { STEP: name },
    tags: { step: name },
  };
  thresholds[`latency_${name}`] = ['p(50)>=0'];  // always report the step's percentiles
});

if (__ENV.MAX_ERROR_RATE) {
  thresholds.http_req_failed = [`rate<=${__ENV.MAX_ERROR_RATE}`];
}

export const options = {
  scenarios,
  thresholds,
  summaryTrendStats: ['min', 'med', 'p(95)', 'p(99)', 'max', 'count'],
};

function retrySeconds(header) {
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds > 0 ? seconds : DEFAULT_RETRY_SECONDS;
}

export function diagnose() {
  const step = __ENV.STEP;
  const body = bodies[exec.scenario.iterationInTest % bodies.length];
  const response = http.post(`${target}/diagnose`, body, {
    headers: { 'Content-Type': 'application/json' },
    timeout: '600s',
    tags: { step },
  });

  if (response.status === 503) {
    rejected[step].add(1);
    sleep(retrySeconds(response.headers['Retry-After']));
    return;
  }

  const good = check(response, {
    'status 200': (r) => r.status === 200,
    'a diagnosis': (r) => r.status === 200 && ['decision', 'proposed_recovery', 'needs_probe'].includes(r.json('result.outcome')),
  });
  latency[step].add(response.timings.duration);
  errors[step].add(!good);
  if (good) ok[step].add(1);
}

export function handleSummary(data) {
  const result = { target, steps, step_seconds: stepSeconds, inputs: bodies.length, steps_summary: {} };
  steps.forEach((vus) => {
    const name = `c${String(vus).padStart(2, '0')}`;
    const trend = data.metrics[`latency_${name}`];
    const done = data.metrics[`diagnoses_${name}`];
    const rate = data.metrics[`errors_${name}`];
    const refused = data.metrics[`rejected_${name}`];
    result.steps_summary[name] = {
      concurrency: vus,
      latency_ms: trend ? { p50: trend.values.med, p95: trend.values['p(95)'], p99: trend.values['p(99)'],
                            max: trend.values.max, requests: trend.values.count } : null,
      diagnoses: done ? done.values.count : 0,
      diagnoses_per_second: done ? done.values.count / stepSeconds : 0,
      rejected: refused ? refused.values.count : 0,
      error_rate: rate ? rate.values.rate : null,
    };
  });
  // k6's own rate: every non-2xx response, rejections included.
  result.http_req_failed = data.metrics.http_req_failed ? data.metrics.http_req_failed.values.rate : null;
  return { stdout: `HETREN_LOADTEST ${JSON.stringify(result)}\n` };
}
