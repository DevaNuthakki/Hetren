# Hetren Secure Runner Operations

Hetren's Phase 3 runner platform coordinates speech evaluation jobs on trusted local or CI infrastructure.

This design allows private audio, transcripts, model files, and repository data to remain inside infrastructure controlled by the operator.

## Current capabilities

The runner platform supports:

- Project-scoped runner registration
- One-time registration tokens
- Hashed runner credentials
- Authenticated runner heartbeats
- Project-scoped evaluation jobs
- Capability-aware assignment
- Priority and scheduled availability
- PostgreSQL row locking for atomic claims
- Claim tokens stored only as hashes
- Claim leases and renewal
- Expired-lease recovery
- Controlled retries and maximum attempts
- Claim-protected lifecycle transitions
- Cancellation with immediate claim invalidation
- Assigned-runner control-status authorization
- Active administrative-cancellation polling
- Configurable cooperative execution deadlines
- Structured job-log persistence
- Authenticated atomic log ingestion
- Server-assigned sequence and attempt numbers
- Cursor-based structured-log retrieval
- Log filtering by execution attempt and severity level
- Standalone HTTP runner client without direct database access
- Continuous local polling with controlled idle waiting
- Background lease renewal during active execution
- Background job-control monitoring during active execution
- Cooperative interruption for cancellation, timeout, and shutdown
- Final control-status verification before successful completion
- Controlled placeholder execution for allowlisted jobs
- CLI administration for enqueue, cancellation, recovery, and revocation

## Security rules

Runner credentials, registration tokens, and claim tokens are secrets.

Plaintext tokens must not be:

- Committed to Git
- Written into application logs
- Stored inside runner-job input payloads
- Shared through insecure communication channels

Hetren stores hashes of runner credentials and claim tokens instead of their plaintext values.

## Issue a registration token

From the `backend` directory:

    python scripts/issue_runner_registration_token.py \
      --project-id 1 \
      --label "Local ASR runner" \
      --ttl-minutes 30

The plaintext registration token is displayed once. The runner exchanges it through the registration API for a runner credential.

Registration tokens cannot be reused.

## Revoke a runner

    python scripts/revoke_runner.py \
      --runner-public-id "<runner-public-id>"

Revocation prevents the runner credential from authenticating again.

## Configure the standalone local runner

The standalone runner communicates with Hetren only through the HTTP API.
It does not require direct PostgreSQL access.

Supply the runner credential through the process environment or an approved
secret-injection mechanism. Do not commit the credential to source control or
include it in job payloads or logs.

Example local configuration:

    export HETREN_RUNNER_API_URL="http://127.0.0.1:8000"
    export HETREN_RUNNER_CREDENTIAL="hetren_runner_REPLACE_ME"
    export HETREN_RUNNER_VERSION="0.1.0"
    export HETREN_RUNNER_CAPABILITIES='["asr","cpu"]'
    export HETREN_RUNNER_REQUEST_TIMEOUT_SECONDS=30
    export HETREN_RUNNER_LEASE_SECONDS=300
    export HETREN_RUNNER_POLL_INTERVAL_SECONDS=5
    export HETREN_RUNNER_LEASE_RENEWAL_INTERVAL_SECONDS=60
    export HETREN_RUNNER_CONTROL_POLL_INTERVAL_SECONDS=2
    export HETREN_RUNNER_EXECUTION_TIMEOUT_SECONDS=3600
    export HETREN_RUNNER_ASR_PROVIDER="mock_local"
    export HETREN_RUNNER_ASR_MODEL="mock-asr-foundation"
    export HETREN_RUNNER_ASR_DEVICE="cpu"
    export HETREN_RUNNER_ASR_COMPUTE_TYPE="int8"

Configuration rules include:

- At least one capability is required
- Request timeout must be greater than `0` and no more than `300` seconds
- Job lease must be between `1` and `3600` seconds
- Poll interval must be greater than `0` and no more than `300` seconds
- Lease-renewal interval must be greater than `0` and no more than `1800` seconds
- Lease-renewal interval must be shorter than the configured job lease
- Control-poll interval must be greater than `0` and no more than `300` seconds
- Control-poll interval must be shorter than the lease-renewal interval
- Execution timeout must be greater than `0` and no more than `86400` seconds
- ASR provider must be `mock_local` or `faster_whisper`
- ASR model, device, and compute type must be non-empty

The credential is represented as a secret by the runner settings model and is
not included in normal settings representations.

## Run the standalone local runner

From the `backend` directory:

    python scripts/run_local_runner.py

For a bounded validation run:

    python scripts/run_local_runner.py --max-cycles 1

For one-shot CI execution:

    python scripts/run_local_runner.py --ci

CI mode always runs exactly one polling cycle. It succeeds only when one job
completes. Its process exit codes are:

- `0`: one job completed
- `3`: no compatible job was available
- `4`: the job failed or timed out
- `5`: the job was cancelled
- `6`: the runner stopped before completing a job
- `1`: runner API, protocol, or execution coordination failed
- `2`: runner configuration was invalid
- `130`: the process was interrupted

`--ci` and `--max-cycles` cannot be used together.

Each polling cycle:

1. Sends an authenticated heartbeat
2. Attempts to claim one compatible queued job
3. Starts the claimed job
4. Uploads a structured execution-started log
5. Starts background lease-renewal and job-control workers
6. Executes the job through the cooperative executor contract
7. Stops both background workers before terminal handling
8. Performs a final assigned-runner control-status check
9. Completes, fails, cancels, or stops according to the observed state

The runner waits for the configured polling interval only when the queue is
idle. After a completed or failed job, it immediately begins the next cycle
instead of sleeping unnecessarily.

During active execution, one background worker renews the job lease while a
second worker monitors assigned-runner control state, the configured execution
deadline, and process shutdown requests.

The control worker calls:

    POST /runners/jobs/{job_public_id}/control

The endpoint authenticates the runner credential and verifies that the job is
assigned to that exact runner. It intentionally does not accept the claim token,
because administrative cancellation immediately removes the stored claim-token
hash.

Executors receive an `ExecutionControl` object. A real executor must inspect it
regularly at safe checkpoints by using `raise_if_stopped()`, `is_set()`, or
`wait()`. Python execution threads are not forcefully terminated.

Before reporting success, the runner stops its background workers and performs
one final control-status check. This closes the race where cancellation occurs
as the executor is returning.

Observed outcomes are handled as follows:

- Administrative cancellation stops the executor cooperatively. The runner
  does not append another claim-protected log and does not call complete or
  fail, because the server has already cancelled the job and invalidated its
  claim token.
- Execution timeout appends an `execution_timed_out` log when possible and
  transitions the active job to `failed`.
- `SIGINT` or `SIGTERM` sets the shared shutdown event and stops an active
  cooperative executor. The runner does not report false success or failure.
  The unfinished claim is later handled through lease expiry and recovery.
- Lease-renewal failure prevents successful completion and causes a controlled
  failure attempt.
- Control-status API failure stops the runner because it cannot safely
  determine the remote job state.

The command prints a final summary containing:

- Total cycles
- Idle cycles
- Completed jobs
- Failed jobs
- Cancelled jobs
- Timed-out jobs
- Whether a stop was requested

Timed-out jobs are included in the failed-job count and are also reported
separately.

## Run multiple runners

A project can operate multiple runners concurrently.

Every runner process should have:

- Its own registered runner identity
- Its own runner name
- Its own runner credential
- Capabilities matching the jobs it should execute

Each runner process currently executes one job at a time. Therefore, five
independently registered runner processes can execute up to five jobs
concurrently.

PostgreSQL row locking and atomic claims prevent compatible runners from
claiming the same queued job. Runners that find no compatible work receive an
idle response.

Do not intentionally share one runner credential across multiple processes.
Separate identities make authentication, heartbeats, leases, logs, revocation,
and operational auditing unambiguous.

Runner processes do not share live process memory. They coordinate through
persisted Hetren jobs, structured logs, results, debug evidence, and future
artifact records.

## Current local execution boundary

The default executor handles only the allowlisted `asr_evaluation` job type.

For each claimed ASR evaluation job, it:

- Retrieves project-scoped evaluation context through the authenticated API
- Downloads only the claim-protected allowlisted audio file
- Stores audio inside a temporary runner-owned directory
- Supports `.wav`, `.mp3`, and `.m4a` input
- Resolves the configured `mock_local` or `faster_whisper` provider
- Uses the evaluation run's stored model name
- Checks cooperative execution control before and after remote access and model execution
- Submits only the generated transcript and controlled provider metadata
- Lets the backend calculate WER, CER, quality label, and error summary
- Completes the job and persists one evaluation result atomically
- Deletes temporary downloaded audio after success or failure
- Reports generic failures without persisting sensitive provider exceptions

The executor does not accept arbitrary shell commands, arbitrary code, backend
filesystem paths, runner-supplied metrics, or runner-controlled lifecycle
state.

Long model operations must inspect `ExecutionControl` at safe checkpoints.
Python threads cannot be forcibly terminated safely when a provider ignores
cooperative stop signals.

One-shot CI runner mode is available through `--ci`.

The repository workflow at `.github/workflows/ci.yml` validates Python
compilation, Alembic migration state, the fast backend suite, the complete
PostgreSQL-enabled suite, frontend linting, and the frontend production build.

The repository validation workflow does not require a persistent runner
credential. External deployment workflows can run
`python scripts/run_local_runner.py --ci` with a securely injected registered
runner credential when one queued Hetren job should be executed.

## Enqueue a runner job

Only allowlisted job types can be enqueued.

The currently supported job type is:

    asr_evaluation

Example:

    python scripts/enqueue_runner_job.py \
      --project-id 1 \
      --name "ASR regression evaluation" \
      --job-type asr_evaluation \
      --capability asr \
      --input-json '{"evaluation_run_id":42}' \
      --priority 10 \
      --max-attempts 3

Job input is validated and stored as structured JSON. Hetren does not execute arbitrary shell commands or code from the input payload.

### Required capabilities

Repeat `--capability` when a job needs multiple capabilities:

    --capability asr \
    --capability cpu

A runner must provide every required capability before it can claim the job.

### Scheduled availability

Use an ISO 8601 timestamp containing a UTC offset:

    --available-at "2026-07-30T09:00:00-05:00"

The job remains unavailable until the specified time.

### Priority

Priority values range from `-1000` to `1000`.

Higher-priority jobs are selected first. Jobs with equal priority are ordered by availability time and database ID.

## Cancel a runner job

Queued, claimed, and running jobs can be cancelled:

    python scripts/cancel_runner_job.py \
      --job-public-id "<job-public-id>"

Cancellation:

- Sets the status to `cancelled`
- Records the cancellation timestamp
- Clears the active lease
- Removes the stored claim-token hash
- Prevents the previous claim token from being reused
- Preserves the assigned runner and start history for claimed or running jobs
- Becomes visible to the exact assigned runner through the control-status API

The local runner observes cancellation during active cooperative execution and
does not attempt to reuse the invalidated claim token.

Completed and failed jobs cannot be cancelled.

## Recover expired jobs

    python scripts/recover_expired_runner_jobs.py \
      --limit 100

Recovery processes claimed or running jobs whose leases expired.

Jobs with attempts remaining return to the queue. Jobs that exhausted their maximum attempts transition to `failed`.

The maximum recovery batch size is `1000`.

## Authenticated runner API

Registered runners authenticate using:

    Authorization: Bearer <runner-credential>

The job lifecycle uses:

    POST /runners/jobs/claim
    POST /runners/jobs/{job_public_id}/start
    POST /runners/jobs/{job_public_id}/control
    POST /runners/jobs/{job_public_id}/renew
    POST /runners/jobs/{job_public_id}/complete
    POST /runners/jobs/{job_public_id}/fail
    POST /runners/jobs/{job_public_id}/logs
    POST /runners/jobs/{job_public_id}/logs/query
    POST /runners/jobs/{job_public_id}/asr/context
    POST /runners/jobs/{job_public_id}/asr/audio
    POST /runners/jobs/{job_public_id}/asr/result

A successful claim returns a plaintext claim token once.

The runner must provide that claim token when starting, renewing, completing,
failing, appending logs, or retrieving logs for the job. Hetren stores only its
hash.

The control-status endpoint is different. It accepts only the authenticated
runner credential and job public ID. It returns `active` or `cancelled` only
when the job belongs to the same project and is assigned to that exact runner.
Unknown jobs, other projects, other runners, expired claims, queued jobs, and
completed or failed jobs return one generic unavailable response.

## Job lifecycle

    queued
      -> claimed
      -> running
      -> completed

    queued / claimed / running
      -> cancelled

    claimed / running
      -> failed

    expired claimed / running
      -> queued when attempts remain
      -> failed when attempts are exhausted

Long-running jobs should renew their lease before it expires. Once a lease expires, the previous claim token is no longer accepted.

## Structured job logs

Runners can append structured execution logs while they own an active, unexpired job claim.

Log ingestion uses:

    POST /runners/jobs/{job_public_id}/logs

The runner credential is supplied through the Bearer authorization header. The claim token is supplied inside the JSON request body.

Example request:

    {
      "claim_token": "hetren_claim_REPLACE_ME",
      "entries": [
        {
          "level": "info",
          "event_type": "asr.started",
          "message": "ASR evaluation started.",
          "context_payload": {
            "evaluation_run_id": 42
          }
        },
        {
          "level": "warning",
          "event_type": "asr.slow",
          "message": "Audio processing is slower than expected.",
          "context_payload": {
            "elapsed_seconds": 18.4
          }
        }
      ]
    }

Supported log levels are:

    debug
    info
    warning
    error

Each request can contain between `1` and `100` entries.

Hetren validates the complete batch before writing anything. If one entry is invalid, the entire batch is rejected and no entries are persisted.

The server assigns:

- The log public ID
- The project, job, and runner ownership fields
- A monotonically increasing sequence number
- The current job attempt number
- The creation timestamp

The runner cannot choose or overwrite those values.

Log limits include:

- Event type: maximum `100` characters
- Message: maximum `10000` characters
- Context payload: JSON object with a maximum serialized size of `65536` bytes

Log context must not contain runner credentials, registration tokens, claim tokens, private keys, passwords, or other secrets.

## Retrieve structured job logs

Controlled log retrieval uses:

    POST /runners/jobs/{job_public_id}/logs/query

A POST endpoint is used so the claim token remains in the request body instead of appearing in URL query parameters or common HTTP access logs.

Example request:

    {
      "claim_token": "hetren_claim_REPLACE_ME",
      "after_sequence": 0,
      "limit": 100,
      "attempt_number": null,
      "level": null
    }

Query controls:

- `after_sequence` defaults to `0` and must not be negative
- `limit` defaults to `100` and cannot exceed `200`
- `attempt_number` optionally filters logs to one execution attempt
- `level` optionally filters by `debug`, `info`, `warning`, or `error`

Logs are returned in ascending sequence order.

Example response shape:

    {
      "logs": [],
      "has_more": false,
      "next_after_sequence": null
    }

For a non-empty response, `next_after_sequence` contains the final returned sequence number. The runner can use that value in the next request to retrieve only newer logs.

When more matching records remain beyond the current page, `has_more` is `true`.

Retrieval is allowed only when:

- The runner credential is active
- The job belongs to the runner's project
- The job is assigned to that runner
- The claim token is valid
- The job status is `claimed` or `running`
- The job lease has not expired

Invalid job IDs, assignments, claim tokens, leases, and terminal job states return the same generic claim-unavailable response so internal ownership state is not exposed.

Read-only log retrieval does not take runner-job transition locks. This allows polling without unnecessarily blocking log ingestion, lease renewal, completion, or failure transitions.


## Read-only runner operations UI

The project workspace includes a read-only runner operations section for
engineers inspecting secure execution infrastructure.

It displays:

- Registered runner count
- Active runner count
- Active and failed job counts
- Runner status, version, capabilities, and last heartbeat
- Recent project-scoped runner jobs
- Assigned runner and execution-attempt information
- Controlled job failure messages
- Ordered safe structured logs

The frontend uses these project-scoped endpoints:

    GET /projects/{project_id}/runner-operations
    GET /projects/{project_id}/runner-jobs/{job_public_id}/logs

The runner operations responses intentionally exclude:

- Runner credentials and credential hashes
- Registration tokens and token hashes
- Job claim tokens and claim-token hashes
- Runner system information
- Raw job input and result payloads
- Private audio or filesystem paths
- Structured-log context payloads

Job-log retrieval supports cursor-based pagination through
`after_sequence` and `limit`. Logs are returned in ascending sequence order.

Runner revocation and job cancellation remain administrative CLI operations.
They are not exposed as browser write actions because Hetren does not yet have
a separate authenticated human-administrator identity layer. This preserves
the existing security boundary while still providing useful operational
visibility.
