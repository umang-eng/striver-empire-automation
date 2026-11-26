"""Domain data models for parsed tasks, category hierarchy, scraped products, and summaries."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class ParsedTask:
    """Structured representation of a user-submitted automation task."""

    raw_message: str
    category: str
    discount_percent: Decimal

    @property
    def discount_display(self) -> str:
        """Return formatted discount percentage without redundant trailing zeros."""
        normalized = self.discount_percent.normalize()
        text = format(normalized, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return f"{text}%"


@dataclass(frozen=True)
class SubcategoryTarget:
    """Resolved subcategory page to scrape, preserving parent & navigation order."""

    name: str
    url: str
    parent_name: str = ""


@dataclass(frozen=True)
class ProductCandidate:
    """Product link discovered from a category or subcategory listing page."""

    url: str
    name_hint: str = ""
    price_hint: Optional[str] = None
    subcategory: str = ""
    parent_category: str = ""


@dataclass(frozen=True)
class ProductRecord:
    """Validated product record ready for Excel and PDF export."""

    sr_no: int
    name: str
    total_price: Decimal
    discount_percent: Decimal
    real_price: Decimal
    size: str
    category_type: str
    url: str

    @property
    def less_price_display(self) -> str:
        """Return discount string for the Less Price column."""
        normalized = self.discount_percent.normalize()
        text = format(normalized, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return f"{text}%"


@dataclass(frozen=True)
class FailedProduct:
    """Record of an individual product whose detail extraction failed."""

    url: str
    name_hint: str
    reason: str
    subcategory: str = ""


@dataclass
class ExtractionSummary:
    """Summary of a complete category scraping and processing run."""

    task: ParsedTask
    category_url: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    expected_total_from_site: Optional[int] = None
    discovered_count: int = 0
    subcategories_scraped: list[str] = field(default_factory=list)
    records: list[ProductRecord] = field(default_factory=list)
    failures: list[FailedProduct] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def succeeded_count(self) -> int:
        return len(self.records)

    @property
    def failed_count(self) -> int:
        return len(self.failures)

    @property
    def total_price_sum(self) -> Decimal:
        return sum((r.total_price for r in self.records), Decimal("0.00"))

    @property
    def total_real_price_sum(self) -> Decimal:
        return sum((r.real_price for r in self.records), Decimal("0.00"))

    @property
    def total_savings(self) -> Decimal:
        return self.total_price_sum - self.total_real_price_sum
