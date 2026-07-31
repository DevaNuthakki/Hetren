# Ovrin Secure Runner Operations

Ovrin's Phase 3 runner platform coordinates speech evaluation jobs on trusted local or CI infrastructure.

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
- Structured job-log persistence
- Authenticated atomic log ingestion
- Server-assigned sequence and attempt numbers
- Cursor-based structured-log retrieval
- Log filtering by execution attempt and severity level
- CLI administration for enqueue, cancellation, recovery, and revocation

## Security rules

Runner credentials, registration tokens, and claim tokens are secrets.

Plaintext tokens must not be:

- Committed to Git
- Written into application logs
- Stored inside runner-job input payloads
- Shared through insecure communication channels

Ovrin stores hashes of runner credentials and claim tokens instead of their plaintext values.

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

Job input is validated and stored as structured JSON. Ovrin does not execute arbitrary shell commands or code from the input payload.

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
    POST /runners/jobs/{job_public_id}/renew
    POST /runners/jobs/{job_public_id}/complete
    POST /runners/jobs/{job_public_id}/fail
    POST /runners/jobs/{job_public_id}/logs
    POST /runners/jobs/{job_public_id}/logs/query

A successful claim returns a plaintext claim token once.

The runner must provide that claim token when starting, renewing, completing, failing, appending logs, or retrieving logs for the job. Ovrin stores only its hash.

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
      "claim_token": "ovrin_claim_REPLACE_ME",
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

Ovrin validates the complete batch before writing anything. If one entry is invalid, the entire batch is rejected and no entries are persisted.

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
      "claim_token": "ovrin_claim_REPLACE_ME",
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
