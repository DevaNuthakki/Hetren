import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  getProjectRunnerJobLogs,
  getProjectRunnerOperations,
  type RunnerOperationsJob,
  type RunnerOperationsLogPage,
  type RunnerOperationsSnapshot,
} from "./api";

type RunnerOperationsPanelProps = {
  projectId: number;
};

function formatTimestamp(value: string | null) {
  if (!value) {
    return "Not available";
  }

  return new Date(value).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function cleanLabel(value: string) {
  return value.replaceAll("_", " ");
}

function getStatusTone(status: string) {
  if (status === "active" || status === "completed") {
    return "good";
  }

  if (
    status === "queued" ||
    status === "claimed" ||
    status === "running"
  ) {
    return "warning";
  }

  if (
    status === "failed" ||
    status === "cancelled" ||
    status === "revoked"
  ) {
    return "danger";
  }

  return "neutral";
}

export function RunnerOperationsPanel({
  projectId,
}: RunnerOperationsPanelProps) {
  const [snapshot, setSnapshot] =
    useState<RunnerOperationsSnapshot | null>(null);
  const [selectedJobPublicId, setSelectedJobPublicId] =
    useState<string | null>(null);
  const [logPage, setLogPage] =
    useState<RunnerOperationsLogPage | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [isLogsLoading, setIsLogsLoading] = useState(false);
  const [errorMessage, setErrorMessage] =
    useState<string | null>(null);
  const [logsError, setLogsError] =
    useState<string | null>(null);

  const loadSnapshot = useCallback(async () => {
    try {
      setIsLoading(true);
      setErrorMessage(null);

      const data = await getProjectRunnerOperations(
        projectId,
      );

      setSnapshot(data);
      setSelectedJobPublicId((current) => {
        if (
          current &&
          data.jobs.some(
            (job) => job.public_id === current,
          )
        ) {
          return current;
        }

        return null;
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to load runner operations.";

      setSnapshot(null);
      setErrorMessage(message);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    setSelectedJobPublicId(null);
    setLogPage(null);
    setLogsError(null);
    void loadSnapshot();
  }, [loadSnapshot, projectId]);

  const activeRunnerCount = useMemo(
    () =>
      snapshot?.runners.filter(
        (runner) => runner.status === "active",
      ).length ?? 0,
    [snapshot],
  );

  const activeJobCount = useMemo(
    () =>
      snapshot?.jobs.filter((job) =>
        ["queued", "claimed", "running"].includes(
          job.status,
        ),
      ).length ?? 0,
    [snapshot],
  );

  const failedJobCount = useMemo(
    () =>
      snapshot?.jobs.filter(
        (job) => job.status === "failed",
      ).length ?? 0,
    [snapshot],
  );

  const selectedJob =
    snapshot?.jobs.find(
      (job) =>
        job.public_id === selectedJobPublicId,
    ) ?? null;

  async function loadLogs(
    job: RunnerOperationsJob,
    afterSequence = 0,
    append = false,
  ) {
    try {
      setIsLogsLoading(true);
      setLogsError(null);

      const page = await getProjectRunnerJobLogs(
        projectId,
        job.public_id,
        {
          afterSequence,
          limit: 100,
        },
      );

      setLogPage((current) => {
        if (!append || current === null) {
          return page;
        }

        return {
          ...page,
          logs: [...current.logs, ...page.logs],
        };
      });
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unable to load runner job logs.";

      if (!append) {
        setLogPage(null);
      }

      setLogsError(message);
    } finally {
      setIsLogsLoading(false);
    }
  }

  function openJobLogs(job: RunnerOperationsJob) {
    setSelectedJobPublicId(job.public_id);
    setLogPage(null);
    void loadLogs(job);
  }

  return (
    <section
      className="runner-operations"
      aria-labelledby="runner-operations-title"
    >
      <div className="panel-header">
        <div>
          <p className="eyebrow">
            Secure execution infrastructure
          </p>
          <h3 id="runner-operations-title">
            Runner operations
          </h3>
          <p className="runner-operations-description">
            Inspect registered runners, execution jobs,
            lifecycle status, and safe structured logs.
          </p>
        </div>

        <button
          className="secondary-button"
          type="button"
          onClick={() => void loadSnapshot()}
          disabled={isLoading}
        >
          {isLoading ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {errorMessage && (
        <div className="state-banner error" role="alert">
          <strong>
            Unable to load runner operations.
          </strong>
          <span>{errorMessage}</span>
        </div>
      )}

      {isLoading && !snapshot && (
        <div
          className="state-banner"
          role="status"
          aria-live="polite"
        >
          Loading runner operations...
        </div>
      )}

      {snapshot && (
        <>
          <div
            className="runner-operations-metrics"
            aria-label="Runner operations summary"
          >
            <article>
              <span>Registered runners</span>
              <strong>{snapshot.runners.length}</strong>
            </article>
            <article>
              <span>Active runners</span>
              <strong>{activeRunnerCount}</strong>
            </article>
            <article>
              <span>Active jobs</span>
              <strong>{activeJobCount}</strong>
            </article>
            <article>
              <span>Failed jobs</span>
              <strong>{failedJobCount}</strong>
            </article>
          </div>

          <div className="runner-operations-grid">
            <article className="runner-operations-section">
              <div className="runner-section-header">
                <div>
                  <p className="eyebrow">Runners</p>
                  <h4>Registered execution agents</h4>
                </div>
                <span className="count-badge">
                  {snapshot.runners.length}
                </span>
              </div>

              {snapshot.runners.length === 0 ? (
                <div className="empty-state">
                  No runners are registered for this
                  project.
                </div>
              ) : (
                <div className="runner-card-list">
                  {snapshot.runners.map((runner) => (
                    <article
                      className="runner-card"
                      key={runner.public_id}
                    >
                      <div className="runner-card-header">
                        <div>
                          <h5>{runner.name}</h5>
                          <span className="runner-public-id">
                            {runner.public_id}
                          </span>
                        </div>

                        <span
                          className={`status-pill ${getStatusTone(
                            runner.status,
                          )}`}
                        >
                          {cleanLabel(runner.status)}
                        </span>
                      </div>

                      <dl className="runner-details">
                        <div>
                          <dt>Version</dt>
                          <dd>
                            {runner.runner_version ??
                              "Not reported"}
                          </dd>
                        </div>
                        <div>
                          <dt>Last heartbeat</dt>
                          <dd>
                            {formatTimestamp(
                              runner.last_seen_at,
                            )}
                          </dd>
                        </div>
                        <div>
                          <dt>Capabilities</dt>
                          <dd>
                            {runner.capabilities.length > 0
                              ? runner.capabilities.join(
                                  ", ",
                                )
                              : "None reported"}
                          </dd>
                        </div>
                      </dl>
                    </article>
                  ))}
                </div>
              )}
            </article>

            <article className="runner-operations-section">
              <div className="runner-section-header">
                <div>
                  <p className="eyebrow">Jobs</p>
                  <h4>Recent execution activity</h4>
                </div>
                <span className="count-badge">
                  {snapshot.jobs.length}
                </span>
              </div>

              {snapshot.jobs.length === 0 ? (
                <div className="empty-state">
                  No runner jobs exist for this project.
                </div>
              ) : (
                <div className="runner-job-list">
                  {snapshot.jobs.map((job) => (
                    <article
                      className={`runner-job-card ${
                        selectedJobPublicId ===
                        job.public_id
                          ? "selected"
                          : ""
                      }`}
                      key={job.public_id}
                    >
                      <div className="runner-job-header">
                        <div>
                          <h5>{job.name}</h5>
                          <span>
                            {cleanLabel(job.job_type)}
                          </span>
                        </div>

                        <span
                          className={`status-pill ${getStatusTone(
                            job.status,
                          )}`}
                        >
                          {cleanLabel(job.status)}
                        </span>
                      </div>

                      <dl className="runner-details">
                        <div>
                          <dt>Runner</dt>
                          <dd>
                            {job.assigned_runner_name ??
                              "Unassigned"}
                          </dd>
                        </div>
                        <div>
                          <dt>Attempts</dt>
                          <dd>
                            {job.attempt_count} /{" "}
                            {job.max_attempts}
                          </dd>
                        </div>
                        <div>
                          <dt>Updated</dt>
                          <dd>
                            {formatTimestamp(
                              job.updated_at,
                            )}
                          </dd>
                        </div>
                      </dl>

                      {job.error_message && (
                        <div className="runner-job-error">
                          <strong>Failure</strong>
                          <span>
                            {job.error_message}
                          </span>
                        </div>
                      )}

                      <button
                        className="text-button"
                        type="button"
                        onClick={() => openJobLogs(job)}
                      >
                        Inspect safe logs
                      </button>
                    </article>
                  ))}
                </div>
              )}
            </article>
          </div>

          {selectedJob && (
            <article
              className="runner-log-panel"
              aria-labelledby="runner-log-title"
            >
              <div className="runner-section-header">
                <div>
                  <p className="eyebrow">
                    Structured execution logs
                  </p>
                  <h4 id="runner-log-title">
                    {selectedJob.name}
                  </h4>
                </div>

                <button
                  className="secondary-button"
                  type="button"
                  onClick={() =>
                    void loadLogs(selectedJob)
                  }
                  disabled={isLogsLoading}
                >
                  {isLogsLoading
                    ? "Loading..."
                    : "Reload logs"}
                </button>
              </div>

              {logsError && (
                <div
                  className="state-banner error"
                  role="alert"
                >
                  <strong>
                    Unable to load runner logs.
                  </strong>
                  <span>{logsError}</span>
                </div>
              )}

              {isLogsLoading && !logPage && (
                <div
                  className="state-banner"
                  role="status"
                  aria-live="polite"
                >
                  Loading safe runner logs...
                </div>
              )}

              {logPage &&
                logPage.logs.length === 0 && (
                  <div className="empty-state">
                    No structured logs exist for this job.
                  </div>
                )}

              {logPage &&
                logPage.logs.length > 0 && (
                  <div className="runner-log-list">
                    {logPage.logs.map((log) => (
                      <article
                        className={`runner-log-entry ${log.level}`}
                        key={log.public_id}
                      >
                        <div className="runner-log-meta">
                          <span>
                            #{log.sequence_number}
                          </span>
                          <span>
                            Attempt{" "}
                            {log.attempt_number}
                          </span>
                          <span>
                            {cleanLabel(
                              log.event_type,
                            )}
                          </span>
                          <span>
                            {formatTimestamp(
                              log.created_at,
                            )}
                          </span>
                        </div>

                        <div className="runner-log-message">
                          <span
                            className={`status-pill ${getStatusTone(
                              log.level === "error"
                                ? "failed"
                                : log.level,
                            )}`}
                          >
                            {log.level}
                          </span>
                          <p>{log.message}</p>
                        </div>
                      </article>
                    ))}
                  </div>
                )}

              {logPage?.has_more &&
                logPage.next_after_sequence !==
                  null && (
                  <button
                    className="secondary-button runner-load-more"
                    type="button"
                    disabled={isLogsLoading}
                    onClick={() =>
                      void loadLogs(
                        selectedJob,
                        logPage.next_after_sequence ??
                          0,
                        true,
                      )
                    }
                  >
                    {isLogsLoading
                      ? "Loading..."
                      : "Load more logs"}
                  </button>
                )}
            </article>
          )}
        </>
      )}
    </section>
  );
}
