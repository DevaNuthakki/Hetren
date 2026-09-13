from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest

import torch
from torch import nn

from transformers import (
    WhisperConfig,
    WhisperForConditionalGeneration as TransformersWhisperForConditionalGeneration,
)

from hvee.core.contracts import HveeContractError
from hvee.core.internal_pytorch_runtime import (
    PyTorchOutputSelectorStepKind,
    calculate_pytorch_target_selector_configuration_sha256,
)
from hvee.core.internal_whisper_small_en_binding import (
    WHISPER_SMALL_EN_CONFIG_SHA256,
    WHISPER_SMALL_EN_DECODER_BLOCK_COUNT,
    WHISPER_SMALL_EN_DECODER_BLOCK_PATH_PATTERN,
    WHISPER_SMALL_EN_ENCODER_BLOCK_COUNT,
    WHISPER_SMALL_EN_ENCODER_BLOCK_PATH_PATTERN,
    WHISPER_SMALL_EN_INTERNAL_BINDING_KEY,
    WHISPER_SMALL_EN_INTERNAL_BINDING_VERSION,
    WHISPER_SMALL_EN_MODEL_ID,
    WHISPER_SMALL_EN_MODEL_REVISION,
    build_whisper_small_en_internal_runtime_adapter,
    build_whisper_small_en_target_bindings,
    calculate_whisper_small_en_selector_configuration_sha256,
)


def digest(
    value: str,
) -> str:
    return hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()


MODEL_SHA = digest(
    "whisper-binding-synthetic-model-v1"
)

SUBJECT_SHA = digest(
    "whisper-binding-synthetic-subject-v1"
)

DRIVER_SHA = digest(
    "whisper-binding-synthetic-driver-v1"
)


class Driver:
    def __init__(
        self,
    ):
        self.calls = 0

    def __call__(
        self,
        model,
    ):
        self.calls += 1

        raise AssertionError(
            "binding construction must not execute the model"
        )


class WhisperEncoderLayer(
    nn.Module,
):
    pass


class WhisperDecoderLayer(
    nn.Module,
):
    pass


class WhisperForConditionalGeneration(
    nn.Module,
):
    def __init__(
        self,
        *,
        encoder_count=12,
        decoder_count=12,
        config_encoder_layers=12,
        config_decoder_layers=12,
        d_model=768,
    ):
        super().__init__()

        self.config = SimpleNamespace(
            model_type="whisper",
            architectures=[
                "WhisperForConditionalGeneration",
            ],
            encoder_layers=(
                config_encoder_layers
            ),
            decoder_layers=(
                config_decoder_layers
            ),
            d_model=d_model,
            encoder_attention_heads=12,
            decoder_attention_heads=12,
            encoder_ffn_dim=3072,
            decoder_ffn_dim=3072,
        )

        self.model = nn.Module()

        self.model.encoder = nn.Module()
        self.model.decoder = nn.Module()

        self.model.encoder.layers = (
            nn.ModuleList(
                WhisperEncoderLayer()
                for _ in range(
                    encoder_count
                )
            )
        )

        self.model.decoder.layers = (
            nn.ModuleList(
                WhisperDecoderLayer()
                for _ in range(
                    decoder_count
                )
            )
        )


def make_actual_meta_model():
    config = WhisperConfig(
        encoder_layers=12,
        decoder_layers=12,
        d_model=768,
        encoder_attention_heads=12,
        decoder_attention_heads=12,
        encoder_ffn_dim=3072,
        decoder_ffn_dim=3072,
    )

    config.architectures = [
        "WhisperForConditionalGeneration",
    ]

    with torch.device("meta"):
        model = (
            TransformersWhisperForConditionalGeneration(
                config
            )
        )

    # The sealed PyTorch runtime requires a preloaded
    # subject model to already be in evaluation mode.
    # Binding construction must not silently change
    # caller-owned model execution state.
    model.eval()

    return model


class InternalWhisperSmallEnBindingTests(
    unittest.TestCase,
):
    @classmethod
    def setUpClass(
        cls,
    ):
        cls.actual_meta_model = (
            make_actual_meta_model()
        )

    def test_binding_identity_constants_are_frozen(
        self,
    ):
        self.assertEqual(
            WHISPER_SMALL_EN_INTERNAL_BINDING_KEY,
            "whisper_small_en_internal_binding",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_INTERNAL_BINDING_VERSION,
            "1.0.0-foundation",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_MODEL_ID,
            "openai/whisper-small.en",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_MODEL_REVISION,
            "e8727524f962ee844a7319d92be39ac1bd25655a",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_CONFIG_SHA256,
            "3441094addfb2a31ef62ea117e95bd6e437bbad8e93d3697fe420a4a6d3603a5",
        )

        self.assertEqual(
            WHISPER_SMALL_EN_ENCODER_BLOCK_COUNT,
            12,
        )

        self.assertEqual(
            WHISPER_SMALL_EN_DECODER_BLOCK_COUNT,
            12,
        )

    def test_actual_transformers_meta_model_has_exact_24_bindings(
        self,
    ):
        model = self.actual_meta_model

        self.assertTrue(
            all(
                parameter.is_meta
                for parameter
                in model.parameters()
            )
        )

        bindings = (
            build_whisper_small_en_target_bindings(
                model=model,
            )
        )

        self.assertEqual(
            len(bindings),
            24,
        )

        expected_paths = (
            tuple(
                WHISPER_SMALL_EN_ENCODER_BLOCK_PATH_PATTERN.format(
                    index=index,
                )
                for index in range(12)
            )
            + tuple(
                WHISPER_SMALL_EN_DECODER_BLOCK_PATH_PATTERN.format(
                    index=index,
                )
                for index in range(12)
            )
        )

        self.assertEqual(
            tuple(
                binding.module_path
                for binding in bindings
            ),
            expected_paths,
        )

        for binding in bindings:
            self.assertEqual(
                binding.module_kind,
                "transformer_block",
            )

            self.assertIsNone(
                binding.head_index
            )

            self.assertEqual(
                len(binding.selector.steps),
                1,
            )

            step = binding.selector.steps[0]

            self.assertEqual(
                step.kind,
                PyTorchOutputSelectorStepKind.TUPLE_OR_LIST_INTEGER_INDEX,
            )

            self.assertEqual(
                step.index,
                0,
            )

            self.assertIsNone(
                step.key
            )

    def test_selector_configuration_is_deterministic_and_public_adapter_owned(
        self,
    ):
        model = self.actual_meta_model

        bindings = (
            build_whisper_small_en_target_bindings(
                model=model,
            )
        )

        direct = (
            calculate_pytorch_target_selector_configuration_sha256(
                bindings
            )
        )

        wrapped = (
            calculate_whisper_small_en_selector_configuration_sha256(
                model=model,
            )
        )

        replay = (
            calculate_whisper_small_en_selector_configuration_sha256(
                model=model,
            )
        )

        self.assertEqual(
            direct,
            wrapped,
        )

        self.assertEqual(
            wrapped,
            replay,
        )

        self.assertEqual(
            len(wrapped),
            64,
        )

    def test_build_adapter_uses_preloaded_model_without_execution(
        self,
    ):
        model = self.actual_meta_model

        driver = Driver()

        adapter = (
            build_whisper_small_en_internal_runtime_adapter(
                model=model,
                model_revision=(
                    WHISPER_SMALL_EN_MODEL_REVISION
                ),
                model_config_sha256=(
                    WHISPER_SMALL_EN_CONFIG_SHA256
                ),
                runtime_model_sha256=(
                    MODEL_SHA
                ),
                bound_subject_sha256=(
                    SUBJECT_SHA
                ),
                execution_driver=(
                    driver
                ),
                execution_driver_identity_sha256=(
                    DRIVER_SHA
                ),
            )
        )

        self.assertEqual(
            driver.calls,
            0,
        )

        encoder_target = adapter.describe_target(
            "model.encoder.layers.0"
        )

        decoder_target = adapter.describe_target(
            "model.decoder.layers.11"
        )

        self.assertEqual(
            encoder_target.module_index,
            0,
        )

        self.assertEqual(
            decoder_target.module_index,
            11,
        )

        self.assertEqual(
            encoder_target.runtime_model_sha256,
            MODEL_SHA,
        )

        self.assertEqual(
            decoder_target.runtime_model_sha256,
            MODEL_SHA,
        )

        self.assertFalse(
            adapter.describe_capability().raw_tensor_egress
        )

    def test_wrong_model_revision_fails_closed(
        self,
    ):
        with self.assertRaises(
            HveeContractError
        ):
            build_whisper_small_en_internal_runtime_adapter(
                model=self.actual_meta_model,
                model_revision=(
                    "0" * 40
                ),
                model_config_sha256=(
                    WHISPER_SMALL_EN_CONFIG_SHA256
                ),
                runtime_model_sha256=(
                    MODEL_SHA
                ),
                bound_subject_sha256=(
                    SUBJECT_SHA
                ),
                execution_driver=Driver(),
                execution_driver_identity_sha256=(
                    DRIVER_SHA
                ),
            )

    def test_wrong_config_identity_fails_closed(
        self,
    ):
        with self.assertRaises(
            HveeContractError
        ):
            build_whisper_small_en_internal_runtime_adapter(
                model=self.actual_meta_model,
                model_revision=(
                    WHISPER_SMALL_EN_MODEL_REVISION
                ),
                model_config_sha256=(
                    "0" * 64
                ),
                runtime_model_sha256=(
                    MODEL_SHA
                ),
                bound_subject_sha256=(
                    SUBJECT_SHA
                ),
                execution_driver=Driver(),
                execution_driver_identity_sha256=(
                    DRIVER_SHA
                ),
            )

    def test_wrong_root_model_class_fails_closed(
        self,
    ):
        class WrongModel(
            nn.Module,
        ):
            pass

        with self.assertRaises(
            HveeContractError
        ):
            build_whisper_small_en_target_bindings(
                model=WrongModel()
            )

    def test_missing_encoder_block_fails_closed(
        self,
    ):
        model = WhisperForConditionalGeneration(
            encoder_count=11,
        )

        with self.assertRaises(
            HveeContractError
        ):
            build_whisper_small_en_target_bindings(
                model=model
            )

    def test_unexpected_decoder_block_fails_closed(
        self,
    ):
        model = WhisperForConditionalGeneration(
            decoder_count=13,
        )

        with self.assertRaises(
            HveeContractError
        ):
            build_whisper_small_en_target_bindings(
                model=model
            )

    def test_config_architecture_drift_fails_closed(
        self,
    ):
        model = WhisperForConditionalGeneration(
            d_model=512,
        )

        with self.assertRaises(
            HveeContractError
        ):
            build_whisper_small_en_target_bindings(
                model=model
            )

    def test_binding_source_has_no_model_loading_or_network_client(
        self,
    ):
        import hvee.core.internal_whisper_small_en_binding as binding_module

        source = Path(
            binding_module.__file__
        ).read_text(
            encoding="utf-8"
        )

        forbidden = (
            "from_pretrained",
            "hf_hub_download",
            "snapshot_download",
            "huggingface_hub",
            "requests.",
            "urllib.",
            "WhisperProcessor",
            "WhisperFeatureExtractor",
            "WhisperTokenizer",
        )

        for token in forbidden:
            with self.subTest(
                token=token
            ):
                self.assertNotIn(
                    token,
                    source,
                )


if __name__ == "__main__":
    unittest.main()
