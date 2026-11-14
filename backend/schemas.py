import re
import base64
import binascii
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Term(BaseModel):
    phrase: str = Field(min_length=1, max_length=120)
    explanation: str = Field(default="", max_length=500)

    @field_validator("phrase")
    @classmethod
    def phrase_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Phrase cannot be blank.")
        return value


class ProductFact(BaseModel):
    product: str = Field(min_length=1, max_length=120)
    fact: str = Field(min_length=1, max_length=200)
    value: float | None = Field(default=None, ge=0)
    unit: str = Field(default="", max_length=40)

    @field_validator("product", "fact")
    @classmethod
    def required_text_not_blank(cls, value):
        if not value.strip():
            raise ValueError("This field cannot be blank.")
        return value


class BrandRules(BaseModel):
    brand_name: str = Field(min_length=1, max_length=120)
    brand_voice: list[str] = Field(min_length=1, max_length=8)
    tone_characteristics: str = Field(default="", max_length=1000)
    restricted_terms: list[Term] = Field(default_factory=list, max_length=100)
    preferred_terms: list[Term] = Field(default_factory=list, max_length=100)
    product_facts: list[ProductFact] = Field(default_factory=list, max_length=100)
    visual_palette: list[str] = Field(default_factory=list, max_length=12)
    logo_reference_data: str | None = Field(default=None, max_length=2_800_000)
    logo_reference_name: str = Field(default="Brand logo", max_length=120)
    clear_logo_reference: bool = False

    @field_validator("brand_name")
    @classmethod
    def brand_name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Brand name cannot be blank.")
        return value

    @field_validator("brand_voice")
    @classmethod
    def clean_voice(cls, values):
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("Add at least one brand voice characteristic.")
        return cleaned

    @model_validator(mode="after")
    def unique_terms(self):
        for terms in (self.restricted_terms, self.preferred_terms):
            phrases = [term.phrase.strip().casefold() for term in terms]
            if len(phrases) != len(set(phrases)):
                raise ValueError("Each term list must contain unique phrases.")
        return self

    @field_validator("visual_palette")
    @classmethod
    def valid_palette(cls, values):
        palette = [value.strip().upper() for value in values if value.strip()]
        if any(not re.fullmatch(r"#[0-9A-F]{6}", value) for value in palette):
            raise ValueError("Brand colors must use six-digit hex values such as #1A2B3C.")
        if len(palette) != len(set(palette)):
            raise ValueError("Brand colors must be unique.")
        return palette

    @field_validator("logo_reference_data")
    @classmethod
    def valid_logo_data_url(cls, value):
        if value is None:
            return value
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})", value)
        if not match:
            raise ValueError("Logo reference must be a PNG, JPEG, or WebP image.")
        try:
            decoded = base64.b64decode(match.group(2), validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Logo reference image data is invalid.") from exc
        if not decoded or len(decoded) > 2_000_000:
            raise ValueError("Logo reference image must be smaller than 2 MB.")
        return value

    @model_validator(mode="after")
    def logo_reference_options(self):
        if self.clear_logo_reference and self.logo_reference_data:
            raise ValueError("Choose either a new logo reference or remove the saved one.")
        return self


class FindingUpdate(BaseModel):
    id: int
    state: Literal["open", "dismissed", "resolved", "accepted", "edited"] | None = None
    suggestion: str | None = Field(default=None, max_length=1000)


class ReviewUpdate(BaseModel):
    status: Literal["approved", "changes_requested"] | None = None
    decision_note: str | None = Field(default=None, max_length=1000)
    findings: list[FindingUpdate] = Field(default_factory=list, max_length=200)
    assigned_to: int | None = None


class AccountCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value):
        normalized = value.strip().casefold()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class AccountSetup(AccountCredentials):
    name: str = Field(min_length=1, max_length=100)
    workspace_token: str = Field(default="", max_length=256)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()


class TeamMemberCreate(AccountCredentials):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["admin", "creator", "reviewer"]

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value):
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()


class TeamMemberUpdate(BaseModel):
    role: Literal["admin", "creator", "reviewer"] | None = None
    is_active: bool | None = None
