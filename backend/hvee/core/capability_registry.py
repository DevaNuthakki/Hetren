from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from typing import Any


CAPABILITY_REGISTRY_SCHEMA_VERSION = "1.0.0"


class CapabilityRegistryError(ValueError):
    pass


class ComponentKind(str, Enum):
    MODEL = "model"
    AGENT = "agent"
    TOOL = "tool"
    MCP_SERVER = "mcp_server"
    API = "api"
    RAG = "rag"
    RETRIEVAL = "retrieval"
    PROMPT = "prompt"
    APPLICATION_CODE = "application_code"
    SERVICE = "service"
    DATABASE = "database"
    OTHER = "other"


class ModelAccessTier(str, Enum):
    CLOSED_API = "a_closed_api"
    PRIVATE_INFERENCE = "b_private_inference"
    AUTHORIZED_INTERNALS = "c_authorized_internals"


class CapabilityAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class CapabilityQualificationState(str, Enum):
    UNQUALIFIED = "unqualified"
    QUALIFIED = "qualified"
    SUSPENDED = "suspended"
    REVOKED = "revoked"


class CapabilityExecutionLocation(str, Enum):
    CONTROL_PLANE = "control_plane"
    PRIVATE_RUNNER = "private_runner"
    CUSTOMER_RUNTIME = "customer_runtime"


class CapabilityEgressPolicy(str, Enum):
    NO_EGRESS = "no_egress"
    AGGREGATE_ONLY = "aggregate_only"
    APPROVED_ARTIFACTS = "approved_artifacts"
    RAW_ALLOWED = "raw_allowed"


_ACCESS_TIER_RANK = {
    ModelAccessTier.CLOSED_API: 1,
    ModelAccessTier.PRIVATE_INFERENCE: 2,
    ModelAccessTier.AUTHORIZED_INTERNALS: 3,
}


def _require_nonempty_string(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise CapabilityRegistryError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise CapabilityRegistryError(
            f"{field_name} must not be empty"
        )

    return normalized


def _require_sha256(
    value: object,
    *,
    field_name: str,
) -> str:
    normalized = _require_nonempty_string(
        value,
        field_name=field_name,
    )

    if len(normalized) != 64:
        raise CapabilityRegistryError(
            f"{field_name} must contain exactly 64 hexadecimal characters"
        )

    try:
        int(normalized, 16)
    except ValueError as exc:
        raise CapabilityRegistryError(
            f"{field_name} must contain hexadecimal characters only"
        ) from exc

    return normalized.lower()


def _require_optional_sha256(
    value: object,
    *,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _require_sha256(
        value,
        field_name=field_name,
    )


def _require_enum(
    value: object,
    enum_type: type[Enum],
    *,
    field_name: str,
) -> None:
    if not isinstance(value, enum_type):
        raise CapabilityRegistryError(
            f"{field_name} must be a {enum_type.__name__}"
        )


def _require_unique_strings(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise CapabilityRegistryError(
            f"{field_name} must be a tuple"
        )

    normalized = []

    for value in values:
        normalized.append(
            _require_nonempty_string(
                value,
                field_name=field_name,
            )
        )

    if len(set(normalized)) != len(normalized):
        raise CapabilityRegistryError(
            f"{field_name} must not contain duplicates"
        )


def _require_sha256_tuple(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> None:
    if not isinstance(values, tuple):
        raise CapabilityRegistryError(
            f"{field_name} must be a tuple"
        )

    normalized = [
        _require_sha256(
            value,
            field_name=field_name,
        )
        for value in values
    ]

    if len(set(normalized)) != len(normalized):
        raise CapabilityRegistryError(
            f"{field_name} must not contain duplicates"
        )


def _to_primitive(
    value: Any,
) -> Any:
    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value):
        return {
            field.name: _to_primitive(
                getattr(
                    value,
                    field.name,
                )
            )
            for field in fields(value)
        }

    if isinstance(value, tuple):
        return [
            _to_primitive(item)
            for item in value
        ]

    if isinstance(value, list):
        return [
            _to_primitive(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            str(key): _to_primitive(item)
            for key, item in sorted(
                value.items(),
                key=lambda entry: str(entry[0]),
            )
        }

    return value


def _calculate_sha256(
    value: Any,
) -> str:
    canonical = json.dumps(
        _to_primitive(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")

    return hashlib.sha256(
        canonical
    ).hexdigest()


@dataclass(frozen=True)
class PortfolioComponentIdentity:
    tenant_key: str
    project_key: str
    system_key: str
    component_key: str
    component_kind: ComponentKind
    version_key: str

    def __post_init__(
        self,
    ) -> None:
        for field_name in (
            "tenant_key",
            "project_key",
            "system_key",
            "component_key",
            "version_key",
        ):
            _require_nonempty_string(
                getattr(
                    self,
                    field_name,
                ),
                field_name=field_name,
            )

        _require_enum(
            self.component_kind,
            ComponentKind,
            field_name="component_kind",
        )


@dataclass(frozen=True)
class ModelRuntimeBinding:
    binding_key: str
    binding_version: str
    component: PortfolioComponentIdentity
    provider_key: str
    model_key: str
    model_version: str
    runtime_key: str
    runtime_version: str
    runtime_identity_sha256: str
    runtime_model_sha256: str
    access_tier: ModelAccessTier
    checkpoint_sha256: str | None = None
    configuration_sha256: str | None = None

    def __post_init__(
        self,
    ) -> None:
        if not isinstance(
            self.component,
            PortfolioComponentIdentity,
        ):
            raise CapabilityRegistryError(
                "component must be a PortfolioComponentIdentity"
            )

        if self.component.component_kind is not ComponentKind.MODEL:
            raise CapabilityRegistryError(
                "ModelRuntimeBinding requires a model component"
            )

        for field_name in (
            "binding_key",
            "binding_version",
            "provider_key",
            "model_key",
            "model_version",
            "runtime_key",
            "runtime_version",
        ):
            _require_nonempty_string(
                getattr(
                    self,
                    field_name,
                ),
                field_name=field_name,
            )

        _require_sha256(
            self.runtime_identity_sha256,
            field_name="runtime_identity_sha256",
        )

        _require_sha256(
            self.runtime_model_sha256,
            field_name="runtime_model_sha256",
        )

        _require_optional_sha256(
            self.checkpoint_sha256,
            field_name="checkpoint_sha256",
        )

        _require_optional_sha256(
            self.configuration_sha256,
            field_name="configuration_sha256",
        )

        _require_enum(
            self.access_tier,
            ModelAccessTier,
            field_name="access_tier",
        )


@dataclass(frozen=True)
class CapabilityRegistration:
    capability_key: str
    capability_version: str
    binding_identity_sha256: str
    availability: CapabilityAvailability
    qualification_state: CapabilityQualificationState
    qualification_scope: str
    required_access_tier: ModelAccessTier
    execution_location: CapabilityExecutionLocation
    egress_policy: CapabilityEgressPolicy
    requires_human_approval: bool
    qualification_evidence_sha256: tuple[str, ...] = ()
    source_capability_sha256: str | None = None
    reason_code: str | None = None
    constraints: tuple[str, ...] = ()

    def __post_init__(
        self,
    ) -> None:
        _require_nonempty_string(
            self.capability_key,
            field_name="capability_key",
        )

        _require_nonempty_string(
            self.capability_version,
            field_name="capability_version",
        )

        _require_sha256(
            self.binding_identity_sha256,
            field_name="binding_identity_sha256",
        )

        _require_enum(
            self.availability,
            CapabilityAvailability,
            field_name="availability",
        )

        _require_enum(
            self.qualification_state,
            CapabilityQualificationState,
            field_name="qualification_state",
        )

        _require_nonempty_string(
            self.qualification_scope,
            field_name="qualification_scope",
        )

        _require_enum(
            self.required_access_tier,
            ModelAccessTier,
            field_name="required_access_tier",
        )

        _require_enum(
            self.execution_location,
            CapabilityExecutionLocation,
            field_name="execution_location",
        )

        _require_enum(
            self.egress_policy,
            CapabilityEgressPolicy,
            field_name="egress_policy",
        )

        if not isinstance(
            self.requires_human_approval,
            bool,
        ):
            raise CapabilityRegistryError(
                "requires_human_approval must be a bool"
            )

        _require_sha256_tuple(
            self.qualification_evidence_sha256,
            field_name="qualification_evidence_sha256",
        )

        _require_optional_sha256(
            self.source_capability_sha256,
            field_name="source_capability_sha256",
        )

        _require_unique_strings(
            self.constraints,
            field_name="constraints",
        )

        if self.reason_code is not None:
            _require_nonempty_string(
                self.reason_code,
                field_name="reason_code",
            )

        if (
            self.availability
            is CapabilityAvailability.UNAVAILABLE
            and self.reason_code is None
        ):
            raise CapabilityRegistryError(
                "unavailable capability requires reason_code"
            )

        if (
            self.qualification_state
            is CapabilityQualificationState.QUALIFIED
            and not self.qualification_evidence_sha256
        ):
            raise CapabilityRegistryError(
                "qualified capability requires qualification evidence"
            )


def calculate_portfolio_component_identity_sha256(
    component: PortfolioComponentIdentity,
) -> str:
    if not isinstance(
        component,
        PortfolioComponentIdentity,
    ):
        raise CapabilityRegistryError(
            "component has invalid type"
        )

    return _calculate_sha256(
        {
            "schema_version": CAPABILITY_REGISTRY_SCHEMA_VERSION,
            "component": component,
        }
    )


def calculate_model_runtime_binding_sha256(
    binding: ModelRuntimeBinding,
) -> str:
    if not isinstance(
        binding,
        ModelRuntimeBinding,
    ):
        raise CapabilityRegistryError(
            "binding has invalid type"
        )

    return _calculate_sha256(
        {
            "schema_version": CAPABILITY_REGISTRY_SCHEMA_VERSION,
            "binding": binding,
        }
    )


def calculate_capability_registration_sha256(
    capability: CapabilityRegistration,
) -> str:
    if not isinstance(
        capability,
        CapabilityRegistration,
    ):
        raise CapabilityRegistryError(
            "capability has invalid type"
        )

    return _calculate_sha256(
        {
            "schema_version": CAPABILITY_REGISTRY_SCHEMA_VERSION,
            "capability": capability,
        }
    )


def _binding_natural_key(
    binding: ModelRuntimeBinding,
) -> tuple[str, ...]:
    return (
        calculate_portfolio_component_identity_sha256(
            binding.component
        ),
        binding.binding_key,
        binding.binding_version,
        binding.provider_key,
        binding.model_key,
        binding.model_version,
        binding.runtime_key,
        binding.runtime_version,
    )


class CapabilityRegistry:
    def __init__(
        self,
    ) -> None:
        self._bindings_by_identity: dict[
            str,
            ModelRuntimeBinding,
        ] = {}

        self._binding_natural_keys: dict[
            tuple[str, ...],
            str,
        ] = {}

        self._capabilities: dict[
            tuple[str, str, str],
            CapabilityRegistration,
        ] = {}

    @property
    def binding_count(
        self,
    ) -> int:
        return len(
            self._bindings_by_identity
        )

    @property
    def capability_count(
        self,
    ) -> int:
        return len(
            self._capabilities
        )

    def register_binding(
        self,
        binding: ModelRuntimeBinding,
    ) -> str:
        if not isinstance(
            binding,
            ModelRuntimeBinding,
        ):
            raise CapabilityRegistryError(
                "binding has invalid type"
            )

        binding_identity = (
            calculate_model_runtime_binding_sha256(
                binding
            )
        )

        natural_key = _binding_natural_key(
            binding
        )

        previous_identity = (
            self._binding_natural_keys.get(
                natural_key
            )
        )

        if (
            previous_identity is not None
            and previous_identity != binding_identity
        ):
            raise CapabilityRegistryError(
                "conflicting model/runtime binding registration"
            )

        previous_binding = (
            self._bindings_by_identity.get(
                binding_identity
            )
        )

        if (
            previous_binding is not None
            and previous_binding != binding
        ):
            raise CapabilityRegistryError(
                "binding identity collision"
            )

        self._binding_natural_keys[
            natural_key
        ] = binding_identity

        self._bindings_by_identity[
            binding_identity
        ] = binding

        return binding_identity

    def get_binding(
        self,
        binding_identity_sha256: str,
    ) -> ModelRuntimeBinding:
        identity = _require_sha256(
            binding_identity_sha256,
            field_name="binding_identity_sha256",
        )

        try:
            return self._bindings_by_identity[
                identity
            ]
        except KeyError as exc:
            raise CapabilityRegistryError(
                "unknown model/runtime binding"
            ) from exc

    def register_capability(
        self,
        capability: CapabilityRegistration,
    ) -> str:
        if not isinstance(
            capability,
            CapabilityRegistration,
        ):
            raise CapabilityRegistryError(
                "capability has invalid type"
            )

        binding = self.get_binding(
            capability.binding_identity_sha256
        )

        if (
            _ACCESS_TIER_RANK[
                binding.access_tier
            ]
            < _ACCESS_TIER_RANK[
                capability.required_access_tier
            ]
        ):
            raise CapabilityRegistryError(
                "binding access tier does not satisfy capability requirement"
            )

        key = (
            capability.binding_identity_sha256,
            capability.capability_key,
            capability.capability_version,
        )

        previous = self._capabilities.get(
            key
        )

        if (
            previous is not None
            and previous != capability
        ):
            raise CapabilityRegistryError(
                "conflicting capability registration"
            )

        self._capabilities[
            key
        ] = capability

        return (
            calculate_capability_registration_sha256(
                capability
            )
        )

    def capabilities_for_binding(
        self,
        binding_identity_sha256: str,
    ) -> tuple[
        CapabilityRegistration,
        ...,
    ]:
        identity = _require_sha256(
            binding_identity_sha256,
            field_name="binding_identity_sha256",
        )

        self.get_binding(
            identity
        )

        matches = [
            capability
            for (
                binding_identity,
                _,
                _,
            ), capability in self._capabilities.items()
            if binding_identity == identity
        ]

        return tuple(
            sorted(
                matches,
                key=lambda capability: (
                    capability.capability_key,
                    capability.capability_version,
                ),
            )
        )

    def require_qualified_capability(
        self,
        *,
        binding_identity_sha256: str,
        capability_key: str,
        capability_version: str,
    ) -> CapabilityRegistration:
        identity = _require_sha256(
            binding_identity_sha256,
            field_name="binding_identity_sha256",
        )

        normalized_key = _require_nonempty_string(
            capability_key,
            field_name="capability_key",
        )

        normalized_version = _require_nonempty_string(
            capability_version,
            field_name="capability_version",
        )

        self.get_binding(
            identity
        )

        registration = self._capabilities.get(
            (
                identity,
                normalized_key,
                normalized_version,
            )
        )

        if registration is None:
            raise CapabilityRegistryError(
                "capability is not registered"
            )

        if (
            registration.availability
            is not CapabilityAvailability.AVAILABLE
        ):
            raise CapabilityRegistryError(
                "capability is unavailable"
            )

        if (
            registration.qualification_state
            is not CapabilityQualificationState.QUALIFIED
        ):
            raise CapabilityRegistryError(
                "capability is not qualified"
            )

        return registration

    def snapshot_payload(
        self,
    ) -> dict[str, Any]:
        bindings = [
            {
                "binding_identity_sha256": identity,
                "binding": _to_primitive(
                    binding
                ),
            }
            for identity, binding in sorted(
                self._bindings_by_identity.items()
            )
        ]

        capabilities = [
            {
                "capability_identity_sha256": (
                    calculate_capability_registration_sha256(
                        capability
                    )
                ),
                "capability": _to_primitive(
                    capability
                ),
            }
            for _, capability in sorted(
                self._capabilities.items(),
                key=lambda item: item[0],
            )
        ]

        return {
            "schema_version": CAPABILITY_REGISTRY_SCHEMA_VERSION,
            "binding_count": len(
                bindings
            ),
            "capability_count": len(
                capabilities
            ),
            "bindings": bindings,
            "capabilities": capabilities,
        }

    def snapshot_sha256(
        self,
    ) -> str:
        return _calculate_sha256(
            self.snapshot_payload()
        )


def register_internal_runtime_capabilities(
    *,
    registry: CapabilityRegistry,
    binding: ModelRuntimeBinding,
    runtime_capability: object,
    qualification_state: CapabilityQualificationState,
    qualification_scope: str,
    qualification_evidence_sha256: tuple[str, ...],
    execution_location: CapabilityExecutionLocation = (
        CapabilityExecutionLocation.PRIVATE_RUNNER
    ),
) -> tuple[
    CapabilityRegistration,
    ...,
]:
    from hvee.core.internal_engine import (
        InternalRuntimeCapability,
        calculate_internal_runtime_capability_sha256,
    )

    if not isinstance(
        registry,
        CapabilityRegistry,
    ):
        raise CapabilityRegistryError(
            "registry has invalid type"
        )

    if not isinstance(
        binding,
        ModelRuntimeBinding,
    ):
        raise CapabilityRegistryError(
            "binding has invalid type"
        )

    if not isinstance(
        runtime_capability,
        InternalRuntimeCapability,
    ):
        raise CapabilityRegistryError(
            "runtime_capability must be an InternalRuntimeCapability"
        )

    if (
        binding.access_tier
        is not ModelAccessTier.AUTHORIZED_INTERNALS
    ):
        raise CapabilityRegistryError(
            "internal runtime capabilities require authorized internals"
        )

    if (
        runtime_capability.runtime_key
        != binding.runtime_key
    ):
        raise CapabilityRegistryError(
            "runtime key does not match binding"
        )

    if (
        runtime_capability.runtime_version
        != binding.runtime_version
    ):
        raise CapabilityRegistryError(
            "runtime version does not match binding"
        )

    if (
        runtime_capability.runtime_identity_sha256
        != binding.runtime_identity_sha256
    ):
        raise CapabilityRegistryError(
            "runtime identity does not match binding"
        )

    if (
        runtime_capability.runtime_model_sha256
        != binding.runtime_model_sha256
    ):
        raise CapabilityRegistryError(
            "runtime model identity does not match binding"
        )

    if runtime_capability.raw_tensor_egress is not False:
        raise CapabilityRegistryError(
            "internal runtime capability allows raw tensor egress"
        )

    if not runtime_capability.supported_interventions:
        raise CapabilityRegistryError(
            "internal runtime capability has no supported interventions"
        )

    registry.register_binding(
        binding
    )

    source_capability_sha256 = (
        calculate_internal_runtime_capability_sha256(
            runtime_capability
        )
    )

    registrations = []

    interventions = sorted(
        runtime_capability.supported_interventions,
        key=lambda item: item.value,
    )

    for intervention in interventions:
        capability = CapabilityRegistration(
            capability_key=(
                "internal_engine."
                + intervention.value
            ),
            capability_version="1.0.0",
            binding_identity_sha256=(
                calculate_model_runtime_binding_sha256(
                    binding
                )
            ),
            availability=(
                CapabilityAvailability.AVAILABLE
            ),
            qualification_state=(
                qualification_state
            ),
            qualification_scope=(
                qualification_scope
            ),
            required_access_tier=(
                ModelAccessTier.AUTHORIZED_INTERNALS
            ),
            execution_location=(
                execution_location
            ),
            egress_policy=(
                CapabilityEgressPolicy.AGGREGATE_ONLY
            ),
            requires_human_approval=False,
            qualification_evidence_sha256=(
                qualification_evidence_sha256
            ),
            source_capability_sha256=(
                source_capability_sha256
            ),
            constraints=(
                "raw_tensor_egress=false",
                "exact_runtime_identity_required=true",
                "exact_runtime_model_identity_required=true",
            ),
        )

        registry.register_capability(
            capability
        )

        registrations.append(
            capability
        )

    return tuple(
        registrations
    )
