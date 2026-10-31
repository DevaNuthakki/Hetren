"""Hetren diagnosis and bounded recovery for the support workflow.

Works only from diagnosis inputs (run-record evidence payloads) and probe
records. Never imports the evaluator or the verifier.
"""

from .diagnosis import (
    Diagnosis,
    DiagnosisOutcome,
    MappingFinding,
    diagnose,
)
from .recovery import (
    ApplicationStatus,
    CORRECTION_TOOL,
    CandidateStatus,
    CorrectionAction,
    DIAGNOSTIC_TOOL_NAMES,
    FrozenOutcome,
    HetrenOutcome,
    RecoveryApplication,
    RecoveryCandidate,
    apply_candidate,
    freeze_outcome,
    propose_candidate,
    recover,
    rollback_application,
    run_probes,
)
from .sufficiency import (
    EvidenceAssessment,
    EvidenceStatus,
    assess_evidence,
)


__all__ = [
    "ApplicationStatus",
    "CORRECTION_TOOL",
    "CandidateStatus",
    "CorrectionAction",
    "DIAGNOSTIC_TOOL_NAMES",
    "Diagnosis",
    "DiagnosisOutcome",
    "EvidenceAssessment",
    "EvidenceStatus",
    "FrozenOutcome",
    "HetrenOutcome",
    "MappingFinding",
    "RecoveryApplication",
    "RecoveryCandidate",
    "apply_candidate",
    "assess_evidence",
    "diagnose",
    "freeze_outcome",
    "propose_candidate",
    "recover",
    "rollback_application",
    "run_probes",
]
