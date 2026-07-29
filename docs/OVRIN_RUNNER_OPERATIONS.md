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

A successful claim returns a plaintext claim token once.

The runner must provide that claim token when starting, renewing, completing, or failing the job. Ovrin stores only its hash.

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
