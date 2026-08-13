import type {
  ASRSemanticEvidence,
  ASRSemanticEvidenceFamily,
  ASRSemanticEvidenceObservation,
} from "./api";

type StatusTone = "good" | "warning" | "danger" | "neutral";

type FamilyDefinition = {
  key:
    | "critical_number"
    | "critical_identifier"
    | "critical_terminology";
  title: string;
  description: string;
  countMetrics: Array<{
    segment: string;
    label: string;
  }>;
};

const FAMILY_DEFINITIONS: FamilyDefinition[] = [
  {
    key: "critical_number",
    title: "Critical Number",
    description:
      "Checks whether important numeric values were preserved in the ASR output.",
    countMetrics: [
      {
        segment: "substitution-count",
        label: "Substitutions",
      },
      {
        segment: "omission-count",
        label: "Omissions",
      },
      {
        segment: "insertion-count",
        label: "Insertions",
      },
      {
        segment: "ambiguity-count",
        label: "Ambiguities",
      },
    ],
  },
  {
    key: "critical_identifier",
    title: "Critical Identifier",
    description:
      "Checks identifiers such as codes, IDs, and structured references.",
    countMetrics: [
      {
        segment: "substitution-count",
        label: "Substitutions",
      },
      {
        segment: "omission-count",
        label: "Omissions",
      },
      {
        segment: "insertion-count",
        label: "Insertions",
      },
      {
        segment: "ordering-change-count",
        label: "Order changes",
      },
      {
        segment: "ambiguity-count",
        label: "Ambiguities",
      },
    ],
  },
  {
    key: "critical_terminology",
    title: "Critical Terminology",
    description:
      "Checks project-configured terminology against the vocabulary pinned to this run.",
    countMetrics: [
      {
        segment: "substitution-count",
        label: "Substitutions",
      },
      {
        segment: "omission-count",
        label: "Omissions",
      },
      {
        segment: "insertion-count",
        label: "Insertions",
      },
      {
        segment: "ordering-change-count",
        label: "Order changes",
      },
    ],
  },
];

function findObservation(
  family: ASRSemanticEvidenceFamily,
  metricSegment: string,
) {
  return family.observations.find((observation) =>
    observation.metric_key.includes(`.${metricSegment}.`),
  );
}

function booleanValue(
  observation: ASRSemanticEvidenceObservation | undefined,
) {
  return observation?.status === "success" &&
    typeof observation.value === "boolean"
    ? observation.value
    : null;
}

function stringValue(
  observation: ASRSemanticEvidenceObservation | undefined,
) {
  return observation?.status === "success" &&
    typeof observation.value === "string"
    ? observation.value
    : null;
}

function integerValue(
  observation: ASRSemanticEvidenceObservation | undefined,
) {
  return observation?.status === "success" &&
    typeof observation.value === "number" &&
    Number.isInteger(observation.value)
    ? observation.value
    : null;
}

function observationStatusTone(
  observation: ASRSemanticEvidenceObservation,
): StatusTone {
  switch (observation.status) {
    case "success":
      return "good";
    case "failed":
    case "invalid":
      return "danger";
    case "timed_out":
    case "cancelled":
      return "warning";
    case "abstained":
    case "unsupported":
      return "neutral";
  }
}

function cleanEvidenceLabel(value: string) {
  return value
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function summarizeFamily(
  family: ASRSemanticEvidenceFamily,
): {
  label: string;
  tone: StatusTone;
} {
  if (family.status === "not_configured") {
    return {
      label: "Not configured",
      tone: "neutral",
    };
  }

  if (family.status === "legacy_unavailable") {
    return {
      label: "Legacy unavailable",
      tone: "neutral",
    };
  }

  const applicable = booleanValue(
    findObservation(family, "applicable"),
  );
  const preserved = booleanValue(
    findObservation(family, "preserved"),
  );
  const outcome = stringValue(
    findObservation(family, "outcome"),
  );

  if (applicable === false) {
    return {
      label: "Not applicable",
      tone: "neutral",
    };
  }

  if (preserved === true) {
    return {
      label: outcome
        ? cleanEvidenceLabel(outcome)
        : "Preserved",
      tone: "good",
    };
  }

  if (preserved === false) {
    return {
      label: outcome
        ? cleanEvidenceLabel(outcome)
        : "Not preserved",
      tone: "danger",
    };
  }

  return {
    label: outcome
      ? cleanEvidenceLabel(outcome)
      : "Evidence available",
    tone: "warning",
  };
}

function unavailableMessage(
  family: ASRSemanticEvidenceFamily,
) {
  if (family.status === "not_configured") {
    return (
      "No Critical Terminology vocabulary was " +
      "configured for this run."
    );
  }

  if (family.status === "legacy_unavailable") {
    return (
      "This result predates Critical Terminology " +
      "evidence."
    );
  }

  return null;
}

function formatEvidenceValue(value: unknown) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }

  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "Unable to display this evidence value.";
  }
}

function renderFamily(
  definition: FamilyDefinition,
  family: ASRSemanticEvidenceFamily,
) {
  const summary = summarizeFamily(family);
  const unavailable = unavailableMessage(family);

  const vocabularySha =
    definition.key === "critical_terminology"
      ? stringValue(
          findObservation(
            family,
            "vocabulary-sha256",
          ),
        )
      : null;

  return (
    <article
      className="semantic-evidence-card"
      key={definition.key}
    >
      <div className="semantic-evidence-card-header">
        <div>
          <h4>{definition.title}</h4>
          <p>{definition.description}</p>
        </div>

        <span className={`status-pill ${summary.tone}`}>
          {summary.label}
        </span>
      </div>

      {unavailable ? (
        <div className="semantic-evidence-unavailable">
          {unavailable}
        </div>
      ) : (
        <>
          <dl
            className="semantic-evidence-counts"
            aria-label={`${definition.title} evidence counts`}
          >
            {definition.countMetrics.map(
              ({ segment, label }) => {
                const value = integerValue(
                  findObservation(
                    family,
                    segment,
                  ),
                );

                return (
                  <div key={segment}>
                    <dt>{label}</dt>
                    <dd>{value ?? "—"}</dd>
                  </div>
                );
              },
            )}
          </dl>

          {vocabularySha && (
            <p className="semantic-evidence-vocabulary">
              Vocabulary identity verified ·{" "}
              <code>
                {vocabularySha.slice(0, 12)}…
              </code>
            </p>
          )}

          <details className="semantic-evidence-details">
            <summary>Evidence details</summary>

            <div className="semantic-observation-list">
              {family.observations.map(
                (observation) => (
                  <article
                    className="semantic-observation"
                    key={`${observation.metric_key}:${observation.metric_version}`}
                  >
                    <div className="semantic-observation-header">
                      <strong>
                        {observation.metric_key}
                      </strong>

                      <span
                        className={`status-pill ${observationStatusTone(
                          observation,
                        )}`}
                      >
                        {cleanEvidenceLabel(
                          observation.status,
                        )}
                      </span>
                    </div>

                    <span className="semantic-observation-identity">
                      Metric {observation.metric_version}
                      {" · "}
                      {observation.evaluator_key}
                      {" · "}
                      Evaluator{" "}
                      {observation.evaluator_version}
                    </span>

                    <pre className="semantic-observation-value">
                      {formatEvidenceValue(
                        observation.value,
                      )}
                    </pre>

                    {observation.status_detail && (
                      <p className="semantic-observation-detail">
                        {observation.status_detail}
                      </p>
                    )}
                  </article>
                ),
              )}
            </div>
          </details>
        </>
      )}
    </article>
  );
}

export function SemanticEvidencePanel({
  evidence,
}: {
  evidence: ASRSemanticEvidence;
}) {
  return (
    <section
      className="semantic-evidence-panel"
      aria-label="ASR semantic fidelity evidence"
    >
      <div className="semantic-evidence-panel-header">
        <div>
          <p className="eyebrow">HVEE evidence</p>
          <h3>Semantic fidelity</h3>
          <p>
            Persisted result evidence from the backend.
            These signals support engineering review and do
            not independently change release authority.
          </p>
        </div>

        <span className="status-pill neutral">
          Result #{evidence.result_id}
        </span>
      </div>

      <div className="semantic-evidence-grid">
        {FAMILY_DEFINITIONS.map((definition) =>
          renderFamily(
            definition,
            evidence[definition.key],
          ),
        )}
      </div>
    </section>
  );
}
