from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


RegistrationToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]

RunnerName = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]

RunnerVersion = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]

RunnerCapability = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]



RunnerJobClaimToken = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=200,
    ),
]

RunnerJobErrorMessage = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=10_000,
    ),
]


RunnerJobLogEventType = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=100,
    ),
]

RunnerJobLogMessage = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=10_000,
    ),
]


class RunnerRegisterRequest(BaseModel):
    registration_token: RegistrationToken
    name: RunnerName
    runner_version: RunnerVersion | None = None
    capabilities: list[RunnerCapability] = Field(
        default_factory=list,
        max_length=50,
    )
    system_info: dict[str, Any] = Field(default_factory=dict)


class RunnerRead(BaseModel):
    project_id: int
    public_id: str
    name: str
    status: str

    runner_version: str | None
    capabilities: list[str]
    system_info: dict[str, Any]

    last_seen_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunnerRegistrationResponse(BaseModel):
    credential: str
    runner: RunnerRead


class RunnerHeartbeatRequest(BaseModel):
    runner_version: RunnerVersion | None = None
    capabilities: list[RunnerCapability] | None = Field(
        default=None,
        max_length=50,
    )
    system_info: dict[str, Any] | None = None


class RunnerHeartbeatResponse(BaseModel):
    status: str
    runner: RunnerRead


class RunnerJobClaimRequest(BaseModel):
    lease_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
    )


class RunnerJobRead(BaseModel):
    public_id: str
    project_id: int

    name: str
    job_type: str
    status: str
    priority: int

    required_capabilities: list[str]
    input_payload: dict[str, Any]

    attempt_count: int
    max_attempts: int

    available_at: datetime
    claimed_at: datetime | None
    lease_expires_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    cancelled_at: datetime | None

    result_payload: dict[str, Any] | None
    error_message: str | None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunnerJobClaimResponse(BaseModel):
    status: Literal["claimed", "idle"]
    claim_token: RunnerJobClaimToken | None = None
    job: RunnerJobRead | None = None

    @model_validator(mode="after")
    def validate_claim_state(self) -> Self:
        if self.status == "claimed":
            if (
                self.claim_token is None
                or self.job is None
            ):
                raise ValueError(
                    "Claimed responses require both a "
                    "claim token and a job."
                )

            return self

        if (
            self.claim_token is not None
            or self.job is not None
        ):
            raise ValueError(
                "Idle responses must not contain a "
                "claim token or job."
            )

        return self


class RunnerJobStartRequest(BaseModel):
    claim_token: RunnerJobClaimToken


class RunnerJobCompleteRequest(BaseModel):
    claim_token: RunnerJobClaimToken
    result_payload: dict[str, Any] = Field(
        default_factory=dict,
    )


class RunnerJobFailRequest(BaseModel):
    claim_token: RunnerJobClaimToken
    error_message: RunnerJobErrorMessage


class RunnerJobTransitionResponse(BaseModel):
    status: Literal["running", "completed", "failed"]
    job: RunnerJobRead


class RunnerJobRenewRequest(BaseModel):
    claim_token: RunnerJobClaimToken
    lease_seconds: int = Field(
        default=300,
        ge=1,
        le=3600,
    )


class RunnerJobLeaseRenewalResponse(BaseModel):
    status: Literal["renewed"]
    job: RunnerJobRead



class RunnerJobLogEntryRequest(BaseModel):
    level: Literal[
        "debug",
        "info",
        "warning",
        "error",
    ]
    event_type: RunnerJobLogEventType
    message: RunnerJobLogMessage
    context_payload: dict[str, Any] = Field(
        default_factory=dict,
    )

    model_config = ConfigDict(extra="forbid")


class RunnerJobLogAppendRequest(BaseModel):
    claim_token: RunnerJobClaimToken
    entries: list[RunnerJobLogEntryRequest] = Field(
        min_length=1,
        max_length=100,
    )


class RunnerJobLogRead(BaseModel):
    public_id: str
    sequence_number: int
    attempt_number: int

    level: str
    event_type: str
    message: str
    context_payload: dict[str, Any]

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RunnerJobLogAppendResponse(BaseModel):
    status: Literal["appended"]
    logs: list[RunnerJobLogRead]


class RunnerJobLogQueryRequest(BaseModel):
    claim_token: RunnerJobClaimToken
    after_sequence: int = Field(
        default=0,
        ge=0,
    )
    limit: int = Field(
        default=100,
        ge=1,
        le=200,
    )
    attempt_number: int | None = Field(
        default=None,
        ge=1,
    )
    level: Literal[
        "debug",
        "info",
        "warning",
        "error",
    ] | None = None

    model_config = ConfigDict(extra="forbid")


class RunnerJobLogQueryResponse(BaseModel):
    logs: list[RunnerJobLogRead]
    has_more: bool
    next_after_sequence: int | None
