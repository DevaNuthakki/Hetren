from __future__ import annotations

from dataclasses import replace
import hashlib
import math
import unittest

import torch
from torch import nn

from hvee.core.contracts import HveeContractError
from hvee.core.internal_engine import (
    InternalExperimentRequest,
    InternalInterventionKind,
    execute_internal_experiment,
    verify_internal_engine_execution_bundle,
)
from hvee.core.internal_pytorch_runtime import (
    PYTORCH_INTERNAL_RUNTIME_KEY,
    PYTORCH_INTERNAL_RUNTIME_VERSION,
    PyTorchInternalRuntimeAdapter,
    PyTorchOutputSelector,
    PyTorchOutputSelectorStep,
    PyTorchOutputSelectorStepKind,
    PyTorchTargetBinding,
)


def digest(
    value: str,
) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


SUBJECT_SHA = digest("synthetic-subject-v1")

MODEL_SHA = digest("synthetic-model-v1")

DRIVER_SHA = digest("synthetic-driver-v1")

BASELINE_SHA = digest("synthetic-baseline-v1")

SOURCE_SHA = digest("synthetic-source-evidence-v1")


def root_selector():
    return PyTorchOutputSelector(
        steps=(
            PyTorchOutputSelectorStep(kind=(PyTorchOutputSelectorStepKind.ROOT_TENSOR)),
        )
    )


def tuple_selector(
    index=0,
):
    return PyTorchOutputSelector(
        steps=(
            PyTorchOutputSelectorStep(
                kind=(PyTorchOutputSelectorStepKind.TUPLE_OR_LIST_INTEGER_INDEX),
                index=index,
            ),
        )
    )


def dict_selector(
    key="hidden",
):
    return PyTorchOutputSelector(
        steps=(
            PyTorchOutputSelectorStep(
                kind=(PyTorchOutputSelectorStepKind.DICT_STRING_KEY),
                key=key,
            ),
        )
    )


class TensorBlock(nn.Module):
    def __init__(
        self,
    ):
        super().__init__()

        self.linear = nn.Linear(
            4,
            4,
            bias=False,
        )

        with torch.no_grad():
            self.linear.weight.copy_(torch.eye(4))

    def forward(
        self,
        value,
    ):
        return self.linear(value) * 2.0


class TupleBlock(nn.Module):
    def forward(
        self,
        value,
    ):
        return (
            value * 3.0,
            value.mean(),
        )


class DictBlock(nn.Module):
    def forward(
        self,
        value,
    ):
        return {
            "hidden": (value * 4.0),
            "aux": (value.sum()),
        }


class ToyModel(nn.Module):
    def __init__(
        self,
    ):
        super().__init__()

        self.tensor_block = TensorBlock()

        self.tuple_block = TupleBlock()

        self.dict_block = DictBlock()

    def forward(
        self,
        value,
    ):
        value = self.tensor_block(value)

        value = self.tuple_block(value)

        value = self.dict_block(value[0])

        return value["hidden"]


class Driver:
    def __init__(
        self,
        *,
        fail=False,
        double=False,
    ):
        self.fail = fail
        self.double = double
        self.calls = 0
        self.outputs = []

        self.input = torch.tensor(
            [
                [
                    1.0,
                    -2.0,
                    3.0,
                    4.0,
                ],
                [
                    -1.0,
                    2.0,
                    0.5,
                    -0.25,
                ],
            ],
            dtype=torch.float32,
        )

    def __call__(
        self,
        model,
    ):
        self.calls += 1

        if self.fail:
            raise RuntimeError("synthetic driver failure")

        output = model(self.input)

        self.outputs.append(output.detach().clone())

        if self.double:
            model(self.input)

        return output


def bindings():
    return (
        PyTorchTargetBinding(
            module_path=("tensor_block"),
            module_kind=("transformer_block"),
            selector=(root_selector()),
            module_index=0,
        ),
        PyTorchTargetBinding(
            module_path=("tuple_block"),
            module_kind=("transformer_block"),
            selector=(tuple_selector()),
            module_index=1,
        ),
        PyTorchTargetBinding(
            module_path=("dict_block"),
            module_kind=("transformer_block"),
            selector=(dict_selector()),
            module_index=2,
        ),
    )


def make_adapter(
    *,
    model=None,
    driver=None,
    target_bindings=None,
):
    if model is None:
        model = ToyModel()

    model.eval()

    if driver is None:
        driver = Driver()

    if target_bindings is None:
        target_bindings = bindings()

    adapter = PyTorchInternalRuntimeAdapter(
        model=model,
        runtime_model_sha256=(MODEL_SHA),
        bound_subject_sha256=(SUBJECT_SHA),
        execution_driver=(driver),
        execution_driver_identity_sha256=(DRIVER_SHA),
        target_bindings=(target_bindings),
    )

    return (
        model,
        driver,
        adapter,
    )


def make_request(
    adapter,
    *,
    module_path="tensor_block",
    intervention=(InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY),
):
    target = adapter.describe_target(module_path)

    cost = (
        1
        if (intervention == InternalInterventionKind.CAPTURE_ACTIVATION_SUMMARY)
        else 2
    )

    return InternalExperimentRequest(
        request_key=("pytorch-runtime-test:" + module_path + ":" + intervention.value),
        request_version="1.0.0",
        campaign_key=("internal-pytorch-runtime-test"),
        campaign_version="1.0.0",
        subject_sha256=(SUBJECT_SHA),
        expected_runtime_identity_sha256=(adapter.runtime_identity_sha256),
        expected_runtime_model_sha256=(MODEL_SHA),
        target=target,
        intervention_kind=(intervention),
        baseline_identity_sha256=(BASELINE_SHA),
        intervention_identity_sha256=(digest(module_path + ":" + intervention.value)),
        estimated_cost_units=(cost),
        maximum_experiments=1,
        maximum_cost_units=2,
        reason_code=("synthetic_pytorch_probe"),
        source_evidence_sha256=(SOURCE_SHA),
    )


class InternalPyTorchRuntimeTests(unittest.TestCase):
    def test_runtime_identity_constants(
        self,
    ):
        self.assertEqual(
            PYTORCH_INTERNAL_RUNTIME_KEY,
            "pytorch_internal_runtime",
        )

        self.assertEqual(
            PYTORCH_INTERNAL_RUNTIME_VERSION,
            "1.0.0-foundation",
        )

    def test_capability_is_exactly_frozen(
        self,
    ):
        _, _, adapter = make_adapter()

        capability = adapter.describe_capability()

        self.assertEqual(
            capability.runtime_key,
            "pytorch_internal_runtime",
        )

        self.assertEqual(
            capability.runtime_version,
            "1.0.0-foundation",
        )

        self.assertEqual(
            capability.runtime_model_sha256,
            MODEL_SHA,
        )

        self.assertFalse(capability.raw_tensor_egress)

    def test_capture_root_tensor_uses_one_forward_pass(
        self,
    ):
        _, driver, adapter = make_adapter()

        request = make_request(adapter)

        bundle = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        self.assertEqual(
            driver.calls,
            1,
        )

        observation = bundle.payload["result"]["observation"]

        self.assertEqual(
            observation["actual_cost_units"],
            1,
        )

        self.assertIsNone(observation["intervention_activation"])

        self.assertFalse(observation["raw_tensor_egress_performed"])

        self.assertTrue(
            verify_internal_engine_execution_bundle(
                bundle.payload,
                bundle.sha256,
            )
        )

    def test_zero_ablation_uses_two_forward_passes(
        self,
    ):
        _, driver, adapter = make_adapter()

        request = make_request(
            adapter,
            intervention=(InternalInterventionKind.ZERO_MODULE_OUTPUT),
        )

        bundle = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        self.assertEqual(
            driver.calls,
            2,
        )

        observation = bundle.payload["result"]["observation"]

        self.assertEqual(
            observation["actual_cost_units"],
            2,
        )

        intervention = observation["intervention_activation"]

        self.assertEqual(
            intervention["minimum"],
            0.0,
        )

        self.assertEqual(
            intervention["maximum"],
            0.0,
        )

        self.assertEqual(
            intervention["mean"],
            0.0,
        )

        self.assertEqual(
            intervention["l2_norm"],
            0.0,
        )

        self.assertFalse(
            torch.equal(
                driver.outputs[0],
                driver.outputs[1],
            )
        )

    def test_tuple_selector_executes(
        self,
    ):
        _, _, adapter = make_adapter()

        request = make_request(
            adapter,
            module_path=("tuple_block"),
        )

        bundle = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        observation = bundle.payload["result"]["observation"]

        self.assertEqual(
            observation["baseline_activation"]["shape"],
            [
                2,
                4,
            ],
        )

    def test_dict_selector_executes(
        self,
    ):
        _, _, adapter = make_adapter()

        request = make_request(
            adapter,
            module_path=("dict_block"),
        )

        bundle = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        observation = bundle.payload["result"]["observation"]

        self.assertEqual(
            observation["baseline_activation"]["shape"],
            [
                2,
                4,
            ],
        )

    def test_zero_ablation_preserves_model_parameters(
        self,
    ):
        model, _, adapter = make_adapter()

        before = {
            key: value.detach().clone() for key, value in model.state_dict().items()
        }

        request = make_request(
            adapter,
            intervention=(InternalInterventionKind.ZERO_MODULE_OUTPUT),
        )

        execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        after = model.state_dict()

        self.assertEqual(
            set(before),
            set(after),
        )

        for key in before:
            self.assertTrue(
                torch.equal(
                    before[key],
                    after[key],
                )
            )

    def test_hooks_removed_after_success(
        self,
    ):
        model, _, adapter = make_adapter()

        request = make_request(adapter)

        execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        self.assertEqual(
            len(model.tensor_block._forward_hooks),
            0,
        )

    def test_hooks_removed_after_driver_failure(
        self,
    ):
        driver = Driver(fail=True)

        model, _, adapter = make_adapter(driver=driver)

        request = make_request(adapter)

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            len(model.tensor_block._forward_hooks),
            0,
        )

    def test_multiple_target_invocations_fail_closed_and_cleanup(
        self,
    ):
        driver = Driver(double=True)

        model, _, adapter = make_adapter(driver=driver)

        request = make_request(adapter)

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            len(model.tensor_block._forward_hooks),
            0,
        )

    def test_subject_mismatch_fails_before_forward(
        self,
    ):
        _, driver, adapter = make_adapter()

        request = make_request(adapter)

        request = replace(
            request,
            subject_sha256=(digest("other-subject")),
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            driver.calls,
            0,
        )

    def test_target_identity_mismatch_fails_before_forward(
        self,
    ):
        _, driver, adapter = make_adapter()

        request = make_request(adapter)

        request = replace(
            request,
            target=replace(
                request.target,
                target_identity_sha256=(digest("tampered-target")),
            ),
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            driver.calls,
            0,
        )

    def test_unknown_target_fails_closed(
        self,
    ):
        _, _, adapter = make_adapter()

        with self.assertRaises(HveeContractError):
            adapter.describe_target("unknown.block")

    def test_model_must_be_eval_mode(
        self,
    ):
        model = ToyModel()

        self.assertTrue(model.training)

        with self.assertRaises(HveeContractError):
            PyTorchInternalRuntimeAdapter(
                model=model,
                runtime_model_sha256=(MODEL_SHA),
                bound_subject_sha256=(SUBJECT_SHA),
                execution_driver=(Driver()),
                execution_driver_identity_sha256=(DRIVER_SHA),
                target_bindings=(bindings()),
            )

    def test_runtime_identity_changes_with_selector_configuration(
        self,
    ):
        _, _, first = make_adapter()

        altered = list(bindings())

        altered[1] = replace(
            altered[1],
            selector=(tuple_selector(index=1)),
        )

        _, _, second = make_adapter(target_bindings=tuple(altered))

        self.assertNotEqual(
            first.runtime_identity_sha256,
            second.runtime_identity_sha256,
        )

    def test_execution_is_exactly_replayable(
        self,
    ):
        _, _, adapter = make_adapter()

        request = make_request(
            adapter,
            module_path=("dict_block"),
            intervention=(InternalInterventionKind.ZERO_MODULE_OUTPUT),
        )

        first = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        second = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        self.assertEqual(
            first,
            second,
        )

    def test_no_tensor_objects_persist_in_execution_bundle(
        self,
    ):
        _, _, adapter = make_adapter()

        request = make_request(adapter)

        bundle = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        def visit(
            value,
        ):
            self.assertFalse(
                isinstance(
                    value,
                    torch.Tensor,
                )
            )

            if isinstance(
                value,
                dict,
            ):
                for item in value.values():
                    visit(item)

            elif isinstance(
                value,
                (
                    list,
                    tuple,
                ),
            ):
                for item in value:
                    visit(item)

        visit(bundle.payload)

    def test_activation_commitment_is_content_sensitive(
        self,
    ):
        _, _, adapter = make_adapter()

        request = make_request(adapter)

        first = execute_internal_experiment(
            request=request,
            runtime_adapter=adapter,
        )

        first_commitment = first.payload["result"]["observation"][
            "baseline_activation"
        ]["activation_commitment_sha256"]

        model = ToyModel()

        with torch.no_grad():
            model.tensor_block.linear.weight.mul_(2.0)

        model.eval()

        driver = Driver()

        changed_adapter = PyTorchInternalRuntimeAdapter(
            model=model,
            runtime_model_sha256=(MODEL_SHA),
            bound_subject_sha256=(SUBJECT_SHA),
            execution_driver=(driver),
            execution_driver_identity_sha256=(DRIVER_SHA),
            target_bindings=(bindings()),
        )

        changed_request = make_request(changed_adapter)

        changed = execute_internal_experiment(
            request=(changed_request),
            runtime_adapter=(changed_adapter),
        )

        changed_commitment = changed.payload["result"]["observation"][
            "baseline_activation"
        ]["activation_commitment_sha256"]

        self.assertNotEqual(
            first_commitment,
            changed_commitment,
        )

    def test_nonfinite_activation_fails_closed(
        self,
    ):
        class NonFiniteBlock(nn.Module):
            def forward(
                self,
                value,
            ):
                result = value.clone()

                result[
                    0,
                    0,
                ] = float("inf")

                return result

        class Model(nn.Module):
            def __init__(
                self,
            ):
                super().__init__()

                self.block = NonFiniteBlock()

            def forward(
                self,
                value,
            ):
                return self.block(value)

        model = Model()
        model.eval()

        driver = Driver()

        adapter = PyTorchInternalRuntimeAdapter(
            model=model,
            runtime_model_sha256=(MODEL_SHA),
            bound_subject_sha256=(SUBJECT_SHA),
            execution_driver=(driver),
            execution_driver_identity_sha256=(DRIVER_SHA),
            target_bindings=(
                (
                    PyTorchTargetBinding(
                        module_path=("block"),
                        module_kind=("synthetic"),
                        selector=(root_selector()),
                    ),
                )
            ),
        )

        request = make_request(
            adapter,
            module_path=("block"),
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            len(model.block._forward_hooks),
            0,
        )

    def test_root_selector_rejects_structured_output(
        self,
    ):
        altered = list(bindings())

        altered[1] = replace(
            altered[1],
            selector=(root_selector()),
        )

        model, _, adapter = make_adapter(target_bindings=tuple(altered))

        request = make_request(
            adapter,
            module_path=("tuple_block"),
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            len(model.tuple_block._forward_hooks),
            0,
        )

    def test_missing_dict_key_fails_closed(
        self,
    ):
        altered = list(bindings())

        altered[2] = replace(
            altered[2],
            selector=(dict_selector(key="missing")),
        )

        model, _, adapter = make_adapter(target_bindings=tuple(altered))

        request = make_request(
            adapter,
            module_path=("dict_block"),
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

        self.assertEqual(
            len(model.dict_block._forward_hooks),
            0,
        )

    def test_scalar_activation_fails_closed(
        self,
    ):
        class ScalarBlock(nn.Module):
            def forward(
                self,
                value,
            ):
                return value.mean()

        class Model(nn.Module):
            def __init__(
                self,
            ):
                super().__init__()

                self.block = ScalarBlock()

            def forward(
                self,
                value,
            ):
                return self.block(value)

        model = Model()
        model.eval()

        driver = Driver()

        adapter = PyTorchInternalRuntimeAdapter(
            model=model,
            runtime_model_sha256=(MODEL_SHA),
            bound_subject_sha256=(SUBJECT_SHA),
            execution_driver=(driver),
            execution_driver_identity_sha256=(DRIVER_SHA),
            target_bindings=(
                (
                    PyTorchTargetBinding(
                        module_path=("block"),
                        module_kind=("synthetic"),
                        selector=(root_selector()),
                    ),
                )
            ),
        )

        request = make_request(
            adapter,
            module_path="block",
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=request,
                runtime_adapter=adapter,
            )

    def test_integer_activation_fails_closed(
        self,
    ):
        class IntegerBlock(nn.Module):
            def forward(
                self,
                value,
            ):
                return torch.ones(
                    (
                        2,
                        4,
                    ),
                    dtype=torch.int64,
                )

        class Model(nn.Module):
            def __init__(
                self,
            ):
                super().__init__()

                self.block = IntegerBlock()

            def forward(
                self,
                value,
            ):
                return self.block(value)

        model = Model()
        model.eval()

        adapter = PyTorchInternalRuntimeAdapter(
            model=model,
            runtime_model_sha256=(MODEL_SHA),
            bound_subject_sha256=(SUBJECT_SHA),
            execution_driver=(Driver()),
            execution_driver_identity_sha256=(DRIVER_SHA),
            target_bindings=(
                (
                    PyTorchTargetBinding(
                        module_path="block",
                        module_kind="synthetic",
                        selector=(root_selector()),
                    ),
                )
            ),
        )

        with self.assertRaises(HveeContractError):
            execute_internal_experiment(
                request=(
                    make_request(
                        adapter,
                        module_path="block",
                    )
                ),
                runtime_adapter=adapter,
            )

    def test_summary_statistics_are_finite(
        self,
    ):
        _, _, adapter = make_adapter()

        bundle = execute_internal_experiment(
            request=(make_request(adapter)),
            runtime_adapter=adapter,
        )

        summary = bundle.payload["result"]["observation"]["baseline_activation"]

        for field in (
            "minimum",
            "maximum",
            "mean",
            "l2_norm",
        ):
            self.assertTrue(math.isfinite(summary[field]))


if __name__ == "__main__":
    unittest.main()
