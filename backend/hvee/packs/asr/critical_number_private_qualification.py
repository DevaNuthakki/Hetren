"""Private qualification-campaign contracts for Critical Number Fidelity v1.

This module seals a campaign protocol before private evaluator outputs exist,
binds that protocol to the existing private-holdout plan, and records complete
independent adjudication after the signed plan -> blind run -> disclosure
evidence chain has been verified.

The numerical acceptance criteria are caller-owned campaign inputs.  HVEE
commits them exactly but deliberately does not define an official threshold,
calculate a qualification verdict, issue certification, qualify the evaluator
for production, or enable release enforcement.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum

from hvee.core.contracts import HveeContractError
from hvee.packs.asr.critical_number_assurance import (
    CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
    CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
    ASRCriticalNumberAssuranceStatus,
    verify_critical_number_assurance_profile_v1,
)
from hvee.packs.asr.critical_number_fidelity import (
    CRITICAL_NUMBER_FIDELITY_EVALUATOR,
    EN_US_CRITICAL_NUMBER_PROFILE,
)
from hvee.packs.asr.critical_number_private_evidence import (
    ASRCriticalNumberPrivateEvidenceArtifactType,
    ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verify_critical_number_private_evidence_disclosure_manifest,
)
from hvee.packs.asr.critical_number_private_holdout import (
    ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    ASRCriticalNumberPrivateHoldoutExecutionStatus,
    ASRCriticalNumberPrivateHoldoutPlanBundle,
    ASRCriticalNumberPrivateHoldoutPlanDefinition,
    verify_critical_number_private_holdout_blind_run,
    verify_critical_number_private_holdout_plan,
)


CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CAMPAIGN_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ADJUDICATION_SCHEMA_VERSION = 1
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY = (
    "hetren.asr.critical-number-private-qualification.en-us"
)
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION = "1.0.0"
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE = 1_000_000

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_EXPECTED_EVALUATOR_IDENTITY = (
    "hetren.asr.critical-number-fidelity.en-us",
    "1.0.0",
    "asr",
)
_EXPECTED_PROFILE_IDENTITY = (
    "hetren.asr.critical-number-profile.en-us",
    "1.0.0",
    "en",
    "en-US",
)


class ASRCriticalNumberPrivateQualificationStratum(StrEnum):
    """Preregistered private oracle-mutation and control strata."""

    SUBSTITUTION_MUTATION = "substitution_mutation"
    OMISSION_MUTATION = "omission_mutation"
    INSERTION_MUTATION = "insertion_mutation"
    AMBIGUITY_CHALLENGE = "ambiguity_challenge"
    EQUIVALENT_RENDERING_CONTROL = "equivalent_rendering_control"
    NO_NUMBER_APPLICABILITY_CONTROL = "no_number_applicability_control"
    UNSUPPORTED_FORMAT_CONTROL = "unsupported_format_control"


CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1 = (
    ASRCriticalNumberPrivateQualificationStratum.SUBSTITUTION_MUTATION,
    ASRCriticalNumberPrivateQualificationStratum.OMISSION_MUTATION,
    ASRCriticalNumberPrivateQualificationStratum.INSERTION_MUTATION,
    ASRCriticalNumberPrivateQualificationStratum.AMBIGUITY_CHALLENGE,
)
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1 = (
    ASRCriticalNumberPrivateQualificationStratum.EQUIVALENT_RENDERING_CONTROL,
    ASRCriticalNumberPrivateQualificationStratum.NO_NUMBER_APPLICABILITY_CONTROL,
    ASRCriticalNumberPrivateQualificationStratum.UNSUPPORTED_FORMAT_CONTROL,
)
CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1 = tuple(
    sorted(
        (
            *CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1,
            *CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1,
        ),
        key=lambda value: value.value,
    )
)


class ASRCriticalNumberPrivateQualificationAdjudicatorRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ARBITER = "arbiter"


class ASRCriticalNumberPrivateQualificationAdjudicationOutcome(StrEnum):
    DETECTED = "detected"
    MISSED = "missed"
    TRUE_NEGATIVE = "true_negative"
    FALSE_POSITIVE = "false_positive"
    ABSTAINED = "abstained"
    UNRESOLVED = "unresolved"
    EXECUTION_FAILURE = "execution_failure"


_ORACLE_OUTCOMES = frozenset(
    {
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.DETECTED,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.MISSED,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.ABSTAINED,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.UNRESOLVED,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.EXECUTION_FAILURE,
    }
)
_CONTROL_OUTCOMES = frozenset(
    {
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.TRUE_NEGATIVE,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.FALSE_POSITIVE,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.ABSTAINED,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.UNRESOLVED,
        ASRCriticalNumberPrivateQualificationAdjudicationOutcome.EXECUTION_FAILURE,
    }
)


def _canonicalize_json_value(value: object, *, name: str) -> object:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        return json.loads(serialized)
    except (TypeError, ValueError) as exc:
        raise HveeContractError(
            f"{name} must contain valid deterministic JSON"
        ) from exc


def _canonical_json(value: object, *, name: str) -> str:
    canonical = _canonicalize_json_value(value, name=name)
    return json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def calculate_critical_number_private_qualification_sha256(
    payload: object,
) -> str:
    """Hash canonical private-qualification evidence."""

    canonical = _canonical_json(
        payload,
        name="critical-number private-qualification payload",
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _require_sha256(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HveeContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _require_identifier(*, name: str, value: object) -> str:
    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise HveeContractError(f"{name} must be a canonical lowercase identifier")
    return value


def _require_version(*, name: str, value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 100
    ):
        raise HveeContractError(f"{name} must be a non-empty, trimmed version")
    return value


def _require_positive_integer(*, name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise HveeContractError(f"{name} must be a positive integer")
    return value


def _require_rate(*, name: str, value: object) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
    ):
        raise HveeContractError(
            f"{name} must be an integer from 0 to "
            f"{CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE}"
        )
    return value


def _require_v1_bindings() -> str:
    assurance = verify_critical_number_assurance_profile_v1()
    evaluator_identity = (
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
        CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
    )
    if evaluator_identity != _EXPECTED_EVALUATOR_IDENTITY:
        raise HveeContractError("private qualification evaluator identity changed")
    profile_identity = (
        EN_US_CRITICAL_NUMBER_PROFILE.key,
        EN_US_CRITICAL_NUMBER_PROFILE.version,
        EN_US_CRITICAL_NUMBER_PROFILE.language,
        EN_US_CRITICAL_NUMBER_PROFILE.locale,
    )
    if profile_identity != _EXPECTED_PROFILE_IDENTITY:
        raise HveeContractError("private qualification profile identity changed")
    if assurance.sha256 != CRITICAL_NUMBER_ASSURANCE_EVIDENCE_SHA256_V1:
        raise HveeContractError("private qualification assurance binding changed")
    profile = assurance.payload.get("assurance_profile")
    if not isinstance(profile, dict) or profile.get("status") != (
        ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value
    ):
        raise HveeContractError(
            "private qualification requires the experimental assurance profile"
        )
    return assurance.sha256


def _bindings(assurance_sha256: str) -> dict[str, object]:
    return {
        "evaluator": {
            "key": CRITICAL_NUMBER_FIDELITY_EVALUATOR.key,
            "version": CRITICAL_NUMBER_FIDELITY_EVALUATOR.version,
            "evaluation_type": CRITICAL_NUMBER_FIDELITY_EVALUATOR.evaluation_type,
        },
        "evaluation_profile": {
            "key": EN_US_CRITICAL_NUMBER_PROFILE.key,
            "version": EN_US_CRITICAL_NUMBER_PROFILE.version,
            "language": EN_US_CRITICAL_NUMBER_PROFILE.language,
            "locale": EN_US_CRITICAL_NUMBER_PROFILE.locale,
        },
        "assurance_profile": {
            "key": CRITICAL_NUMBER_ASSURANCE_PROFILE_KEY,
            "version": CRITICAL_NUMBER_ASSURANCE_PROFILE_VERSION,
            "status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
            "sha256": assurance_sha256,
        },
    }


def _qualification_boundary() -> dict[str, object]:
    return {
        "campaign_mechanics_verified": True,
        "statistical_qualification_assessed": False,
        "evaluator_status": ASRCriticalNumberAssuranceStatus.EXPERIMENTAL.value,
        "certification_issued": False,
        "production_qualified": False,
        "release_enforcement_eligible": False,
        "official_release_verdict_modified": False,
    }


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationStratumDefinition:
    stratum: ASRCriticalNumberPrivateQualificationStratum
    construction_protocol_sha256: str
    population_manifest_sha256: str
    selection_manifest_sha256: str
    expected_behavior_sha256: str
    case_tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(
            self.stratum,
            ASRCriticalNumberPrivateQualificationStratum,
        ):
            raise HveeContractError(
                "private qualification requires a versioned stratum"
            )
        for name, value in (
            ("construction protocol", self.construction_protocol_sha256),
            ("population manifest", self.population_manifest_sha256),
            ("selection manifest", self.selection_manifest_sha256),
            ("expected behavior", self.expected_behavior_sha256),
        ):
            _require_sha256(name=f"private qualification {name}", value=value)
        if (
            not isinstance(self.case_tokens, tuple)
            or not self.case_tokens
            or tuple(sorted(set(self.case_tokens))) != self.case_tokens
        ):
            raise HveeContractError(
                "private qualification stratum case tokens must be non-empty, "
                "unique, and sorted"
            )
        for token in self.case_tokens:
            _require_sha256(name="private qualification case token", value=token)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationStatisticalCriteria:
    method_key: str
    method_version: str
    method_manifest_sha256: str
    multiplicity_control_key: str
    multiplicity_control_version: str
    random_seed_commitment_sha256: str
    confidence_level_ppm: int
    minimum_total_usable_cases: int
    minimum_usable_cases_per_stratum: int
    minimum_oracle_detection_lower_bound_ppm: int
    maximum_control_false_positive_upper_bound_ppm: int
    maximum_abstention_upper_bound_ppm: int
    maximum_unresolved_fraction_ppm: int
    maximum_execution_failure_fraction_ppm: int

    def __post_init__(self) -> None:
        _require_identifier(name="private statistical method key", value=self.method_key)
        _require_version(
            name="private statistical method version",
            value=self.method_version,
        )
        _require_sha256(
            name="private statistical method manifest",
            value=self.method_manifest_sha256,
        )
        _require_identifier(
            name="private multiplicity-control key",
            value=self.multiplicity_control_key,
        )
        _require_version(
            name="private multiplicity-control version",
            value=self.multiplicity_control_version,
        )
        _require_sha256(
            name="private statistical random-seed commitment",
            value=self.random_seed_commitment_sha256,
        )
        _require_rate(
            name="private statistical confidence level",
            value=self.confidence_level_ppm,
        )
        if not (
            CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE // 2
            < self.confidence_level_ppm
            < CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE
        ):
            raise HveeContractError(
                "private statistical confidence level must be greater than "
                "0.5 and less than 1.0"
            )
        _require_positive_integer(
            name="private minimum total usable cases",
            value=self.minimum_total_usable_cases,
        )
        _require_positive_integer(
            name="private minimum usable cases per stratum",
            value=self.minimum_usable_cases_per_stratum,
        )
        for name, value in (
            (
                "minimum oracle-detection lower bound",
                self.minimum_oracle_detection_lower_bound_ppm,
            ),
            (
                "maximum control false-positive upper bound",
                self.maximum_control_false_positive_upper_bound_ppm,
            ),
            (
                "maximum abstention upper bound",
                self.maximum_abstention_upper_bound_ppm,
            ),
            (
                "maximum unresolved fraction",
                self.maximum_unresolved_fraction_ppm,
            ),
            (
                "maximum execution-failure fraction",
                self.maximum_execution_failure_fraction_ppm,
            ),
        ):
            _require_rate(name=f"private {name}", value=value)


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationCampaignDefinition:
    campaign_id: str
    campaign_version: str
    run_id: str
    holdout_set_key: str
    holdout_set_version: str
    protocol_owner_key_id: str
    strata: tuple[ASRCriticalNumberPrivateQualificationStratumDefinition, ...]
    statistical_criteria: (
        ASRCriticalNumberPrivateQualificationStatisticalCriteria
    )
    adjudication_protocol_sha256: str
    adjudicator_roster_sha256: str
    conflict_of_interest_policy_sha256: str
    data_handling_policy_sha256: str
    supersedes_protocol_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_identifier(
            name="private qualification campaign id",
            value=self.campaign_id,
        )
        _require_version(
            name="private qualification campaign version",
            value=self.campaign_version,
        )
        _require_identifier(name="private qualification run id", value=self.run_id)
        _require_identifier(
            name="private qualification holdout-set key",
            value=self.holdout_set_key,
        )
        _require_version(
            name="private qualification holdout-set version",
            value=self.holdout_set_version,
        )
        _require_identifier(
            name="private qualification protocol-owner key id",
            value=self.protocol_owner_key_id,
        )
        if self.supersedes_protocol_sha256 is not None:
            _require_sha256(
                name="superseded private qualification protocol",
                value=self.supersedes_protocol_sha256,
            )
        for name, value in (
            ("adjudication protocol", self.adjudication_protocol_sha256),
            ("adjudicator roster", self.adjudicator_roster_sha256),
            ("conflict-of-interest policy", self.conflict_of_interest_policy_sha256),
            ("data-handling policy", self.data_handling_policy_sha256),
        ):
            _require_sha256(name=f"private qualification {name}", value=value)
        if not isinstance(
            self.statistical_criteria,
            ASRCriticalNumberPrivateQualificationStatisticalCriteria,
        ):
            raise HveeContractError(
                "private qualification requires frozen statistical criteria"
            )
        if (
            not isinstance(self.strata, tuple)
            or not all(
                isinstance(
                    stratum,
                    ASRCriticalNumberPrivateQualificationStratumDefinition,
                )
                for stratum in self.strata
            )
        ):
            raise HveeContractError(
                "private qualification requires stratum definitions"
            )
        expected = CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
        actual = tuple(stratum.stratum for stratum in self.strata)
        if actual != expected:
            raise HveeContractError(
                "private qualification strata must contain the exact sorted v1 set"
            )
        tokens = tuple(
            token for stratum in self.strata for token in stratum.case_tokens
        )
        if len(tokens) != len(set(tokens)):
            raise HveeContractError(
                "private qualification case tokens cannot cross strata"
            )
        criteria = self.statistical_criteria
        if criteria.minimum_total_usable_cases > len(tokens):
            raise HveeContractError(
                "private qualification minimum usable cases exceeds selection"
            )
        if any(
            criteria.minimum_usable_cases_per_stratum > len(stratum.case_tokens)
            for stratum in self.strata
        ):
            raise HveeContractError(
                "private qualification per-stratum minimum exceeds selection"
            )
        if criteria.minimum_total_usable_cases < (
            criteria.minimum_usable_cases_per_stratum * len(self.strata)
        ):
            raise HveeContractError(
                "private qualification total usable minimum cannot be lower "
                "than its combined per-stratum minima"
            )

    @property
    def case_tokens(self) -> tuple[str, ...]:
        return tuple(
            sorted(token for stratum in self.strata for token in stratum.case_tokens)
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationProtocolBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private-qualification protocol",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError("private qualification protocol must be an object")
        _require_sha256(
            name="private qualification protocol SHA-256",
            value=self.sha256,
        )
        if calculate_critical_number_private_qualification_sha256(canonical) != (
            self.sha256
        ):
            raise HveeContractError(
                "private qualification protocol SHA-256 does not match its payload"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationCampaignBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private-qualification campaign",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError("private qualification campaign must be an object")
        _require_sha256(
            name="private qualification campaign SHA-256",
            value=self.sha256,
        )
        if calculate_critical_number_private_qualification_sha256(canonical) != (
            self.sha256
        ):
            raise HveeContractError(
                "private qualification campaign SHA-256 does not match its payload"
            )


def _stratum_purpose(
    stratum: ASRCriticalNumberPrivateQualificationStratum,
) -> str:
    if stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1:
        return "oracle_mutation"
    if stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CONTROL_STRATA_V1:
        return "control"
    raise HveeContractError("unsupported private qualification stratum")


def _stratum_snapshot(
    definition: ASRCriticalNumberPrivateQualificationStratumDefinition,
) -> dict[str, object]:
    return {
        "key": definition.stratum.value,
        "purpose": _stratum_purpose(definition.stratum),
        "construction_protocol_sha256": definition.construction_protocol_sha256,
        "population_manifest_sha256": definition.population_manifest_sha256,
        "selection_manifest_sha256": definition.selection_manifest_sha256,
        "expected_behavior_sha256": definition.expected_behavior_sha256,
        "selected_case_count": len(definition.case_tokens),
        "case_tokens": list(definition.case_tokens),
    }


def _criteria_snapshot(
    criteria: ASRCriticalNumberPrivateQualificationStatisticalCriteria,
) -> dict[str, object]:
    return {
        "rate_scale": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_RATE_SCALE,
        "method": {
            "key": criteria.method_key,
            "version": criteria.method_version,
            "manifest_sha256": criteria.method_manifest_sha256,
        },
        "multiplicity_control": {
            "key": criteria.multiplicity_control_key,
            "version": criteria.multiplicity_control_version,
        },
        "random_seed_commitment_sha256": (
            criteria.random_seed_commitment_sha256
        ),
        "confidence_level_ppm": criteria.confidence_level_ppm,
        "minimum_total_usable_cases": criteria.minimum_total_usable_cases,
        "minimum_usable_cases_per_stratum": (
            criteria.minimum_usable_cases_per_stratum
        ),
        "minimum_oracle_detection_lower_bound_ppm": (
            criteria.minimum_oracle_detection_lower_bound_ppm
        ),
        "maximum_control_false_positive_upper_bound_ppm": (
            criteria.maximum_control_false_positive_upper_bound_ppm
        ),
        "maximum_abstention_upper_bound_ppm": (
            criteria.maximum_abstention_upper_bound_ppm
        ),
        "maximum_unresolved_fraction_ppm": (
            criteria.maximum_unresolved_fraction_ppm
        ),
        "maximum_execution_failure_fraction_ppm": (
            criteria.maximum_execution_failure_fraction_ppm
        ),
    }


def build_critical_number_private_qualification_protocol(
    definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
) -> ASRCriticalNumberPrivateQualificationProtocolBundle:
    """Seal campaign composition and criteria before evaluator outputs exist."""

    if not isinstance(
        definition,
        ASRCriticalNumberPrivateQualificationCampaignDefinition,
    ):
        raise HveeContractError(
            "private qualification requires a campaign definition"
        )
    assurance_sha256 = _require_v1_bindings()
    payload = {
        "schema_version": (
            CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_SCHEMA_VERSION
        ),
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION,
            "artifact": "preregistered_private_qualification_protocol",
        },
        "bindings": _bindings(assurance_sha256),
        "preregistration": {
            "campaign_id": definition.campaign_id,
            "campaign_version": definition.campaign_version,
            "run_id": definition.run_id,
            "supersedes_protocol_sha256": (
                definition.supersedes_protocol_sha256
            ),
            "protocol_owner_key_id": definition.protocol_owner_key_id,
            "holdout_set": {
                "key": definition.holdout_set_key,
                "version": definition.holdout_set_version,
            },
            "selected_case_count": len(definition.case_tokens),
            "strata": [
                _stratum_snapshot(stratum) for stratum in definition.strata
            ],
            "statistical_acceptance_criteria": _criteria_snapshot(
                definition.statistical_criteria
            ),
            "independent_adjudication": {
                "adjudication_protocol_sha256": (
                    definition.adjudication_protocol_sha256
                ),
                "adjudicator_roster_sha256": (
                    definition.adjudicator_roster_sha256
                ),
                "conflict_of_interest_policy_sha256": (
                    definition.conflict_of_interest_policy_sha256
                ),
                "data_handling_policy_sha256": (
                    definition.data_handling_policy_sha256
                ),
                "dual_independent_review_required": True,
                "disagreement_arbitration_required": True,
            },
            "locks": {
                "sealed_before_evaluator_outputs": True,
                "composition_change_after_seal_allowed": False,
                "criteria_change_after_seal_allowed": False,
                "adjudication_protocol_change_after_seal_allowed": False,
                "post_reveal_tuning_allowed": False,
                "redesign_requires_new_campaign_and_run": True,
            },
        },
        "confidentiality": {
            "private_case_content_in_artifact": False,
            "expected_results_in_artifact": False,
            "private_provenance_in_artifact": False,
            "private_salts_in_artifact": False,
            "opaque_case_tokens_only": True,
        },
        "qualification": _qualification_boundary(),
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private-qualification protocol",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError("private qualification protocol must be an object")
    return ASRCriticalNumberPrivateQualificationProtocolBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_qualification_sha256(canonical),
    )


def verify_critical_number_private_qualification_protocol(
    *,
    payload: object,
    expected_sha256: object,
    definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
) -> ASRCriticalNumberPrivateQualificationProtocolBundle:
    """Rebuild a preregistered campaign protocol and require exact equality."""

    expected_digest = _require_sha256(
        name="expected private qualification protocol",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied private qualification protocol",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError("supplied qualification protocol must be an object")
    if calculate_critical_number_private_qualification_sha256(supplied) != (
        expected_digest
    ):
        raise HveeContractError(
            "supplied qualification protocol does not match expected SHA-256"
        )
    rebuilt = build_critical_number_private_qualification_protocol(definition)
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "qualification protocol does not match the preregistered definition"
        )
    return rebuilt


def build_critical_number_private_qualification_protocol_revision(
    *,
    previous_protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    previous_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    revised_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
) -> ASRCriticalNumberPrivateQualificationProtocolBundle:
    """Require a new campaign identity and run for a sealed-protocol redesign."""

    if not isinstance(
        previous_protocol,
        ASRCriticalNumberPrivateQualificationProtocolBundle,
    ):
        raise HveeContractError(
            "qualification revision requires the previous sealed protocol"
        )
    verify_critical_number_private_qualification_protocol(
        payload=previous_protocol.payload,
        expected_sha256=previous_protocol.sha256,
        definition=previous_definition,
    )
    if revised_definition.supersedes_protocol_sha256 != previous_protocol.sha256:
        raise HveeContractError(
            "revised qualification protocol must bind the previous SHA-256"
        )
    if (
        revised_definition.campaign_id,
        revised_definition.campaign_version,
    ) == (
        previous_definition.campaign_id,
        previous_definition.campaign_version,
    ):
        raise HveeContractError(
            "revised qualification protocol requires a new campaign identity"
        )
    if revised_definition.run_id == previous_definition.run_id:
        raise HveeContractError(
            "revised qualification protocol requires a new run id"
        )
    return build_critical_number_private_qualification_protocol(
        revised_definition
    )


def build_critical_number_private_qualification_campaign(
    *,
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
) -> ASRCriticalNumberPrivateQualificationCampaignBundle:
    """Bind the sealed protocol to its exact private-holdout plan."""

    if not isinstance(
        protocol,
        ASRCriticalNumberPrivateQualificationProtocolBundle,
    ):
        raise HveeContractError("private qualification requires a sealed protocol")
    verified_protocol = verify_critical_number_private_qualification_protocol(
        payload=protocol.payload,
        expected_sha256=protocol.sha256,
        definition=definition,
    )
    verified_plan = verify_critical_number_private_holdout_plan(
        payload=plan.payload,
        expected_sha256=plan.sha256,
        definition=plan_definition,
    )
    if plan_definition.analysis_protocol_sha256 != verified_protocol.sha256:
        raise HveeContractError(
            "private holdout plan does not bind the sealed qualification protocol"
        )
    if (
        definition.run_id != plan_definition.run_id
        or definition.holdout_set_key != plan_definition.holdout_set_key
        or definition.holdout_set_version != plan_definition.holdout_set_version
    ):
        raise HveeContractError(
            "qualification protocol identity does not match the holdout plan"
        )
    planned_tokens = tuple(case.case_token for case in plan_definition.cases)
    if definition.case_tokens != planned_tokens:
        raise HveeContractError(
            "qualification protocol must assign every holdout case exactly"
        )

    assurance_sha256 = _require_v1_bindings()
    payload = {
        "schema_version": (
            CRITICAL_NUMBER_PRIVATE_QUALIFICATION_CAMPAIGN_SCHEMA_VERSION
        ),
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION,
            "artifact": "bound_private_qualification_campaign",
        },
        "bindings": _bindings(assurance_sha256),
        "campaign": {
            "campaign_id": definition.campaign_id,
            "campaign_version": definition.campaign_version,
            "run_id": definition.run_id,
            "qualification_protocol_sha256": verified_protocol.sha256,
            "private_holdout_plan_sha256": verified_plan.sha256,
            "selected_case_count": len(planned_tokens),
            "all_holdout_cases_assigned": True,
            "analysis_protocol_binding_verified": True,
        },
        "campaign_state": {
            "preregistration_complete": True,
            "blind_run_evaluated": False,
            "private_disclosure_evaluated": False,
            "adjudication_complete": False,
            "statistical_qualification_assessed": False,
        },
        "qualification": _qualification_boundary(),
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private-qualification campaign",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError("private qualification campaign must be an object")
    return ASRCriticalNumberPrivateQualificationCampaignBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_qualification_sha256(canonical),
    )


def verify_critical_number_private_qualification_campaign(
    *,
    payload: object,
    expected_sha256: object,
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
) -> ASRCriticalNumberPrivateQualificationCampaignBundle:
    """Rebuild the protocol-to-plan binding and require exact equality."""

    expected_digest = _require_sha256(
        name="expected private qualification campaign",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied private qualification campaign",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError("supplied qualification campaign must be an object")
    if calculate_critical_number_private_qualification_sha256(supplied) != (
        expected_digest
    ):
        raise HveeContractError(
            "supplied qualification campaign does not match expected SHA-256"
        )
    rebuilt = build_critical_number_private_qualification_campaign(
        protocol=protocol,
        definition=definition,
        plan=plan,
        plan_definition=plan_definition,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "qualification campaign does not match the bound holdout plan"
        )
    return rebuilt


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationAdjudicator:
    role: ASRCriticalNumberPrivateQualificationAdjudicatorRole
    key_id: str
    affiliation_key: str
    qualification_sha256: str
    independence_attestation_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(
            self.role,
            ASRCriticalNumberPrivateQualificationAdjudicatorRole,
        ):
            raise HveeContractError(
                "private qualification adjudicator requires a versioned role"
            )
        _require_identifier(
            name="private adjudicator key id",
            value=self.key_id,
        )
        _require_identifier(
            name="private adjudicator affiliation key",
            value=self.affiliation_key,
        )
        _require_sha256(
            name="private adjudicator qualification",
            value=self.qualification_sha256,
        )
        _require_sha256(
            name="private adjudicator independence attestation",
            value=self.independence_attestation_sha256,
        )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationCaseAdjudication:
    case_token: str
    stratum: ASRCriticalNumberPrivateQualificationStratum
    execution_status: ASRCriticalNumberPrivateHoldoutExecutionStatus
    outcome: ASRCriticalNumberPrivateQualificationAdjudicationOutcome
    primary_record_sha256: str
    secondary_record_sha256: str
    reviewers_agreed: bool
    resolution_record_sha256: str | None = None

    def __post_init__(self) -> None:
        _require_sha256(name="private adjudication case token", value=self.case_token)
        if not isinstance(
            self.stratum,
            ASRCriticalNumberPrivateQualificationStratum,
        ):
            raise HveeContractError(
                "private adjudication requires a versioned stratum"
            )
        if not isinstance(
            self.execution_status,
            ASRCriticalNumberPrivateHoldoutExecutionStatus,
        ):
            raise HveeContractError(
                "private adjudication requires an execution status"
            )
        if not isinstance(
            self.outcome,
            ASRCriticalNumberPrivateQualificationAdjudicationOutcome,
        ):
            raise HveeContractError(
                "private adjudication requires a versioned outcome"
            )
        for name, value in (
            ("primary record", self.primary_record_sha256),
            ("secondary record", self.secondary_record_sha256),
        ):
            _require_sha256(name=f"private adjudication {name}", value=value)
        if self.primary_record_sha256 == self.secondary_record_sha256:
            raise HveeContractError(
                "private adjudication independent review records must differ"
            )
        if not isinstance(self.reviewers_agreed, bool):
            raise HveeContractError(
                "private adjudication reviewer agreement must be boolean"
            )
        if self.reviewers_agreed and self.resolution_record_sha256 is not None:
            raise HveeContractError(
                "agreed private adjudication cannot contain arbitration"
            )
        if not self.reviewers_agreed:
            _require_sha256(
                name="private adjudication resolution record",
                value=self.resolution_record_sha256,
            )
        allowed = (
            _ORACLE_OUTCOMES
            if self.stratum
            in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ORACLE_STRATA_V1
            else _CONTROL_OUTCOMES
        )
        if self.outcome not in allowed:
            raise HveeContractError(
                "private adjudication outcome is incompatible with its stratum"
            )
        completed = (
            self.execution_status
            == ASRCriticalNumberPrivateHoldoutExecutionStatus.COMPLETED
        )
        if completed == (
            self.outcome
            == ASRCriticalNumberPrivateQualificationAdjudicationOutcome.EXECUTION_FAILURE
        ):
            raise HveeContractError(
                "private adjudication outcome does not match execution status"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationAdjudicationDefinition:
    adjudication_id: str
    adjudication_version: str
    campaign_sha256: str
    disclosure_manifest_sha256: str
    adjudication_procedure_sha256: str
    adjudication_environment_sha256: str
    independence_attestation_sha256: str
    adjudicators: tuple[ASRCriticalNumberPrivateQualificationAdjudicator, ...]
    cases: tuple[ASRCriticalNumberPrivateQualificationCaseAdjudication, ...]

    def __post_init__(self) -> None:
        _require_identifier(
            name="private adjudication id",
            value=self.adjudication_id,
        )
        _require_version(
            name="private adjudication version",
            value=self.adjudication_version,
        )
        for name, value in (
            ("campaign", self.campaign_sha256),
            ("disclosure manifest", self.disclosure_manifest_sha256),
            ("procedure", self.adjudication_procedure_sha256),
            ("environment", self.adjudication_environment_sha256),
            ("independence attestation", self.independence_attestation_sha256),
        ):
            _require_sha256(name=f"private adjudication {name}", value=value)
        if (
            not isinstance(self.adjudicators, tuple)
            or not all(
                isinstance(
                    adjudicator,
                    ASRCriticalNumberPrivateQualificationAdjudicator,
                )
                for adjudicator in self.adjudicators
            )
        ):
            raise HveeContractError(
                "private adjudication requires adjudicator definitions"
            )
        expected_roles = tuple(ASRCriticalNumberPrivateQualificationAdjudicatorRole)
        actual_roles = tuple(adjudicator.role for adjudicator in self.adjudicators)
        if actual_roles != expected_roles:
            raise HveeContractError(
                "private adjudicators must be ordered primary, secondary, arbiter"
            )
        key_ids = tuple(adjudicator.key_id for adjudicator in self.adjudicators)
        if len(key_ids) != len(set(key_ids)):
            raise HveeContractError("private adjudicator key ids must be distinct")
        if (
            not isinstance(self.cases, tuple)
            or not self.cases
            or not all(
                isinstance(
                    case,
                    ASRCriticalNumberPrivateQualificationCaseAdjudication,
                )
                for case in self.cases
            )
        ):
            raise HveeContractError("private adjudication requires case records")
        case_tokens = tuple(case.case_token for case in self.cases)
        if tuple(sorted(set(case_tokens))) != case_tokens:
            raise HveeContractError(
                "private adjudication cases must be unique and sorted"
            )
        record_sha256s = tuple(
            digest
            for case in self.cases
            for digest in (
                case.primary_record_sha256,
                case.secondary_record_sha256,
                case.resolution_record_sha256,
            )
            if digest is not None
        )
        if len(record_sha256s) != len(set(record_sha256s)):
            raise HveeContractError(
                "private adjudication record commitments must be unique"
            )


@dataclass(frozen=True, slots=True)
class ASRCriticalNumberPrivateQualificationAdjudicationBundle:
    payload: dict[str, object]
    sha256: str

    def __post_init__(self) -> None:
        canonical = _canonicalize_json_value(
            self.payload,
            name="critical-number private-qualification adjudication",
        )
        if not isinstance(canonical, dict):
            raise HveeContractError("private adjudication record must be an object")
        _require_sha256(
            name="private adjudication record SHA-256",
            value=self.sha256,
        )
        if calculate_critical_number_private_qualification_sha256(canonical) != (
            self.sha256
        ):
            raise HveeContractError(
                "private adjudication SHA-256 does not match its payload"
            )


def _adjudicator_snapshot(
    adjudicator: ASRCriticalNumberPrivateQualificationAdjudicator,
) -> dict[str, object]:
    return {
        "role": adjudicator.role.value,
        "key_id": adjudicator.key_id,
        "affiliation_key": adjudicator.affiliation_key,
        "qualification_sha256": adjudicator.qualification_sha256,
        "independence_attestation_sha256": (
            adjudicator.independence_attestation_sha256
        ),
    }


def calculate_critical_number_private_qualification_adjudicator_roster_sha256(
    adjudicators: tuple[
        ASRCriticalNumberPrivateQualificationAdjudicator,
        ...,
    ],
) -> str:
    """Commit the exact ordered independent-adjudicator roster."""

    if (
        not isinstance(adjudicators, tuple)
        or not adjudicators
        or not all(
            isinstance(
                adjudicator,
                ASRCriticalNumberPrivateQualificationAdjudicator,
            )
            for adjudicator in adjudicators
        )
    ):
        raise HveeContractError(
            "private qualification roster requires adjudicators"
        )
    return calculate_critical_number_private_qualification_sha256(
        {
            "domain": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION,
            "artifact": "independent_adjudicator_roster",
            "adjudicators": [
                _adjudicator_snapshot(adjudicator)
                for adjudicator in adjudicators
            ],
        }
    )


def _adjudication_case_snapshot(
    case: ASRCriticalNumberPrivateQualificationCaseAdjudication,
) -> dict[str, object]:
    return {
        "case_token": case.case_token,
        "stratum": case.stratum.value,
        "purpose": _stratum_purpose(case.stratum),
        "execution_status": case.execution_status.value,
        "outcome": case.outcome.value,
        "primary_record_sha256": case.primary_record_sha256,
        "secondary_record_sha256": case.secondary_record_sha256,
        "reviewers_agreed": case.reviewers_agreed,
        "resolution_record_sha256": case.resolution_record_sha256,
    }


def _adjudication_counts(
    cases: tuple[ASRCriticalNumberPrivateQualificationCaseAdjudication, ...],
) -> dict[str, object]:
    return {
        "outcomes": {
            outcome.value: sum(case.outcome == outcome for case in cases)
            for outcome in ASRCriticalNumberPrivateQualificationAdjudicationOutcome
        },
        "execution_statuses": {
            status.value: sum(case.execution_status == status for case in cases)
            for status in ASRCriticalNumberPrivateHoldoutExecutionStatus
        },
        "strata": {
            stratum.value: sum(case.stratum == stratum for case in cases)
            for stratum in CRITICAL_NUMBER_PRIVATE_QUALIFICATION_REQUIRED_STRATA_V1
        },
        "reviewer_agreements": sum(case.reviewers_agreed for case in cases),
        "arbitrated_disagreements": sum(
            not case.reviewers_agreed for case in cases
        ),
    }


def _require_verified_evidence_chain(
    *,
    expected_chain_id: str,
    plan_sha256: str,
    run_sha256: str,
    manifest_sha256: str,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_disclosure_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
) -> None:
    if (
        not isinstance(
            verified_plan_envelope,
            ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
        )
        or not isinstance(
            verified_run_envelope,
            ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
        )
        or not isinstance(
            verified_disclosure_envelope,
            ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
        )
    ):
        raise HveeContractError(
            "private adjudication requires the verified evidence chain"
        )
    if (
        verified_plan_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.PREREGISTERED_PLAN
        or verified_plan_envelope.artifact_sha256 != plan_sha256
        or verified_run_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.BLIND_RUN
        or verified_run_envelope.artifact_sha256 != run_sha256
        or verified_disclosure_envelope.artifact_type
        != ASRCriticalNumberPrivateEvidenceArtifactType.DISCLOSURE_MANIFEST
        or verified_disclosure_envelope.artifact_sha256 != manifest_sha256
    ):
        raise HveeContractError(
            "private adjudication evidence artifacts do not match"
        )
    if (
        verified_plan_envelope.definition.sequence_number != 1
        or verified_run_envelope.definition.sequence_number != 2
        or verified_disclosure_envelope.definition.sequence_number != 3
        or verified_plan_envelope.definition.chain_id != expected_chain_id
        or verified_run_envelope.definition.chain_id != expected_chain_id
        or verified_disclosure_envelope.definition.chain_id != expected_chain_id
        or verified_run_envelope.definition.previous_envelope_sha256
        != verified_plan_envelope.envelope.sha256
        or verified_disclosure_envelope.definition.previous_envelope_sha256
        != verified_run_envelope.envelope.sha256
        or verified_disclosure_envelope.replay_state.last_envelope_sha256
        != verified_disclosure_envelope.envelope.sha256
        or verified_disclosure_envelope.replay_state.last_sequence_number != 3
    ):
        raise HveeContractError(
            "private adjudication evidence chain is incomplete or broken"
        )


def build_critical_number_private_qualification_adjudication(
    *,
    campaign: ASRCriticalNumberPrivateQualificationCampaignBundle,
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    campaign_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    disclosure_manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    disclosure_definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_disclosure_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
) -> ASRCriticalNumberPrivateQualificationAdjudicationBundle:
    """Record complete dual adjudication without calculating qualification."""

    if not isinstance(
        definition,
        ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
    ):
        raise HveeContractError(
            "private qualification requires an adjudication definition"
        )
    verified_campaign = verify_critical_number_private_qualification_campaign(
        payload=campaign.payload,
        expected_sha256=campaign.sha256,
        protocol=protocol,
        definition=campaign_definition,
        plan=plan,
        plan_definition=plan_definition,
    )
    verified_plan = verify_critical_number_private_holdout_plan(
        payload=plan.payload,
        expected_sha256=plan.sha256,
        definition=plan_definition,
    )
    verified_run = verify_critical_number_private_holdout_blind_run(
        payload=run.payload,
        expected_sha256=run.sha256,
        plan=plan,
        plan_definition=plan_definition,
        run_definition=run_definition,
    )
    verified_manifest = verify_critical_number_private_evidence_disclosure_manifest(
        payload=disclosure_manifest.payload,
        expected_sha256=disclosure_manifest.sha256,
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        verified_plan_envelope=verified_plan_envelope,
        verified_run_envelope=verified_run_envelope,
        definition=disclosure_definition,
    )
    _require_verified_evidence_chain(
        expected_chain_id=campaign_definition.run_id,
        plan_sha256=verified_plan.sha256,
        run_sha256=verified_run.sha256,
        manifest_sha256=verified_manifest.sha256,
        verified_plan_envelope=verified_plan_envelope,
        verified_run_envelope=verified_run_envelope,
        verified_disclosure_envelope=verified_disclosure_envelope,
    )
    if definition.campaign_sha256 != verified_campaign.sha256:
        raise HveeContractError(
            "private adjudication does not bind the qualification campaign"
        )
    if definition.disclosure_manifest_sha256 != verified_manifest.sha256:
        raise HveeContractError(
            "private adjudication does not bind the disclosure manifest"
        )
    protocol_preregistration = protocol.payload.get("preregistration")
    if not isinstance(protocol_preregistration, dict):
        raise HveeContractError("private qualification protocol is malformed")
    independent_adjudication = protocol_preregistration.get(
        "independent_adjudication"
    )
    if not isinstance(independent_adjudication, dict) or (
        independent_adjudication.get("adjudication_protocol_sha256")
        != campaign_definition.adjudication_protocol_sha256
    ):
        raise HveeContractError(
            "private adjudication protocol binding is invalid"
        )
    if definition.adjudication_procedure_sha256 != (
        campaign_definition.adjudication_protocol_sha256
    ):
        raise HveeContractError(
            "private adjudication does not use the preregistered procedure"
        )
    roster_sha256 = (
        calculate_critical_number_private_qualification_adjudicator_roster_sha256(
            definition.adjudicators
        )
    )
    if roster_sha256 != campaign_definition.adjudicator_roster_sha256:
        raise HveeContractError(
            "private adjudication roster does not match preregistration"
        )
    expected_by_token = {
        token: stratum.stratum
        for stratum in campaign_definition.strata
        for token in stratum.case_tokens
    }
    execution_by_token = {
        execution.case_token: execution
        for execution in run_definition.executions
    }
    if tuple(case.case_token for case in definition.cases) != (
        campaign_definition.case_tokens
    ):
        raise HveeContractError(
            "private adjudication must retain every campaign case exactly"
        )
    for case in definition.cases:
        execution = execution_by_token.get(case.case_token)
        if (
            expected_by_token.get(case.case_token) != case.stratum
            or execution is None
            or execution.status != case.execution_status
        ):
            raise HveeContractError(
                "private adjudication case does not match campaign evidence"
            )

    assurance_sha256 = _require_v1_bindings()
    payload = {
        "schema_version": (
            CRITICAL_NUMBER_PRIVATE_QUALIFICATION_ADJUDICATION_SCHEMA_VERSION
        ),
        "protocol": {
            "key": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_KEY,
            "version": CRITICAL_NUMBER_PRIVATE_QUALIFICATION_PROTOCOL_VERSION,
            "artifact": "independent_private_qualification_adjudication",
        },
        "bindings": _bindings(assurance_sha256),
        "sealed_evidence": {
            "qualification_protocol_sha256": protocol.sha256,
            "qualification_campaign_sha256": verified_campaign.sha256,
            "private_holdout_plan_sha256": verified_plan.sha256,
            "private_blind_run_sha256": verified_run.sha256,
            "private_disclosure_manifest_sha256": verified_manifest.sha256,
            "signed_plan_envelope_sha256": (
                verified_plan_envelope.envelope.sha256
            ),
            "signed_blind_run_envelope_sha256": (
                verified_run_envelope.envelope.sha256
            ),
            "signed_disclosure_envelope_sha256": (
                verified_disclosure_envelope.envelope.sha256
            ),
        },
        "independent_adjudication": {
            "adjudication_id": definition.adjudication_id,
            "adjudication_version": definition.adjudication_version,
            "adjudication_procedure_sha256": (
                definition.adjudication_procedure_sha256
            ),
            "adjudication_environment_sha256": (
                definition.adjudication_environment_sha256
            ),
            "independence_attestation_sha256": (
                definition.independence_attestation_sha256
            ),
            "adjudicators": [
                _adjudicator_snapshot(adjudicator)
                for adjudicator in definition.adjudicators
            ],
            "selected_case_count": len(campaign_definition.case_tokens),
            "adjudicated_case_count": len(definition.cases),
            "all_selected_cases_retained": True,
            "dual_independent_review_complete": True,
            "all_disagreements_arbitrated": True,
            "counts": _adjudication_counts(definition.cases),
            "cases": [
                _adjudication_case_snapshot(case) for case in definition.cases
            ],
        },
        "statistical_assessment": {
            "criteria_sha256": calculate_critical_number_private_qualification_sha256(
                _criteria_snapshot(campaign_definition.statistical_criteria)
            ),
            "criteria_frozen_before_outputs": True,
            "qualification_statistics_calculated": False,
            "acceptance_criteria_evaluated": False,
            "qualification_verdict": None,
        },
        "confidentiality": {
            "private_case_content_in_artifact": False,
            "expected_results_in_artifact": False,
            "private_provenance_in_artifact": False,
            "evaluator_outputs_in_artifact": False,
            "private_salts_in_artifact": False,
            "adjudication_record_contents_in_artifact": False,
            "opaque_commitments_and_outcomes_only": True,
        },
        "qualification": _qualification_boundary(),
    }
    canonical = _canonicalize_json_value(
        payload,
        name="critical-number private-qualification adjudication",
    )
    if not isinstance(canonical, dict):
        raise HveeContractError("private adjudication record must be an object")
    return ASRCriticalNumberPrivateQualificationAdjudicationBundle(
        payload=canonical,
        sha256=calculate_critical_number_private_qualification_sha256(canonical),
    )


def verify_critical_number_private_qualification_adjudication(
    *,
    payload: object,
    expected_sha256: object,
    campaign: ASRCriticalNumberPrivateQualificationCampaignBundle,
    protocol: ASRCriticalNumberPrivateQualificationProtocolBundle,
    campaign_definition: ASRCriticalNumberPrivateQualificationCampaignDefinition,
    plan: ASRCriticalNumberPrivateHoldoutPlanBundle,
    plan_definition: ASRCriticalNumberPrivateHoldoutPlanDefinition,
    run: ASRCriticalNumberPrivateHoldoutBlindRunBundle,
    run_definition: ASRCriticalNumberPrivateHoldoutBlindRunDefinition,
    disclosure_manifest: ASRCriticalNumberPrivateEvidenceDisclosureManifestBundle,
    disclosure_definition: ASRCriticalNumberPrivateEvidenceDisclosureDefinition,
    verified_plan_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_run_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    verified_disclosure_envelope: ASRCriticalNumberPrivateEvidenceVerifiedEnvelope,
    definition: ASRCriticalNumberPrivateQualificationAdjudicationDefinition,
) -> ASRCriticalNumberPrivateQualificationAdjudicationBundle:
    """Rebuild the adjudication artifact and require exact evidence equality."""

    expected_digest = _require_sha256(
        name="expected private qualification adjudication",
        value=expected_sha256,
    )
    supplied = _canonicalize_json_value(
        payload,
        name="supplied private qualification adjudication",
    )
    if not isinstance(supplied, dict):
        raise HveeContractError("supplied private adjudication must be an object")
    if calculate_critical_number_private_qualification_sha256(supplied) != (
        expected_digest
    ):
        raise HveeContractError(
            "supplied private adjudication does not match expected SHA-256"
        )
    rebuilt = build_critical_number_private_qualification_adjudication(
        campaign=campaign,
        protocol=protocol,
        campaign_definition=campaign_definition,
        plan=plan,
        plan_definition=plan_definition,
        run=run,
        run_definition=run_definition,
        disclosure_manifest=disclosure_manifest,
        disclosure_definition=disclosure_definition,
        verified_plan_envelope=verified_plan_envelope,
        verified_run_envelope=verified_run_envelope,
        verified_disclosure_envelope=verified_disclosure_envelope,
        definition=definition,
    )
    if supplied != rebuilt.payload or expected_digest != rebuilt.sha256:
        raise HveeContractError(
            "private adjudication does not match independently rebuilt evidence"
        )
    return rebuilt
