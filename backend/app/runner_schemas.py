from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
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
    claim_token: str | None = None
    job: RunnerJobRead | None = None


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
