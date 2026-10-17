from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
AssetID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Layout = Literal["editorial", "split", "poster", "frame", "orbit", "stack"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Brief(StrictModel):
    brand: str = Field(default="MORNING", min_length=1, max_length=32)
    headline: str = Field(default="오늘의 리듬을 바꾸다", min_length=1, max_length=80)
    subline: str = Field(default="작은 선택에서 시작되는 새로운 일상", max_length=120)
    cta: str = Field(default="컬렉션 살펴보기", max_length=22)
    palette: list[Color] = Field(default=["#F6F1E8", "#EE5A36", "#24263B"], min_length=2, max_length=5)
    format: Literal["square", "portrait", "landscape"] = "square"
    category: str = Field(default="lifestyle", min_length=1, max_length=60)
    audience: str = Field(default="일상의 작은 변화를 원하는 사람", max_length=160)
    asset_id: AssetID | None = None


class GenerateRequest(StrictModel):
    brief: Brief = Field(default_factory=Brief)
    count: int = Field(default=12, ge=1, le=60)
    seed: int = Field(default=42, ge=0, le=2**31-1)
    use_evidence: bool = False
    cohort_platform: str | None = Field(default=None, max_length=32)
    traffic: Literal["organic", "paid", "unknown"] = "organic"
    window_hours: int = Field(default=168, ge=1, le=8760)
    lookback_days: int = Field(default=90, ge=1, le=365)


class DesignSpec(StrictModel):
    layout: Layout
    background: Color
    foreground: Color
    accent: Color
    font_scale: float = Field(default=1.0, ge=0.75, le=1.25)
    motif: Literal["circle", "ribbon", "bars"] = "circle"


class EditRequest(StrictModel):
    brief: Brief
    spec: DesignSpec
    expected_revision: int = Field(ge=1)


class Observation(StrictModel):
    source_id: str = Field(min_length=1, max_length=150)
    platform: Literal["owned", "instagram", "youtube", "tiktok", "x", "reddit", "pinterest", "other", "demo"] = "owned"
    source_url: str | None = Field(default=None, max_length=2048)
    title: str = Field(min_length=1, max_length=200)
    caption: str = Field(default="", max_length=3000)
    category: str = Field(default="lifestyle", min_length=1, max_length=60)
    traffic: Literal["organic", "paid", "unknown"] = "organic"
    media_type: Literal["image"] = "image"
    window_hours: int = Field(default=168, ge=1, le=8760)
    published_at: datetime
    observed_at: datetime
    impressions: int | None = Field(default=None, gt=0, le=10**12)
    views: int | None = Field(default=None, gt=0, le=10**12)
    likes: int | None = Field(default=None, ge=0, le=10**12)
    shares: int | None = Field(default=None, ge=0, le=10**12)
    comments_count: int | None = Field(default=None, ge=0, le=10**12)
    saves: int | None = Field(default=None, ge=0, le=10**12)
    comments: list[str] = Field(default_factory=list, max_length=100)
    asset_id: AssetID | None = None
    palette: list[Color] = Field(default_factory=list, max_length=5)
    layout: Layout | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    rights_basis: str = Field(min_length=3, max_length=400)
    allow_analysis: bool = False
    allow_generation: bool = False
    allow_model_input: bool = False
    is_demo: bool = False

    @field_validator("comments", "tags")
    @classmethod
    def bounded_strings(cls, values):
        if any(len(v) > 2000 for v in values):
            raise ValueError("댓글/태그 한 항목은 2,000자 이하이어야 합니다.")
        return values

    @field_validator("published_at", "observed_at")
    @classmethod
    def timezone_required(cls, dt):
        if dt.tzinfo is None:
            raise ValueError("타임스탬프에 시간대(+09:00 또는 Z)를 포함하세요.")
        return dt.astimezone(timezone.utc)

    @field_validator("source_url")
    @classmethod
    def public_link_only(cls, url):
        if url and not url.startswith(("https://", "http://")):
            raise ValueError("출처 링크는 http/https URL이어야 합니다.")
        return url

    @model_validator(mode="after")
    def check_rights_and_time(self):
        if not self.allow_analysis:
            raise ValueError("분석 사용권을 확인해야 가져올 수 있습니다.")
        if self.observed_at < self.published_at:
            raise ValueError("관측 시각은 게시 시각 이후이어야 합니다.")
        if self.observed_at > datetime.now(timezone.utc):
            raise ValueError("미래의 관측치를 가져올 수 없습니다.")
        if self.platform == "demo" and not self.is_demo:
            raise ValueError("demo 출처는 is_demo=true가 필요합니다.")
        return self


class Preference(StrictModel):
    winner_id: AssetID
    loser_id: AssetID
    reason: str = Field(default="", max_length=400)

    @model_validator(mode="after")
    def distinct(self):
        if self.winner_id == self.loser_id:
            raise ValueError("서로 다른 두 시안을 선택하세요.")
        return self


class AIRequest(StrictModel):
    brief: Brief
    instruction: str = Field(min_length=2, max_length=1200)
    confirm_external_processing: bool = False


class VisionRequest(StrictModel):
    asset_id: AssetID
    confirm_external_processing: bool = False


class ImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=2, max_length=3000)
    asset_id: AssetID | None = None
    size: Literal["1024x1024", "1024x1536", "1536x1024"] = "1024x1024"
    quality: Literal["low", "medium", "high"] = "medium"
    confirm_external_processing: bool = False
