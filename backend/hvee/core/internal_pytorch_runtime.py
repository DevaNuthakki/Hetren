from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
import math
import re
from typing import Protocol

import torch
from torch import Tensor, nn

from hvee.core.contracts import HveeContractError
from hvee.core.experiment_protocol import (
    ExperimentObservationStatus,
)
from hvee.core.internal_engine import (
    InternalActivationSummary,
    InternalExperimentRequest,
    InternalInterventionKind,
    InternalInterventionObservation,
    InternalModuleTarget,
    InternalRuntimeCapability,
    build_internal_intervention_observation,
)


PYTORCH_INTERNAL_RUNTIME_KEY = "pytorch_internal_runtime"

PYTORCH_INTERNAL_RUNTIME_VERSION = "1.0.0-foundation"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PyTorchOutputSelectorStepKind(StrEnum):
    ROOT_TENSOR = "root_tensor"
    TUPLE_OR_LIST_INTEGER_INDEX = "tuple_or_list_integer_index"
    DICT_STRING_KEY = "dict_string_key"


@dataclass(
    frozen=True,
    slots=True,
)
class PyTorchOutputSelectorStep:
    kind: PyTorchOutputSelectorStepKind
    index: int | None = None
    key: str | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class PyTorchOutputSelector:
    steps: tuple[
        PyTorchOutputSelectorStep,
        ...,
    ]


@dataclass(
    frozen=True,
    slots=True,
)
class PyTorchTargetBinding:
    module_path: str
    module_kind: str
    selector: PyTorchOutputSelector
    module_index: int | None = None
    head_index: int | None = None


class PyTorchExecutionDriver(Protocol):
    def __call__(
        self,
        model: nn.Module,
    ) -> object: ...


def _canonical_bytes(
    value: object,
) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise HveeContractError("value is not canonically serializable") from exc


def _calculate_sha256(
    value: object,
) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_identifier(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise HveeContractError(field + " must be a string")

    normalized = value.strip()

    if not normalized:
        raise HveeContractError(field + " must not be empty")

    if normalized != value:
        raise HveeContractError(field + " must not contain surrounding whitespace")

    if len(normalized) > 512:
        raise HveeContractError(field + " is too long")

    return normalized


def _require_sha256(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(
        value,
        str,
    ) or not _SHA256_RE.fullmatch(value):
        raise HveeContractError(field + " must be a lowercase SHA-256 digest")

    return value


def _require_optional_nonnegative_integer(
    value: object,
    *,
    field: str,
) -> int | None:
    if value is None:
        return None

    if (
        isinstance(
            value,
            bool,
        )
        or not isinstance(
            value,
            int,
        )
        or value < 0
    ):
        raise HveeContractError(field + " must be a non-negative integer or null")

    return value


def _selector_payload(
    selector: PyTorchOutputSelector,
) -> dict[str, object]:
    if not isinstance(
        selector,
        PyTorchOutputSelector,
    ):
        raise HveeContractError("output selector has invalid type")

    if (
        not isinstance(
            selector.steps,
            tuple,
        )
        or not selector.steps
    ):
        raise HveeContractError("output selector must contain at least one step")

    result = []

    for step in selector.steps:
        if not isinstance(
            step,
            PyTorchOutputSelectorStep,
        ):
            raise HveeContractError("output selector contains invalid step")

        if not isinstance(
            step.kind,
            PyTorchOutputSelectorStepKind,
        ):
            raise HveeContractError("output selector step kind is invalid")

        if step.kind == PyTorchOutputSelectorStepKind.ROOT_TENSOR:
            if len(selector.steps) != 1:
                raise HveeContractError("ROOT_TENSOR must be the only selector step")

            if step.index is not None or step.key is not None:
                raise HveeContractError("ROOT_TENSOR does not accept index or key")

            result.append(
                {
                    "kind": (step.kind.value),
                }
            )

        elif step.kind == PyTorchOutputSelectorStepKind.TUPLE_OR_LIST_INTEGER_INDEX:
            index = _require_optional_nonnegative_integer(
                step.index,
                field="selector index",
            )

            if index is None:
                raise HveeContractError("tuple/list selector requires index")

            if step.key is not None:
                raise HveeContractError("tuple/list selector does not accept key")

            result.append(
                {
                    "index": index,
                    "kind": (step.kind.value),
                }
            )

        elif step.kind == PyTorchOutputSelectorStepKind.DICT_STRING_KEY:
            if step.index is not None:
                raise HveeContractError("dict selector does not accept index")

            key = _require_identifier(
                step.key,
                field="selector key",
            )

            result.append(
                {
                    "key": key,
                    "kind": (step.kind.value),
                }
            )

        else:
            raise HveeContractError("unsupported output selector step")

    return {
        "steps": result,
    }


def _binding_payload(
    binding: PyTorchTargetBinding,
) -> dict[str, object]:
    if not isinstance(
        binding,
        PyTorchTargetBinding,
    ):
        raise HveeContractError("target binding has invalid type")

    return {
        "head_index": (
            _require_optional_nonnegative_integer(
                binding.head_index,
                field="head_index",
            )
        ),
        "module_index": (
            _require_optional_nonnegative_integer(
                binding.module_index,
                field="module_index",
            )
        ),
        "module_kind": (
            _require_identifier(
                binding.module_kind,
                field="module_kind",
            )
        ),
        "module_path": (
            _require_identifier(
                binding.module_path,
                field="module_path",
            )
        ),
        "selector": (_selector_payload(binding.selector)),
    }


def calculate_pytorch_target_selector_configuration_sha256(
    bindings: tuple[
        PyTorchTargetBinding,
        ...,
    ],
) -> str:
    if (
        not isinstance(
            bindings,
            tuple,
        )
        or not bindings
    ):
        raise HveeContractError("target bindings must be a non-empty tuple")

    payloads = [_binding_payload(binding) for binding in bindings]

    paths = [str(payload["module_path"]) for payload in payloads]

    if len(paths) != len(set(paths)):
        raise HveeContractError("target bindings contain duplicate module paths")

    return _calculate_sha256(
        {
            "bindings": sorted(
                payloads,
                key=lambda item: (str(item["module_path"])),
            ),
            "schema_version": 1,
        }
    )


def calculate_pytorch_target_identity_sha256(
    *,
    runtime_model_sha256: str,
    binding: PyTorchTargetBinding,
) -> str:
    model_sha = _require_sha256(
        runtime_model_sha256,
        field="runtime_model_sha256",
    )

    return _calculate_sha256(
        {
            "binding": (_binding_payload(binding)),
            "runtime_model_sha256": (model_sha),
            "schema_version": 1,
        }
    )


def calculate_pytorch_runtime_identity_sha256(
    *,
    torch_version: str,
    runtime_model_sha256: str,
    execution_driver_identity_sha256: str,
    target_selector_configuration_sha256: str,
) -> str:
    return _calculate_sha256(
        {
            "execution_driver_identity_sha256": (
                _require_sha256(
                    execution_driver_identity_sha256,
                    field="execution_driver_identity_sha256",
                )
            ),
            "runtime_key": (PYTORCH_INTERNAL_RUNTIME_KEY),
            "runtime_model_sha256": (
                _require_sha256(
                    runtime_model_sha256,
                    field="runtime_model_sha256",
                )
            ),
            "runtime_version": (PYTORCH_INTERNAL_RUNTIME_VERSION),
            "schema_version": 1,
            "target_selector_configuration_sha256": (
                _require_sha256(
                    target_selector_configuration_sha256,
                    field="target_selector_configuration_sha256",
                )
            ),
            "torch_version": (
                _require_identifier(
                    torch_version,
                    field="torch_version",
                )
            ),
        }
    )


def _select_output_tensor(
    output: object,
    selector: PyTorchOutputSelector,
) -> Tensor:
    selector_payload = _selector_payload(selector)

    steps = selector_payload["steps"]

    if not isinstance(
        steps,
        list,
    ):
        raise HveeContractError("selector payload is invalid")

    if (
        len(steps) == 1
        and steps[0]["kind"] == PyTorchOutputSelectorStepKind.ROOT_TENSOR.value
    ):
        current = output

    else:
        current = output

        for step in steps:
            kind = step["kind"]

            if kind == PyTorchOutputSelectorStepKind.TUPLE_OR_LIST_INTEGER_INDEX.value:
                if type(current) not in (
                    tuple,
                    list,
                ):
                    raise HveeContractError(
                        "tuple/list selector reached unsupported output container"
                    )

                index = step["index"]

                if (
                    not isinstance(
                        index,
                        int,
                    )
                    or index < 0
                    or index >= len(current)
                ):
                    raise HveeContractError("tuple/list selector index is out of range")

                current = current[index]

            elif kind == PyTorchOutputSelectorStepKind.DICT_STRING_KEY.value:
                if type(current) is not dict:
                    raise HveeContractError(
                        "dict selector reached unsupported output container"
                    )

                key = step["key"]

                if key not in current:
                    raise HveeContractError("dict selector key is missing")

                current = current[key]

            else:
                raise HveeContractError("unsupported selector traversal")

    if not isinstance(
        current,
        Tensor,
    ):
        raise HveeContractError("output selector did not resolve exactly one tensor")

    return current


def _replace_selected_tensor(
    output: object,
    selector: PyTorchOutputSelector,
    replacement: Tensor,
) -> object:
    selector_payload = _selector_payload(selector)

    steps = selector_payload["steps"]

    if not isinstance(
        steps,
        list,
    ):
        raise HveeContractError("selector payload is invalid")

    if (
        len(steps) == 1
        and steps[0]["kind"] == PyTorchOutputSelectorStepKind.ROOT_TENSOR.value
    ):
        if not isinstance(
            output,
            Tensor,
        ):
            raise HveeContractError("ROOT_TENSOR selector reached non-tensor output")

        return replacement

    def replace_at(
        current: object,
        offset: int,
    ) -> object:
        if offset == len(steps):
            if not isinstance(
                current,
                Tensor,
            ):
                raise HveeContractError("selector replacement target is not a tensor")

            return replacement

        step = steps[offset]

        kind = step["kind"]

        if kind == PyTorchOutputSelectorStepKind.TUPLE_OR_LIST_INTEGER_INDEX.value:
            if type(current) not in (
                tuple,
                list,
            ):
                raise HveeContractError(
                    "tuple/list replacement reached unsupported container"
                )

            index = step["index"]

            if (
                not isinstance(
                    index,
                    int,
                )
                or index < 0
                or index >= len(current)
            ):
                raise HveeContractError("tuple/list replacement index is out of range")

            items = list(current)

            items[index] = replace_at(
                items[index],
                offset + 1,
            )

            if type(current) is tuple:
                return tuple(items)

            return items

        if kind == PyTorchOutputSelectorStepKind.DICT_STRING_KEY.value:
            if type(current) is not dict:
                raise HveeContractError(
                    "dict replacement reached unsupported container"
                )

            key = step["key"]

            if key not in current:
                raise HveeContractError("dict replacement key is missing")

            copied = dict(current)

            copied[key] = replace_at(
                copied[key],
                offset + 1,
            )

            return copied

        raise HveeContractError("unsupported selector replacement traversal")

    return replace_at(
        output,
        0,
    )


def _summarize_activation(
    tensor: Tensor,
) -> InternalActivationSummary:
    if not isinstance(
        tensor,
        Tensor,
    ):
        raise HveeContractError("activation is not a torch.Tensor")

    if not tensor.is_floating_point():
        raise HveeContractError(
            "Internal Engine V1 requires floating-point activations"
        )

    if tensor.ndim <= 0:
        raise HveeContractError("scalar activations are unsupported")

    if tensor.numel() <= 0:
        raise HveeContractError("empty activations are unsupported")

    detached = tensor.detach()

    finite = torch.isfinite(detached)

    finite_count = int(finite.sum().item())

    element_count = int(detached.numel())

    if finite_count != element_count:
        raise HveeContractError("non-finite activation detected")

    cpu = detached.contiguous().to(device="cpu")

    shape = tuple(int(value) for value in cpu.shape)

    if not shape:
        raise HveeContractError("activation shape is empty")

    dtype = str(cpu.dtype).removeprefix("torch.")

    byte_view = cpu.view(torch.uint8).contiguous().reshape(-1)

    tensor_bytes = byte_view.numpy().tobytes(order="C")

    commitment_metadata = {
        "dtype": dtype,
        "shape": list(shape),
        "schema_version": 1,
    }

    commitment_hasher = hashlib.sha256()

    commitment_hasher.update(_canonical_bytes(commitment_metadata))

    commitment_hasher.update(b"\x00")

    commitment_hasher.update(tensor_bytes)

    commitment = commitment_hasher.hexdigest()

    working = cpu.to(dtype=torch.float64)

    minimum = float(torch.min(working).item())

    maximum = float(torch.max(working).item())

    mean = float(torch.mean(working).item())

    l2_norm = float(
        torch.linalg.vector_norm(
            working.reshape(-1),
            ord=2,
        ).item()
    )

    for value in (
        minimum,
        maximum,
        mean,
        l2_norm,
    ):
        if not math.isfinite(value):
            raise HveeContractError("activation summary is non-finite")

    return InternalActivationSummary(
        shape=shape,
        dtype=dtype,
        element_count=(element_count),
        finite_element_count=(finite_count),
        minimum=minimum,
        maximum=maximum,
        mean=mean,
        l2_norm=l2_norm,
        activation_commitment_sha256=(commitment),
    )


class PyTorchInternalRuntimeAdapter:
    def __init__(
        self,
        *,
        model: nn.Module,
        runtime_model_sha256: str,
        bound_subject_sha256: str,
        execution_driver: PyTorchExecutionDriver,
        execution_driver_identity_sha256: str,
        target_bindings: tuple[
            PyTorchTargetBinding,
            ...,
        ],
    ) -> None:
        if not isinstance(
            model,
            nn.Module,
        ):
            raise HveeContractError("PyTorch runtime requires torch.nn.Module model")

        if model.training:
            raise HveeContractError(
                "PyTorch runtime requires model.eval() before construction"
            )

        if not callable(execution_driver):
            raise HveeContractError("execution_driver must be callable")

        self._runtime_model_sha256 = _require_sha256(
            runtime_model_sha256,
            field="runtime_model_sha256",
        )

        self._bound_subject_sha256 = _require_sha256(
            bound_subject_sha256,
            field="bound_subject_sha256",
        )

        self._execution_driver_identity_sha256 = _require_sha256(
            execution_driver_identity_sha256,
            field="execution_driver_identity_sha256",
        )

        if (
            not isinstance(
                target_bindings,
                tuple,
            )
            or not target_bindings
        ):
            raise HveeContractError("target_bindings must be a non-empty tuple")

        selector_configuration_sha256 = (
            calculate_pytorch_target_selector_configuration_sha256(target_bindings)
        )

        named_modules = list(model.named_modules(remove_duplicate=False))

        module_counts: dict[
            str,
            int,
        ] = {}

        resolved_modules: dict[
            str,
            nn.Module,
        ] = {}

        for name, module in named_modules:
            module_counts[name] = (
                module_counts.get(
                    name,
                    0,
                )
                + 1
            )

            if name not in (resolved_modules):
                resolved_modules[name] = module

        bindings_by_path: dict[
            str,
            PyTorchTargetBinding,
        ] = {}

        targets_by_path: dict[
            str,
            InternalModuleTarget,
        ] = {}

        modules_by_path: dict[
            str,
            nn.Module,
        ] = {}

        for binding in target_bindings:
            binding_payload = _binding_payload(binding)

            module_path = str(binding_payload["module_path"])

            if (
                module_counts.get(
                    module_path,
                    0,
                )
                != 1
            ):
                raise HveeContractError("target module path must resolve exactly once")

            if module_path in bindings_by_path:
                raise HveeContractError("duplicate target module path")

            target_identity = calculate_pytorch_target_identity_sha256(
                runtime_model_sha256=(self._runtime_model_sha256),
                binding=binding,
            )

            target = InternalModuleTarget(
                module_path=(module_path),
                module_kind=(str(binding_payload["module_kind"])),
                target_identity_sha256=(target_identity),
                runtime_model_sha256=(self._runtime_model_sha256),
                module_index=(binding.module_index),
                head_index=(binding.head_index),
            )

            bindings_by_path[module_path] = binding

            targets_by_path[module_path] = target

            modules_by_path[module_path] = resolved_modules[module_path]

        self._model = model
        self._execution_driver = execution_driver
        self._bindings_by_path = bindings_by_path
        self._targets_by_path = targets_by_path
        self._modules_by_path = modules_by_path
        self._target_selector_configuration_sha256 = selector_configuration_sha256

        self._runtime_identity_sha256 = calculate_pytorch_runtime_identity_sha256(
            torch_version=(torch.__version__),
            runtime_model_sha256=(self._runtime_model_sha256),
            execution_driver_identity_sha256=(self._execution_driver_identity_sha256),
            target_selector_configuration_sha256=(
                self._target_selector_configuration_sha256
            ),
        )

    @property
    def runtime_identity_sha256(
        self,
    ) -> str:
        return self._runtime_identity_sha256

    @property
    def runtime_model_sha256(
        self,
    ) -> str:
        return self._runtime_model_sha256

    @property
    def bound_subject_sha256(
        self,
    ) -> str:
        return self._bound_subject_sha256

    @property
    def target_selector_configuration_sha256(
        self,
    ) -> str:
        return self._target_selector_configuration_sha256

    def describe_target(
        self,
        module_path: str,
    ) -> InternalModuleTarget:
        module_path = _require_identifier(
            module_path,
            field="module_path",
        )

        try:
            return self._targets_by_path[module_path]

        except KeyError as exc:
            raise HveeContractError("unknown PyTorch runtime target") from exc

    def describe_capability(
        self,
    ) -> InternalRuntimeCapability:
        return InternalRuntimeCapability(
            runtime_key=(PYTORCH_INTERNAL_RUNTIME_KEY),
            runtime_version=(PYTORCH_INTERNAL_RUNTIME_VERSION),
            runtime_identity_sha256=(self._runtime_identity_sha256),
            runtime_model_sha256=(self._runtime_model_sha256),
            supported_interventions=(
                InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY,
                InternalInterventionKind.ZERO_MODULE_OUTPUT,
            ),
            raw_tensor_egress=False,
        )

    def _validate_request_target(
        self,
        request: InternalExperimentRequest,
    ) -> tuple[
        PyTorchTargetBinding,
        nn.Module,
    ]:
        if not isinstance(
            request,
            InternalExperimentRequest,
        ):
            raise HveeContractError("PyTorch runtime received invalid request type")

        if request.subject_sha256 != self._bound_subject_sha256:
            raise HveeContractError(
                "request subject does not match bound runtime subject"
            )

        if request.expected_runtime_identity_sha256 != self._runtime_identity_sha256:
            raise HveeContractError("request runtime identity does not match adapter")

        if request.expected_runtime_model_sha256 != self._runtime_model_sha256:
            raise HveeContractError("request model identity does not match adapter")

        if request.target.runtime_model_sha256 != self._runtime_model_sha256:
            raise HveeContractError(
                "request target model identity does not match adapter"
            )

        module_path = request.target.module_path

        try:
            binding = self._bindings_by_path[module_path]

            module = self._modules_by_path[module_path]

            expected_target = self._targets_by_path[module_path]

        except KeyError as exc:
            raise HveeContractError("request references unknown target module") from exc

        if request.target != expected_target:
            raise HveeContractError(
                "request target identity or metadata does not match frozen binding"
            )

        if request.intervention_kind not in (
            InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY,
            InternalInterventionKind.ZERO_MODULE_OUTPUT,
        ):
            raise HveeContractError("unsupported PyTorch runtime intervention")

        if self._model.training:
            raise HveeContractError(
                "model entered training mode after runtime construction"
            )

        return (
            binding,
            module,
        )

    def _run_target_pass(
        self,
        *,
        module: nn.Module,
        selector: PyTorchOutputSelector,
        zero_selected_tensor: bool,
    ) -> InternalActivationSummary:
        captured: list[InternalActivationSummary] = []

        def hook(
            _module: nn.Module,
            _inputs: tuple[
                object,
                ...,
            ],
            output: object,
        ) -> object | None:
            if captured:
                raise HveeContractError(
                    "target module executed more than once in a single driver pass"
                )

            selected = _select_output_tensor(
                output,
                selector,
            )

            if zero_selected_tensor:
                replacement = torch.zeros_like(selected)

                summary = _summarize_activation(replacement)

                captured.append(summary)

                return _replace_selected_tensor(
                    output,
                    selector,
                    replacement,
                )

            summary = _summarize_activation(selected)

            captured.append(summary)

            return None

        handle = module.register_forward_hook(hook)

        try:
            try:
                with torch.inference_mode():
                    self._execution_driver(self._model)

            except HveeContractError:
                raise

            except Exception as exc:
                raise HveeContractError("PyTorch execution driver failed") from exc

        finally:
            try:
                handle.remove()

            except Exception as exc:
                raise HveeContractError("PyTorch forward hook cleanup failed") from exc

        if len(captured) != 1:
            raise HveeContractError(
                "target module must execute exactly once per driver pass"
            )

        return captured[0]

    def execute(
        self,
        request: InternalExperimentRequest,
    ) -> InternalInterventionObservation:
        binding, module = self._validate_request_target(request)

        if (
            request.intervention_kind
            == InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY
        ):
            baseline = self._run_target_pass(
                module=module,
                selector=(binding.selector),
                zero_selected_tensor=False,
            )

            intervention = None
            actual_cost_units = 1
            outcome_key = "pytorch_activation_summary_captured"

        elif request.intervention_kind == InternalInterventionKind.ZERO_MODULE_OUTPUT:
            baseline = self._run_target_pass(
                module=module,
                selector=(binding.selector),
                zero_selected_tensor=False,
            )

            intervention = self._run_target_pass(
                module=module,
                selector=(binding.selector),
                zero_selected_tensor=True,
            )

            if (
                intervention.minimum != 0.0
                or intervention.maximum != 0.0
                or intervention.mean != 0.0
                or intervention.l2_norm != 0.0
            ):
                raise HveeContractError(
                    "zero-module intervention summary is not exactly zero"
                )

            actual_cost_units = 2
            outcome_key = "pytorch_module_output_zeroed"

        else:
            raise HveeContractError("unsupported PyTorch intervention")

        return build_internal_intervention_observation(
            status=(ExperimentObservationStatus.COMPLETED),
            outcome_key=(outcome_key),
            actual_cost_units=(actual_cost_units),
            runtime_identity_sha256=(self._runtime_identity_sha256),
            runtime_model_sha256=(self._runtime_model_sha256),
            target_identity_sha256=(request.target.target_identity_sha256),
            intervention_kind=(request.intervention_kind),
            baseline_identity_sha256=(request.baseline_identity_sha256),
            intervention_identity_sha256=(request.intervention_identity_sha256),
            baseline_activation=(baseline),
            intervention_activation=(intervention),
            raw_tensor_egress_performed=False,
        )
