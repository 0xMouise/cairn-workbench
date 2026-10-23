from typing import Literal
from pydantic import BaseModel, Field, field_validator


class ProjectInput(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    origin: str = Field(min_length=1, max_length=20000)
    goal: str = Field(min_length=1, max_length=20000)
    scope: list[str] = Field(default_factory=list, max_length=100)
    excluded: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("title", "origin", "goal")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("不能为空")
        return value.strip()


class RunInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=30000)
    parent_id: str | None = None
    max_steps: int = Field(default=6, ge=1, le=30)
    timeout: int = Field(default=600, ge=30, le=7200)


class FindingInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    severity: Literal["info", "low", "medium", "high", "critical"] = "medium"
    status: Literal["draft", "review", "confirmed", "dismissed"] = "draft"
    description: str = Field(default="", max_length=50000)
    reproduction: str = Field(default="", max_length=50000)
    impact: str = Field(default="", max_length=20000)
    evidence: list[str] = Field(default_factory=list, max_length=100)
    run_id: str | None = None


class ApprovalInput(BaseModel):
    decision: Literal["once", "reject"]


class HintInput(BaseModel):
    content: str = Field(min_length=1, max_length=20000)
    run_id: str | None = None


class ImportInput(BaseModel):
    format: Literal["har", "openapi"]
    content: dict


class RequestInput(BaseModel):
    method: Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"] = "GET"
    url: str = Field(min_length=1, max_length=4096)
    headers: dict[str, str] = Field(default_factory=dict)
    body: str = Field(default="", max_length=200000)
    identity_id: str | None = None


class IdentityInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    headers: dict[str, str] = Field(min_length=1, max_length=30)


class LoginInput(BaseModel):
    token: str


class NetworkInput(BaseModel):
    proxy: str = Field(default="", max_length=2048)


class ProviderInput(BaseModel):
    key: str = Field(min_length=10, max_length=2048, repr=False)
