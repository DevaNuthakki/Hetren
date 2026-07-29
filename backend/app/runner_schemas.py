from datetime import datetime
from typing import Annotated, Any

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
