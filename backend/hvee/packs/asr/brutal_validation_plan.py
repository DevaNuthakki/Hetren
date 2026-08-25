"""Frozen development plan for the first Hetren ASR brutal validation.

This artifact defines what Brutal Validation v1 must exercise.

It does not execute audio, invoke an ASR provider, create a production
qualification, certify an evaluator, enable a release gate, or authorize
deployment.

The eventual brutal execution must use real audio material, real ASR
execution, real cross-stage evidence, and no verifier stubs.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError


ASR_BRUTAL_VALIDATION_PLAN_SCHEMA_VERSION = 1

ASR_BRUTAL_VALIDATION_PLAN_KEY = (
    "hetren.asr.brutal-validation"
)

ASR_BRUTAL_VALIDATION_PLAN_VERSION = "1.0.0"

ASR_BRUTAL_VALIDATION_BASELINE_BRANCH = (
    "feature/hvee-asr-incident-mode-v1"
)

ASR_BRUTAL_VALIDATION_BASELINE_COMMIT = (
    "ced137523926d941bfcd7e4ad2e66c560e46cd59"
)


_IDENTIFIER = re.compile(
    r"^[a-z0-9][a-z0-9._-]*$"
)

_GIT_COMMIT = re.compile(
    r"^[0-9a-f]{40}$"
)


class ASRBrutalCaseSource(StrEnum):
    """Origin of one required Brutal-v1 case."""

    EXISTING_CORPUS = "existing_corpus"
    REQUIRED_NEW_CASE = "required_new_case"


class ASRBrutalStressFamily(StrEnum):
    """Stress families that Brutal v1 must cover."""

    CONTROL = "control"
    TELEPHONY = "telephony"
    LOSSY_CODEC = "lossy_codec"
    NOISE = "noise"


class ASRBrutalSemanticDimension(StrEnum):
    """Critical semantic dimensions exercised by the campaign."""

    CRITICAL_NUMBER = "critical_number"
    CRITICAL_IDENTIFIER = "critical_identifier"
    CRITICAL_TERMINOLOGY = "critical_terminology"


@dataclass(frozen=True, slots=True)
class ASRBrutalCaseRequirement:
    """One required case or case obligation."""

    case_id: str
    source: ASRBrutalCaseSource
    stress_families: tuple[
        ASRBrutalStressFamily,
        ...,
    ]
    semantic_dimensions: tuple[
        ASRBrutalSemanticDimension,
        ...,
    ]

    def __post_init__(self) -> None:
        _require_identifier(
            name="brutal case id",
            value=self.case_id,
        )

        if not isinstance(
            self.source,
            ASRBrutalCaseSource,
        ):
            raise HveeContractError(
                "brutal case source must be canonical"
            )

        if (
            not isinstance(
                self.stress_families,
                tuple,
            )
            or not self.stress_families
            or any(
                not isinstance(
                    item,
                    ASRBrutalStressFamily,
                )
                for item
                in self.stress_families
            )
            or len(
                set(self.stress_families)
            )
            != len(
                self.stress_families
            )
        ):
            raise HveeContractError(
                "brutal case stress families "
                "must be a unique non-empty tuple"
            )

        if (
            not isinstance(
                self.semantic_dimensions,
                tuple,
            )
            or not self.semantic_dimensions
            or any(
                not isinstance(
                    item,
                    ASRBrutalSemanticDimension,
                )
                for item
                in self.semantic_dimensions
            )
            or len(
                set(self.semantic_dimensions)
            )
            != len(
                self.semantic_dimensions
            )
        ):
            raise HveeContractError(
                "brutal case semantic dimensions "
                "must be a unique non-empty tuple"
            )


@dataclass(frozen=True, slots=True)
class ASRBrutalValidationPlanBundle:
    """Deterministic Brutal-v1 plan artifact."""

    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.payload,
            dict,
        ):
            raise HveeContractError(
                "brutal validation plan payload "
                "must be a JSON object"
            )

        _require_sha256(
            name="brutal validation plan SHA-256",
            value=self.sha256,
        )


def _require_identifier(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value
        or _IDENTIFIER.fullmatch(value) is None
    ):
        raise HveeContractError(
            f"{name} must be a canonical identifier"
        )

    return value


def _require_sha256(
    *,
    name: str,
    value: object,
) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(
            character
            not in "0123456789abcdef"
            for character in value
        )
    ):
        raise HveeContractError(
            f"{name} must be a lowercase SHA-256 digest"
        )

    return value


def _canonical_json(
    value: object,
    *,
    name: str,
) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must be deterministic JSON"
        ) from exc


def _canonical_json_value(
    value: object,
    *,
    name: str,
) -> object:
    return json.loads(
        _canonical_json(
            value,
            name=name,
        )
    )


def calculate_asr_brutal_validation_plan_sha256(
    payload: object,
) -> str:
    canonical = _canonical_json(
        payload,
        name="ASR brutal validation plan",
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def _case(
    case_id: str,
    source: ASRBrutalCaseSource,
    stress_families: tuple[
        ASRBrutalStressFamily,
        ...,
    ],
    semantic_dimensions: tuple[
        ASRBrutalSemanticDimension,
        ...,
    ],
) -> ASRBrutalCaseRequirement:
    return ASRBrutalCaseRequirement(
        case_id=case_id,
        source=source,
        stress_families=stress_families,
        semantic_dimensions=semantic_dimensions,
    )


ASR_BRUTAL_VALIDATION_CASES_V1 = (
    # ---------------------------------------------------------
    # Existing clean controls
    # ---------------------------------------------------------
    _case(
        "clean.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.CONTROL,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),
    _case(
        "clean.identifier-confirmation",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.CONTROL,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),
    _case(
        "clean.number-measurement",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.CONTROL,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
        ),
    ),

    # ---------------------------------------------------------
    # Existing telephony / companded-codec stress
    # ---------------------------------------------------------
    _case(
        "stress.codec-mulaw.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.TELEPHONY,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),
    _case(
        "stress.codec-alaw.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.TELEPHONY,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),
    _case(
        "stress.telephony-bandwidth.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.TELEPHONY,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),

    # ---------------------------------------------------------
    # Existing lossy-codec stress
    # ---------------------------------------------------------
    _case(
        "stress.codec-aac.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.LOSSY_CODEC,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),
    _case(
        "stress.codec-mp3.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.LOSSY_CODEC,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),

    # ---------------------------------------------------------
    # Existing noise stress
    # ---------------------------------------------------------
    _case(
        "stress.noise-moderate.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.NOISE,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),
    _case(
        "stress.noise-severe-usable.multi-number-id",
        ASRBrutalCaseSource.EXISTING_CORPUS,
        (
            ASRBrutalStressFamily.NOISE,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
        ),
    ),

    # ---------------------------------------------------------
    # Required new terminology-bearing controls / stress.
    #
    # These are obligations only. This plan does NOT claim their
    # audio assets already exist.
    # ---------------------------------------------------------
    _case(
        "brutal.terminology.clean",
        ASRBrutalCaseSource.REQUIRED_NEW_CASE,
        (
            ASRBrutalStressFamily.CONTROL,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_TERMINOLOGY,
        ),
    ),
    _case(
        "brutal.terminology.telephony-noise",
        ASRBrutalCaseSource.REQUIRED_NEW_CASE,
        (
            ASRBrutalStressFamily.TELEPHONY,
            ASRBrutalStressFamily.NOISE,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_TERMINOLOGY,
        ),
    ),
    _case(
        "brutal.compound-critical.telephony-noise",
        ASRBrutalCaseSource.REQUIRED_NEW_CASE,
        (
            ASRBrutalStressFamily.TELEPHONY,
            ASRBrutalStressFamily.NOISE,
        ),
        (
            ASRBrutalSemanticDimension.CRITICAL_NUMBER,
            ASRBrutalSemanticDimension.CRITICAL_IDENTIFIER,
            ASRBrutalSemanticDimension.CRITICAL_TERMINOLOGY,
        ),
    ),
)


ASR_BRUTAL_VALIDATION_WORKFLOW_V1 = (
    "adversarial_audio_execution",
    "critical_fidelity_evaluation",
    "counterexample_evidence",
    "adaptive_scenario_search",
    "observed_boundary",
    "minimal_counterexample_reduction",
    "neighborhood_generation",
    "counterexample_contract_proposal",
    "incident_mode",
    "governance_assurance",
)


def _require_case_set() -> None:
    case_ids = tuple(
        case.case_id
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
    )

    if len(case_ids) != len(set(case_ids)):
        raise HveeContractError(
            "Brutal-v1 case ids must be unique"
        )

    semantic_dimensions = {
        dimension
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
        for dimension
        in case.semantic_dimensions
    }

    if semantic_dimensions != set(
        ASRBrutalSemanticDimension
    ):
        raise HveeContractError(
            "Brutal-v1 must cover every critical "
            "semantic dimension"
        )

    stress_families = {
        family
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
        for family
        in case.stress_families
    }

    if stress_families != set(
        ASRBrutalStressFamily
    ):
        raise HveeContractError(
            "Brutal-v1 must cover every required "
            "stress family"
        )


def _case_snapshot(
    case: ASRBrutalCaseRequirement,
) -> dict[str, object]:
    return {
        "case_id": case.case_id,
        "source": case.source.value,
        "stress_families": [
            family.value
            for family
            in case.stress_families
        ],
        "semantic_dimensions": [
            dimension.value
            for dimension
            in case.semantic_dimensions
        ],
    }


def build_asr_brutal_validation_plan_v1(
) -> ASRBrutalValidationPlanBundle:
    """Build the frozen Brutal-v1 development plan."""

    _require_case_set()

    if (
        _GIT_COMMIT.fullmatch(
            ASR_BRUTAL_VALIDATION_BASELINE_COMMIT
        )
        is None
    ):
        raise HveeContractError(
            "Brutal-v1 baseline commit is invalid"
        )

    existing_case_count = sum(
        case.source
        is ASRBrutalCaseSource.EXISTING_CORPUS
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
    )

    required_new_case_count = sum(
        case.source
        is ASRBrutalCaseSource.REQUIRED_NEW_CASE
        for case
        in ASR_BRUTAL_VALIDATION_CASES_V1
    )

    payload: dict[str, object] = {
        "schema_version": (
            ASR_BRUTAL_VALIDATION_PLAN_SCHEMA_VERSION
        ),
        "type": "asr_brutal_validation_plan",
        "plan": {
            "key": ASR_BRUTAL_VALIDATION_PLAN_KEY,
            "version": (
                ASR_BRUTAL_VALIDATION_PLAN_VERSION
            ),
            "purpose": (
                "development_reliability_validation"
            ),
        },
        "baseline": {
            "branch": (
                ASR_BRUTAL_VALIDATION_BASELINE_BRANCH
            ),
            "git_commit": (
                ASR_BRUTAL_VALIDATION_BASELINE_COMMIT
            ),
        },
        "case_requirements": [
            _case_snapshot(case)
            for case
            in ASR_BRUTAL_VALIDATION_CASES_V1
        ],
        "coverage": {
            "required_case_count": len(
                ASR_BRUTAL_VALIDATION_CASES_V1
            ),
            "existing_corpus_case_count": (
                existing_case_count
            ),
            "required_new_case_count": (
                required_new_case_count
            ),
            "required_stress_families": [
                family.value
                for family
                in ASRBrutalStressFamily
            ],
            "required_semantic_dimensions": [
                dimension.value
                for dimension
                in ASRBrutalSemanticDimension
            ],
            "clean_control_required": True,
            "telephony_required": True,
            "lossy_codec_required": True,
            "noise_required": True,
            "critical_number_required": True,
            "critical_identifier_required": True,
            "critical_terminology_required": True,
        },
        "workflow": {
            "required_stages": list(
                ASR_BRUTAL_VALIDATION_WORKFLOW_V1
            ),
            "counterexample_contract_proposal_required": True,
            "contract_promotion_execution_required": False,
            "incident_mode_required": True,
            "governance_assurance_required": True,
        },
        "execution_requirements": {
            "real_audio_material_required": True,
            "real_asr_provider_execution_required": True,
            "real_cross_stage_evidence_required": True,
            "real_incident_chain_required": True,
            "verifier_stubs_allowed": False,
            "synthetic_only_campaign_acceptable": False,
            "fix_serious_defects_and_rerun": True,
        },
        "execution_boundary": {
            "brutal_validation_execution_started": False,
            "audio_executed": False,
            "model_execution_performed": False,
            "cross_stage_chain_executed": False,
            "incident_chain_executed": False,
            "governance_review_executed": False,
            "brutal_validation_completed": False,
        },
        "authority_boundary": {
            "development_evidence_only": True,
            "production_certification": False,
            "contract_promoted": False,
            "blocking_release_gate_enabled": False,
            "release_authority_granted": False,
            "qualification_authority": False,
        },
    }

    canonical = _canonical_json_value(
        payload,
        name="ASR brutal validation plan",
    )

    if not isinstance(
        canonical,
        dict,
    ):
        raise HveeContractError(
            "ASR brutal validation plan "
            "must be a JSON object"
        )

    return ASRBrutalValidationPlanBundle(
        payload=canonical,
        sha256=(
            calculate_asr_brutal_validation_plan_sha256(
                canonical
            )
        ),
    )


def verify_asr_brutal_validation_plan_v1(
    *,
    payload: object,
    expected_sha256: object,
) -> bool:
    try:
        expected = _require_sha256(
            name="expected Brutal-v1 plan SHA-256",
            value=expected_sha256,
        )

        if not isinstance(
            payload,
            dict,
        ):
            return False

        if (
            calculate_asr_brutal_validation_plan_sha256(
                payload
            )
            != expected
        ):
            return False

        rebuilt = (
            build_asr_brutal_validation_plan_v1()
        )

        return (
            payload == rebuilt.payload
            and expected == rebuilt.sha256
        )

    except (
        HveeContractError,
        TypeError,
        ValueError,
    ):
        return False


__all__ = [
    "ASR_BRUTAL_VALIDATION_BASELINE_BRANCH",
    "ASR_BRUTAL_VALIDATION_BASELINE_COMMIT",
    "ASR_BRUTAL_VALIDATION_CASES_V1",
    "ASR_BRUTAL_VALIDATION_PLAN_KEY",
    "ASR_BRUTAL_VALIDATION_PLAN_SCHEMA_VERSION",
    "ASR_BRUTAL_VALIDATION_PLAN_VERSION",
    "ASR_BRUTAL_VALIDATION_WORKFLOW_V1",
    "ASRBrutalCaseRequirement",
    "ASRBrutalCaseSource",
    "ASRBrutalSemanticDimension",
    "ASRBrutalStressFamily",
    "ASRBrutalValidationPlanBundle",
    "build_asr_brutal_validation_plan_v1",
    "calculate_asr_brutal_validation_plan_sha256",
    "verify_asr_brutal_validation_plan_v1",
]
