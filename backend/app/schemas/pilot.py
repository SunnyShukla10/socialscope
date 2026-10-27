"""Small account and feedback forms. Never serialize passwords back to clients."""
import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class MemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    password: SecretStr

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Name is required")
        return value.strip()

    @field_validator("email")
    @classmethod
    def clean_email(cls, value):
        value = value.strip().casefold()
        if value.count("@") != 1 or any(c.isspace() for c in value) or not all(value.split("@")):
            raise ValueError("Enter a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def valid_password(cls, value):
        validate_password(value.get_secret_value())
        return value


def validate_password(value: str):
    if len(value) < 12 or len(value.encode("utf-8")) > 72 or not value.strip():
        raise ValueError("Password must contain at least 12 characters and at most 72 UTF-8 bytes")


class UserStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    full_name: str
    email: str
    role: str
    is_active: bool


class FeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["feedback", "issue"]
    message: str = Field(min_length=1, max_length=5000)
    page_path: str = Field(min_length=1, max_length=1000)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value):
        if not value.strip():
            raise ValueError("Message is required")
        return value.strip()

    @field_validator("page_path")
    @classmethod
    def clean_path(cls, value):
        value = value.split("?", 1)[0].split("#", 1)[0]
        if not value.startswith("/") or value.startswith("//") or any(ord(c) < 32 for c in value):
            raise ValueError("Use an application page path")
        return value


class FeedbackOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    submitter_label: str
    kind: str
    message: str
    page_path: str
    reviewed: bool
    created_at: datetime


class FeedbackReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewed: bool
