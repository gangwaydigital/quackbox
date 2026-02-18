"""
Pydantic models for API request/response schemas.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# -- Request Models --

class IngestRequest(BaseModel):
    """Request to ingest an mbox file."""
    mbox_path: str = Field(..., description="Path to .mbox file relative to data/ directory")


class SearchRequest(BaseModel):
    """Full-text search request."""
    query: str = Field(..., min_length=1, description="Search query string")
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


class EmailFilterParams(BaseModel):
    """Filter and sort parameters for email listing."""
    sender_email: Optional[str] = None
    sender_name: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    subject_contains: Optional[str] = None
    mbox_source: Optional[str] = None
    topic_id: Optional[int] = None
    has_attachments: Optional[bool] = None
    sort_by: str = Field("date_timestamp", pattern="^(date_timestamp|sender_email|subject)$")
    sort_order: str = Field("desc", pattern="^(asc|desc)$")
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=200)


class ClusterRequest(BaseModel):
    """Request to run topic clustering."""
    num_clusters: Optional[int] = Field(None, ge=2, le=100, description="Number of clusters (auto if None)")
    regenerate_embeddings: bool = Field(False, description="Force re-generate all embeddings")


# -- Response Models --

class Recipient(BaseModel):
    name: Optional[str] = None
    email: str
    type: str = "to"  # to, cc, bcc


class EmailSummary(BaseModel):
    """Compact email representation for list views."""
    id: int
    message_id: Optional[str]
    subject: Optional[str]
    sender_name: Optional[str]
    sender_email: Optional[str]
    date_sent: Optional[str]
    has_attachments: bool = False
    topic_ids: list[int] = []
    snippet: Optional[str] = None  # First ~200 chars of body


class EmailDetail(BaseModel):
    """Full email representation."""
    id: int
    message_id: Optional[str]
    subject: Optional[str]
    sender_name: Optional[str]
    sender_email: Optional[str]
    recipients: list[Recipient] = []
    date_sent: Optional[str]
    body_text: Optional[str]
    body_html: Optional[str]
    has_attachments: bool = False
    attachment_names: list[str] = []
    mbox_source: Optional[str]
    thread_id: Optional[str]
    topics: list["TopicSummary"] = []


class TopicSummary(BaseModel):
    """Topic cluster summary."""
    id: int
    label: str
    description: Optional[str]
    keywords: list[str] = []
    email_count: int = 0


class TopicDetail(BaseModel):
    """Topic with associated emails."""
    id: int
    label: str
    description: Optional[str]
    keywords: list[str] = []
    email_count: int = 0
    emails: list[EmailSummary] = []


class PaginatedResponse(BaseModel):
    """Wrapper for paginated results."""
    items: list[EmailSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class SearchResult(BaseModel):
    """Search result with relevance and FTS5 highlights."""
    email: EmailSummary
    rank: float = 0.0


class SearchResponse(BaseModel):
    """Paginated search results."""
    results: list[SearchResult]
    total: int
    query: str
    page: int
    page_size: int


class IngestResponse(BaseModel):
    """Result of mbox ingestion."""
    mbox_file: str
    total_messages: int
    imported: int
    skipped: int
    errors: int
    duration_seconds: float


class StatsResponse(BaseModel):
    """Database statistics."""
    total_emails: int
    unique_senders: int
    mbox_sources: int
    total_topics: int
    total_embeddings: int
    date_range: dict[str, Optional[str]]
