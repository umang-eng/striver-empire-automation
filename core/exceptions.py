"""Custom exception hierarchy for Striver Empire Product Automation."""


class StriverAutomationError(Exception):
    """Base exception for all application errors."""


class TaskParseError(StriverAutomationError):
    """Raised when a submitted task message cannot be parsed or validated."""


class CategoryNotFoundError(StriverAutomationError):
    """Raised when the requested category cannot be resolved on the target site."""


class CategoryAmbiguityError(StriverAutomationError):
    """Raised when a subcategory name matches multiple parent categories without qualification."""


class BlockedAccessError(StriverAutomationError):
    """Raised when access is blocked by CAPTCHA, anti-bot protection, or HTTP denial."""


class ScrapingError(StriverAutomationError):
    """Raised when scraping fails due to network, timeout, or layout issues."""


class PriceParseError(StriverAutomationError):
    """Raised when a product price string is missing or cannot be safely parsed."""


class FileGenerationError(StriverAutomationError):
    """Raised when Excel or PDF output generation fails."""
