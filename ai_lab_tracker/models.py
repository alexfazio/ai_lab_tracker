"""Pydantic models for the ai_lab_tracker application."""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, HttpUrl

# =================================================================================================
# DATA MODELS
# =================================================================================================

class Diff(BaseModel):
    """Container for diff results: text and optional JSON form."""

    text: Optional[str]
    json_data: Optional[Any] = Field(None, alias="json")

class ChangeTracking(BaseModel):
    """Metadata and diff information for change tracking results."""

    previous_scrape_at: Optional[datetime] = Field(alias="previousScrapeAt")
    change_status: str = Field(alias="changeStatus")
    visibility: str
    diff: Optional[Diff] = None

    class Config:
        """Allow population of fields by their Pydantic field name, not alias."""
        validate_by_name = True

class FirecrawlResult(BaseModel):
    """Container for Firecrawl API response including URL, markdown, and change tracking."""

    url: HttpUrl
    markdown: Optional[str] = None
    change_tracking: Optional[ChangeTracking] = Field(default=None, alias="changeTracking")

    class Config:
        """Allow population of fields by their Pydantic field name, not alias."""
        validate_by_name = True

# =================================================================================================
# CRAWL OPTIONS MODEL
# =================================================================================================
class CrawlOptions(BaseModel):
    """
    Configuration for the Firecrawl /crawl endpoint to control URL discovery.
    """
    allowBackwardLinks: Optional[bool] = None
    maxDepth: Optional[int] = None
    limit: Optional[int] = None  # max pages to crawl per invocation
    includePaths: Optional[List[str]] = None
    excludePaths: Optional[List[str]] = None

class SourceConfig(BaseModel):
    """Configuration for a source, including tracking mode, cadence, and labels."""

    name: str
    url: HttpUrl
    mode: Optional[str] = "GitDiff"
    cadence: Optional[str] = None
    enabled: bool = True
    labels: List[str] = Field(default_factory=list)
    crawl_options: Optional[CrawlOptions] = Field(default=None, alias="crawlOptions")

    class Config:
        """Allow population of fields by their Pydantic field name, not alias."""
        validate_by_name = True

    def add_label(self, label: str) -> None:
        """Add a label if not already present."""
        if label not in self.labels:
            self.labels.append(label)

    def remove_label(self, label: str) -> None:
        """Remove a label if present."""
        if label in self.labels:
            self.labels.remove(label)

    def update_labels(self, labels: List[str]) -> None:
        """Replace labels list with provided list."""
        self.labels = labels

    def clear_labels(self) -> None:
        """Clear all labels."""
        self.labels.clear() 
 