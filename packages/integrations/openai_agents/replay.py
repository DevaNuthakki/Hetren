"""Capture and replay of model responses behind the SDK ``Model`` interface.

Replay key
----------
A ``ReplayKey`` is derived from one ``Model.get_response`` call. Its
components are:

- ``model``: the source model identity and its non-None settings;
- ``system_instructions``: the system prompt text;
- ``input_items``: the transcript with SDK/provider item ``id`` fields
  removed, ``call_id`` values replaced by first-appearance ordinals, and
  tool outputs replaced by ``{"observation_ref": n}``;
- ``prior_observations``: digests of every tool output, in order;
- ``tool_definitions``: name, description, schema, and strictness;
- ``output_schema``, ``handoffs``, ``prompt``.

``previous_response_id``, ``conversation_id``, tracing, item IDs, call IDs,
and timestamps are excluded. Replay is exact: the full history is part of
the key, so a run whose history diverges (for example after a recovery)
gets ``ReplayMissError`` instead of a nearby capture.

Captures
--------
One JSON file per model call, named ``capture-NNNN.json``, and one directory
per recorded run: ``RecordingModel`` requires an empty store, and each run is
replayed from its own directory. Captures from different runs are therefore
never mixed, even when their first turns are identical. A capture holds
its key digest and component digests (not the prompt text), the response
output, usage counts, the ``openai`` and ``openai-agents`` versions, and its
source provenance (``live`` or ``scripted``) and source model ID. Replay
refuses captures recorded under different package versions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from importlib.metadata import version
import json
from pathlib import Path
import re
from typing import Any

from agents import Model, ModelProvider, ModelResponse, Usage
from openai.types.responses import ResponseOutputItem
from pydantic import TypeAdapter

from packages.contracts import (
    ContractError,
    canonical_sha256,
)
from packages.integrations.openai_agents.provenance import (
    RunProvenance,
    model_identity,
    model_provenance,
)


CAPTURE_FORMAT = "hetren-model-capture"
CAPTURE_FORMAT_VERSION = 1
CAPTURE_FILE_NAME = re.compile(r"capture-([0-9]{4})\.json")
SOURCE_PROVENANCES = (RunProvenance.LIVE, RunProvenance.SCRIPTED)

_OUTPUT_ITEMS = TypeAdapter(list[ResponseOutputItem])


class ReplayMissError(ContractError):
    """No capture matches the exact replay key."""


class ReplayVersionError(ContractError):
    """A capture was recorded under different package versions."""


class CaptureConflictError(ContractError):
    """A capture for this replay key already exists in the store."""


def installed_versions() -> dict[str, str]:
    return {
        "openai": version("openai"),
        "openai-agents": version("openai-agents"),
    }


def _plain(value: Any) -> Any:
    return json.loads(
        json.dumps(
            value,
            default=lambda item: (
                item.model_dump(mode="json", exclude_none=True)
                if hasattr(item, "model_dump")
                else str(item)
            ),
            sort_keys=True,
        )
    )


def _normalize_items(
    input_items: str | list[Any],
) -> tuple[list[object], list[str]]:
    if isinstance(input_items, str):
        return [{"text": input_items}], []

    call_ordinals: dict[str, int] = {}
    observations: list[str] = []
    normalized: list[object] = []

    def strip(value: object) -> object:
        if isinstance(value, dict):
            result: dict[str, object] = {}

            for key, item in value.items():
                if key == "id":
                    continue

                if key == "call_id" and isinstance(item, str):
                    result[key] = call_ordinals.setdefault(item, len(call_ordinals))
                    continue

                result[key] = strip(item)

            return result

        if isinstance(value, list):
            return [strip(item) for item in value]

        return value

    for item in _plain(input_items):
        if isinstance(item, dict) and item.get("type") == "function_call_output":
            output = item.get("output")
            observations.append(canonical_sha256({"output": output}))
            item = {**item, "output": {"observation_ref": len(observations) - 1}}

        normalized.append(strip(item))

    return normalized, observations


def _tool_definitions(tools: list[Any]) -> list[dict[str, object]]:
    definitions = []

    for tool in tools:
        definitions.append(
            {
                "type": type(tool).__name__,
                "name": getattr(tool, "name", None),
                "description": getattr(tool, "description", None),
                "parameters": _plain(getattr(tool, "params_json_schema", None)),
                "strict": getattr(tool, "strict_json_schema", None),
            }
        )

    return sorted(definitions, key=lambda item: str(item["name"]))


def _settings(model_settings: Any) -> dict[str, object]:
    if model_settings is None:
        return {}

    return {
        key: value
        for key, value in _plain(model_settings.to_json_dict()).items()
        if value is not None
    }


@dataclass(frozen=True)
class ReplayKey:
    components: dict[str, object]

    @property
    def component_digests(self) -> dict[str, str]:
        return {
            name: canonical_sha256(value)
            for name, value in sorted(self.components.items())
        }

    @property
    def key_sha256(self) -> str:
        return canonical_sha256(self.component_digests)


def replay_key(
    *,
    model_id: str,
    system_instructions: str | None,
    input_items: str | list[Any],
    model_settings: Any,
    tools: list[Any],
    output_schema: Any,
    handoffs: list[Any],
    prompt: Any = None,
) -> ReplayKey:
    normalized, observations = _normalize_items(input_items)

    return ReplayKey(
        components={
            "model": {"model_id": model_id, "settings": _settings(model_settings)},
            "system_instructions": system_instructions,
            "input_items": normalized,
            "prior_observations": observations,
            "tool_definitions": _tool_definitions(tools),
            "output_schema": (
                None if output_schema is None
                else _plain(output_schema.json_schema())
            ),
            "handoffs": sorted(str(getattr(item, "tool_name", item)) for item in handoffs),
            "prompt": _plain(prompt),
        }
    )


@dataclass(frozen=True)
class Capture:
    capture_id: str
    key_sha256: str
    component_digests: dict[str, str]
    output: list[dict[str, object]]
    usage: dict[str, int]
    versions: dict[str, str]
    source_provenance: RunProvenance
    source_model_id: str

    def __post_init__(self) -> None:
        if CAPTURE_FILE_NAME.fullmatch(f"{self.capture_id}.json") is None:
            raise ContractError("capture_id must be a neutral capture-NNNN identifier")

        if self.source_provenance not in SOURCE_PROVENANCES:
            raise ContractError("capture source provenance must be live or scripted")

    def to_document(self) -> dict[str, object]:
        return {
            "format": CAPTURE_FORMAT,
            "format_version": CAPTURE_FORMAT_VERSION,
            "capture_id": self.capture_id,
            "key_sha256": self.key_sha256,
            "component_digests": self.component_digests,
            "response": {"output": self.output, "usage": self.usage},
            "versions": self.versions,
            "source_provenance": self.source_provenance.value,
            "source_model_id": self.source_model_id,
        }

    @property
    def capture_sha256(self) -> str:
        return canonical_sha256(self.to_document())

    @classmethod
    def from_document(cls, document: dict[str, Any]) -> "Capture":
        if (
            document.get("format") != CAPTURE_FORMAT
            or document.get("format_version") != CAPTURE_FORMAT_VERSION
        ):
            raise ContractError("unsupported capture format or version")

        try:
            return cls(
                capture_id=document["capture_id"],
                key_sha256=document["key_sha256"],
                component_digests=dict(document["component_digests"]),
                output=list(document["response"]["output"]),
                usage=dict(document["response"]["usage"]),
                versions=dict(document["versions"]),
                source_provenance=RunProvenance(document["source_provenance"]),
                source_model_id=document["source_model_id"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ContractError("capture document is malformed") from exc

    def model_response(self) -> ModelResponse:
        return ModelResponse(
            output=_OUTPUT_ITEMS.validate_python(self.output),
            usage=Usage(**self.usage),
            response_id=None,
        )


def _usage_counts(usage: Any) -> dict[str, int]:
    return {
        name: int(getattr(usage, name, 0) or 0)
        for name in ("requests", "input_tokens", "output_tokens", "total_tokens")
    }


class CaptureStore:
    """Captures in one directory, one ``capture-NNNN.json`` per model call."""

    def __init__(self, directory: Path) -> None:
        self._directory = Path(directory)
        self._by_key: dict[str, Capture] = {}
        self._loaded = False

    @property
    def directory(self) -> Path:
        return self._directory

    def _load(self) -> None:
        if self._loaded:
            return

        self._by_key = {}

        if self._directory.exists():
            for path in sorted(self._directory.iterdir()):
                if path.suffix != ".json":
                    continue

                if CAPTURE_FILE_NAME.fullmatch(path.name) is None:
                    raise ContractError(f"non-neutral capture file name: {path.name}")

                capture = Capture.from_document(
                    json.loads(path.read_text(encoding="utf-8"))
                )

                if f"{capture.capture_id}.json" != path.name:
                    raise ContractError("capture_id does not match its file name")

                if capture.key_sha256 in self._by_key:
                    raise ContractError("duplicate replay key in capture store")

                self._by_key[capture.key_sha256] = capture

        self._loaded = True

    def captures(self) -> tuple[Capture, ...]:
        self._load()
        return tuple(sorted(self._by_key.values(), key=lambda item: item.capture_id))

    def _next_capture_id(self) -> str:
        numbers = [
            int(match.group(1))
            for path in (self._directory.iterdir() if self._directory.exists() else ())
            if (match := CAPTURE_FILE_NAME.fullmatch(path.name))
        ]
        return f"capture-{max(numbers, default=0) + 1:04d}"

    def append(
        self,
        *,
        key: ReplayKey,
        response: ModelResponse,
        source_provenance: RunProvenance,
        source_model_id: str,
    ) -> Capture:
        self._load()

        if key.key_sha256 in self._by_key:
            raise CaptureConflictError("a capture for this replay key already exists")

        capture = Capture(
            capture_id=self._next_capture_id(),
            key_sha256=key.key_sha256,
            component_digests=key.component_digests,
            output=_plain(list(response.output)),
            usage=_usage_counts(response.usage),
            versions=installed_versions(),
            source_provenance=source_provenance,
            source_model_id=source_model_id,
        )

        self._directory.mkdir(parents=True, exist_ok=True)
        path = self._directory / f"{capture.capture_id}.json"

        with path.open("x", encoding="utf-8") as handle:
            json.dump(capture.to_document(), handle, indent=2, sort_keys=True)
            handle.write("\n")

        self._by_key[capture.key_sha256] = capture
        return capture

    def lookup(self, key: ReplayKey) -> Capture:
        self._load()
        capture = self._by_key.get(key.key_sha256)

        if capture is None:
            raise ReplayMissError(self._miss_message(key))

        installed = installed_versions()

        if capture.versions != installed:
            raise ReplayVersionError(
                f"{capture.capture_id} was recorded with {capture.versions}; "
                f"installed versions are {installed}"
            )

        return capture

    def _miss_message(self, key: ReplayKey) -> str:
        message = f"no capture matches replay key {key.key_sha256}"
        digests = key.component_digests
        closest: tuple[int, list[str]] | None = None

        for capture in self._by_key.values():
            differing = sorted(
                name for name in set(digests) | set(capture.component_digests)
                if digests.get(name) != capture.component_digests.get(name)
            )

            if closest is None or len(differing) < closest[0]:
                closest = (len(differing), differing)

        if closest is not None:
            message += f"; the closest capture differs in: {', '.join(closest[1])}"

        return message


class ReplayModel(Model):
    """Serves exact-key captures; never calls a provider."""

    hetren_provenance = RunProvenance.REPLAY

    def __init__(
        self,
        *,
        store: CaptureStore,
        source_provenance: RunProvenance,
        source_model_id: str,
    ) -> None:
        if source_provenance not in SOURCE_PROVENANCES:
            raise ContractError("replay source provenance must be live or scripted")

        self._store = store
        self.hetren_source_provenance = source_provenance
        self.source_model_id = source_model_id
        self.hetren_model_id = f"replay:{source_model_id}"
        self.used_capture_ids: list[str] = []

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> ModelResponse:
        key = replay_key(
            model_id=self.source_model_id,
            system_instructions=system_instructions,
            input_items=input,
            model_settings=model_settings,
            tools=tools,
            output_schema=output_schema,
            handoffs=handoffs,
            prompt=prompt,
        )
        capture = self._store.lookup(key)

        if capture.source_provenance is not self.hetren_source_provenance:
            raise ReplayMissError(
                f"{capture.capture_id} has source provenance "
                f"{capture.source_provenance.value}, not "
                f"{self.hetren_source_provenance.value}"
            )

        if capture.source_model_id != self.source_model_id:
            raise ReplayMissError(
                f"{capture.capture_id} was recorded from a different model"
            )

        self.used_capture_ids.append(capture.capture_id)
        return capture.model_response()

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError("ReplayModel does not stream")


class RecordingModel(Model):
    """Calls an inner model and writes one capture per call."""

    def __init__(
        self,
        *,
        inner: Model,
        store: CaptureStore,
        source_provenance: RunProvenance,
        source_model_id: str | None = None,
    ) -> None:
        if source_provenance not in SOURCE_PROVENANCES:
            raise ContractError("recording source provenance must be live or scripted")

        declared = getattr(inner, "hetren_provenance", None)

        if declared is not None and declared is not source_provenance:
            raise ContractError("source provenance does not match the inner model")

        if declared is None and source_provenance is not RunProvenance.LIVE:
            raise ContractError("an unlabelled inner model can only be recorded as live")

        if source_model_id is None:
            source_model_id = model_identity(inner)

        if store.captures():
            raise CaptureConflictError(
                "recording requires an empty capture store (one directory per run)"
            )

        self._inner = inner
        self._store = store
        self.hetren_provenance = source_provenance
        self.hetren_model_id = source_model_id
        self.recorded_capture_ids: list[str] = []

    async def get_response(
        self,
        system_instructions: str | None,
        input: str | list[Any],
        model_settings: Any,
        tools: list[Any],
        output_schema: Any,
        handoffs: list[Any],
        tracing: Any,
        *,
        previous_response_id: str | None,
        conversation_id: str | None,
        prompt: Any,
    ) -> ModelResponse:
        key = replay_key(
            model_id=self.hetren_model_id,
            system_instructions=system_instructions,
            input_items=input,
            model_settings=model_settings,
            tools=tools,
            output_schema=output_schema,
            handoffs=handoffs,
            prompt=prompt,
        )
        response = await self._inner.get_response(
            system_instructions, input, model_settings, tools, output_schema,
            handoffs, tracing, previous_response_id=previous_response_id,
            conversation_id=conversation_id, prompt=prompt,
        )
        capture = self._store.append(
            key=key,
            response=response,
            source_provenance=self.hetren_provenance,
            source_model_id=self.hetren_model_id,
        )
        self.recorded_capture_ids.append(capture.capture_id)
        return response

    def stream_response(self, *args: Any, **kwargs: Any) -> AsyncIterator[Any]:
        raise NotImplementedError("RecordingModel does not stream")


class ReplayModelProvider(ModelProvider):
    def __init__(self, *, store: CaptureStore, source_provenance: RunProvenance) -> None:
        self._store = store
        self._source_provenance = source_provenance

    def get_model(self, model_name: str | None) -> Model:
        if not model_name:
            raise ContractError("replay requires the source model name")

        return ReplayModel(
            store=self._store,
            source_provenance=self._source_provenance,
            source_model_id=model_name,
        )


class RecordingModelProvider(ModelProvider):
    def __init__(
        self,
        *,
        inner: ModelProvider,
        store: CaptureStore,
        source_provenance: RunProvenance,
    ) -> None:
        self._inner = inner
        self._store = store
        self._source_provenance = source_provenance

    def get_model(self, model_name: str | None) -> Model:
        if not model_name:
            raise ContractError("recording requires the source model name")

        return RecordingModel(
            inner=self._inner.get_model(model_name),
            store=self._store,
            source_provenance=self._source_provenance,
            source_model_id=model_name,
        )


__all__ = [
    "CAPTURE_FILE_NAME",
    "CaptureConflictError",
    "CAPTURE_FORMAT",
    "CAPTURE_FORMAT_VERSION",
    "Capture",
    "CaptureStore",
    "RecordingModel",
    "RecordingModelProvider",
    "ReplayKey",
    "ReplayMissError",
    "ReplayModel",
    "ReplayModelProvider",
    "ReplayVersionError",
    "installed_versions",
    "replay_key",
]
