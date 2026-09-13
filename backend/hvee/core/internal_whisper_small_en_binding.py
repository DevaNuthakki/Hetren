from __future__ import annotations

import re

from torch import nn

from hvee.core.contracts import HveeContractError
from hvee.core.internal_pytorch_runtime import (
    PyTorchExecutionDriver,
    PyTorchInternalRuntimeAdapter,
    PyTorchOutputSelector,
    PyTorchOutputSelectorStep,
    PyTorchOutputSelectorStepKind,
    PyTorchTargetBinding,
    calculate_pytorch_target_selector_configuration_sha256,
)


WHISPER_SMALL_EN_INTERNAL_BINDING_KEY = (
    "whisper_small_en_internal_binding"
)

WHISPER_SMALL_EN_INTERNAL_BINDING_VERSION = (
    "1.0.0-foundation"
)

WHISPER_SMALL_EN_MODEL_ID = "openai/whisper-small.en"

WHISPER_SMALL_EN_MODEL_REVISION = (
    "e8727524f962ee844a7319d92be39ac1bd25655a"
)

WHISPER_SMALL_EN_CONFIG_SHA256 = (
    "3441094addfb2a31ef62ea117e95bd6e437bbad8e93d3697fe420a4a6d3603a5"
)

WHISPER_SMALL_EN_MODEL_CLASS = (
    "WhisperForConditionalGeneration"
)

WHISPER_SMALL_EN_ENCODER_BLOCK_COUNT = 12
WHISPER_SMALL_EN_DECODER_BLOCK_COUNT = 12

WHISPER_SMALL_EN_D_MODEL = 768

WHISPER_SMALL_EN_ENCODER_ATTENTION_HEADS = 12
WHISPER_SMALL_EN_DECODER_ATTENTION_HEADS = 12

WHISPER_SMALL_EN_ENCODER_FFN_DIM = 3072
WHISPER_SMALL_EN_DECODER_FFN_DIM = 3072

WHISPER_SMALL_EN_ENCODER_BLOCK_PATH_PATTERN = (
    "model.encoder.layers.{index}"
)

WHISPER_SMALL_EN_DECODER_BLOCK_PATH_PATTERN = (
    "model.decoder.layers.{index}"
)

_MODULE_KIND = "transformer_block"

_ENCODER_DIRECT_PATH_RE = re.compile(
    r"^model\.encoder\.layers\.(\d+)$"
)

_DECODER_DIRECT_PATH_RE = re.compile(
    r"^model\.decoder\.layers\.(\d+)$"
)

_BLOCK_OUTPUT_SELECTOR = PyTorchOutputSelector(
    steps=(
        PyTorchOutputSelectorStep(
            kind=(
                PyTorchOutputSelectorStepKind.TUPLE_OR_LIST_INTEGER_INDEX
            ),
            index=0,
        ),
    )
)


def _require_exact_text(
    value: object,
    *,
    expected: str,
    field: str,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        raise HveeContractError(
            field + " must be a string"
        )

    if value != expected:
        raise HveeContractError(
            field + " does not match frozen authority"
        )

    return value


def _require_exact_config_value(
    config: object,
    *,
    attribute: str,
    expected: object,
) -> None:
    if not hasattr(
        config,
        attribute,
    ):
        raise HveeContractError(
            "model config is missing " + attribute
        )

    actual = getattr(
        config,
        attribute,
    )

    if actual != expected:
        raise HveeContractError(
            "model config "
            + attribute
            + " does not match frozen authority"
        )


def _expected_encoder_paths() -> tuple[str, ...]:
    return tuple(
        WHISPER_SMALL_EN_ENCODER_BLOCK_PATH_PATTERN.format(
            index=index,
        )
        for index in range(
            WHISPER_SMALL_EN_ENCODER_BLOCK_COUNT
        )
    )


def _expected_decoder_paths() -> tuple[str, ...]:
    return tuple(
        WHISPER_SMALL_EN_DECODER_BLOCK_PATH_PATTERN.format(
            index=index,
        )
        for index in range(
            WHISPER_SMALL_EN_DECODER_BLOCK_COUNT
        )
    )


def _validate_preloaded_model_structure(
    model: nn.Module,
) -> dict[str, nn.Module]:
    if not isinstance(
        model,
        nn.Module,
    ):
        raise HveeContractError(
            "model must be a torch.nn.Module"
        )

    if (
        model.__class__.__name__
        != WHISPER_SMALL_EN_MODEL_CLASS
    ):
        raise HveeContractError(
            "model class does not match frozen Whisper authority"
        )

    config = getattr(
        model,
        "config",
        None,
    )

    if config is None:
        raise HveeContractError(
            "preloaded Whisper model is missing config"
        )

    _require_exact_config_value(
        config,
        attribute="model_type",
        expected="whisper",
    )

    _require_exact_config_value(
        config,
        attribute="architectures",
        expected=[
            WHISPER_SMALL_EN_MODEL_CLASS,
        ],
    )

    _require_exact_config_value(
        config,
        attribute="encoder_layers",
        expected=(
            WHISPER_SMALL_EN_ENCODER_BLOCK_COUNT
        ),
    )

    _require_exact_config_value(
        config,
        attribute="decoder_layers",
        expected=(
            WHISPER_SMALL_EN_DECODER_BLOCK_COUNT
        ),
    )

    _require_exact_config_value(
        config,
        attribute="d_model",
        expected=WHISPER_SMALL_EN_D_MODEL,
    )

    _require_exact_config_value(
        config,
        attribute="encoder_attention_heads",
        expected=(
            WHISPER_SMALL_EN_ENCODER_ATTENTION_HEADS
        ),
    )

    _require_exact_config_value(
        config,
        attribute="decoder_attention_heads",
        expected=(
            WHISPER_SMALL_EN_DECODER_ATTENTION_HEADS
        ),
    )

    _require_exact_config_value(
        config,
        attribute="encoder_ffn_dim",
        expected=WHISPER_SMALL_EN_ENCODER_FFN_DIM,
    )

    _require_exact_config_value(
        config,
        attribute="decoder_ffn_dim",
        expected=WHISPER_SMALL_EN_DECODER_FFN_DIM,
    )

    named_modules = list(
        model.named_modules()
    )

    names = [
        name
        for name, _module
        in named_modules
    ]

    if len(names) != len(set(names)):
        raise HveeContractError(
            "model named_modules contains duplicate paths"
        )

    module_by_path = dict(
        named_modules
    )

    expected_encoder_paths = (
        _expected_encoder_paths()
    )

    expected_decoder_paths = (
        _expected_decoder_paths()
    )

    direct_encoder_paths = tuple(
        sorted(
            (
                name
                for name in names
                if _ENCODER_DIRECT_PATH_RE.fullmatch(
                    name
                )
            ),
            key=lambda name: int(
                name.rsplit(
                    ".",
                    1,
                )[1]
            ),
        )
    )

    direct_decoder_paths = tuple(
        sorted(
            (
                name
                for name in names
                if _DECODER_DIRECT_PATH_RE.fullmatch(
                    name
                )
            ),
            key=lambda name: int(
                name.rsplit(
                    ".",
                    1,
                )[1]
            ),
        )
    )

    if (
        direct_encoder_paths
        != expected_encoder_paths
    ):
        raise HveeContractError(
            "encoder block paths do not match frozen authority"
        )

    if (
        direct_decoder_paths
        != expected_decoder_paths
    ):
        raise HveeContractError(
            "decoder block paths do not match frozen authority"
        )

    for path in expected_encoder_paths:
        module = module_by_path.get(
            path
        )

        if module is None:
            raise HveeContractError(
                "expected encoder block is missing: "
                + path
            )

        if (
            module.__class__.__name__
            != "WhisperEncoderLayer"
        ):
            raise HveeContractError(
                "encoder block class does not match frozen authority: "
                + path
            )

    for path in expected_decoder_paths:
        module = module_by_path.get(
            path
        )

        if module is None:
            raise HveeContractError(
                "expected decoder block is missing: "
                + path
            )

        if (
            module.__class__.__name__
            != "WhisperDecoderLayer"
        ):
            raise HveeContractError(
                "decoder block class does not match frozen authority: "
                + path
            )

    return module_by_path


def build_whisper_small_en_target_bindings(
    *,
    model: nn.Module,
) -> tuple[
    PyTorchTargetBinding,
    ...,
]:
    _validate_preloaded_model_structure(
        model
    )

    encoder_bindings = tuple(
        PyTorchTargetBinding(
            module_path=(
                WHISPER_SMALL_EN_ENCODER_BLOCK_PATH_PATTERN.format(
                    index=index,
                )
            ),
            module_kind=_MODULE_KIND,
            selector=_BLOCK_OUTPUT_SELECTOR,
            module_index=index,
            head_index=None,
        )
        for index in range(
            WHISPER_SMALL_EN_ENCODER_BLOCK_COUNT
        )
    )

    decoder_bindings = tuple(
        PyTorchTargetBinding(
            module_path=(
                WHISPER_SMALL_EN_DECODER_BLOCK_PATH_PATTERN.format(
                    index=index,
                )
            ),
            module_kind=_MODULE_KIND,
            selector=_BLOCK_OUTPUT_SELECTOR,
            module_index=index,
            head_index=None,
        )
        for index in range(
            WHISPER_SMALL_EN_DECODER_BLOCK_COUNT
        )
    )

    bindings = (
        encoder_bindings
        + decoder_bindings
    )

    if len(bindings) != 24:
        raise HveeContractError(
            "Whisper target binding count is not exactly 24"
        )

    return bindings


def calculate_whisper_small_en_selector_configuration_sha256(
    *,
    model: nn.Module,
) -> str:
    return (
        calculate_pytorch_target_selector_configuration_sha256(
            build_whisper_small_en_target_bindings(
                model=model,
            )
        )
    )


def build_whisper_small_en_internal_runtime_adapter(
    *,
    model: nn.Module,
    model_revision: str,
    model_config_sha256: str,
    runtime_model_sha256: str,
    bound_subject_sha256: str,
    execution_driver: PyTorchExecutionDriver,
    execution_driver_identity_sha256: str,
) -> PyTorchInternalRuntimeAdapter:
    _require_exact_text(
        model_revision,
        expected=(
            WHISPER_SMALL_EN_MODEL_REVISION
        ),
        field="model_revision",
    )

    _require_exact_text(
        model_config_sha256,
        expected=(
            WHISPER_SMALL_EN_CONFIG_SHA256
        ),
        field="model_config_sha256",
    )

    target_bindings = (
        build_whisper_small_en_target_bindings(
            model=model,
        )
    )

    return PyTorchInternalRuntimeAdapter(
        model=model,
        runtime_model_sha256=(
            runtime_model_sha256
        ),
        bound_subject_sha256=(
            bound_subject_sha256
        ),
        execution_driver=(
            execution_driver
        ),
        execution_driver_identity_sha256=(
            execution_driver_identity_sha256
        ),
        target_bindings=(
            target_bindings
        ),
    )
