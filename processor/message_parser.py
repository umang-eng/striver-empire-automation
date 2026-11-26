"""Parse manual task messages into structured category/subcategory and discount."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable, Optional

from core.exceptions import TaskParseError
from core.models import ParsedTask, SubcategoryTarget

_LOWERCASE_CONNECTORS = {"and", "or", "of", "for", "the", "in", "on", "to", "with", "&"}

_DISCOUNT_PATTERNS = [
    re.compile(r"(?:discount\s*(?:of|:)?\s*)?(-?\d+(?:\.\d+)?)\s*%\s*(?:off|discount)?", re.IGNORECASE),
    re.compile(r"(?:discount\s*(?:of|:)?\s*)?(-?\d+(?:\.\d+)?)\s*(?:percent|pct)\b(?:\s*off)?", re.IGNORECASE),
    re.compile(r"(?:^|[\s,\-|])(-?\d+(?:\.\d+)?)\s*$"),
]

_MAIN_DISPLAY_ALIASES = {
    "men": "Men's",
    "mens": "Men's",
    "men's": "Men's",
    "women": "Women's",
    "womens": "Women's",
    "women's": "Women's",
    "beauty and cosmetics": "Beauty and Cosmetics",
    "beauty & cosmetics": "Beauty and Cosmetics",
    "beauty": "Beauty and Cosmetics",
    "accessories": "Accessories",
    "accessory": "Accessories",
    "winter": "Winter",
    "home and living": "Home & Living",
    "home & living": "Home & Living",
    "home living": "Home & Living",
}


def format_category_label(category: str) -> str:
    """Format category name cleanly while keeping connector words lowercase and apostrophes intact."""
    words = category.strip().rstrip(".,").split()
    formatted: list[str] = []
    for idx, word in enumerate(words):
        low = word.lower()
        if idx > 0 and low in _LOWERCASE_CONNECTORS:
            formatted.append("and" if low == "&" else low)
        elif "-" in word:
            formatted.append(
                "-".join(part[:1].upper() + part[1:].lower() if part else "" for part in word.split("-"))
            )
        elif "'" in word or "’" in word:
            sep = "'" if "'" in word else "’"
            head, tail = word.split(sep, 1)
            formatted.append(f"{head[:1].upper() + head[1:].lower()}{sep}{tail.lower()}")
        else:
            formatted.append(word[:1].upper() + word[1:].lower())
    return " ".join(formatted)


def format_display_category_for_filename(category: str) -> str:
    """Format main or parent+subcategory display name cleanly for output filenames."""
    raw = " ".join(category.strip().rstrip(".,").split())
    low = raw.lower()
    if low in _MAIN_DISPLAY_ALIASES:
        return _MAIN_DISPLAY_ALIASES[low]

    # Check if prefixed by a main category alias (e.g. "men formal pants" -> "Men's Formal Pants")
    words = raw.split()
    for prefix_len in (3, 2, 1):
        if len(words) > prefix_len:
            head = " ".join(words[:prefix_len]).lower()
            if head in _MAIN_DISPLAY_ALIASES:
                tail = format_category_label(" ".join(words[prefix_len:]))
                return f"{_MAIN_DISPLAY_ALIASES[head]} {tail}"

    return format_category_label(raw)


def resolve_filename_category_label(
    task: ParsedTask,
    targets: Optional[list[SubcategoryTarget]] = None,
    is_parent_category: bool = True,
) -> str:
    """Compute clean filename category label from resolved targets or parsed task."""
    if targets:
        if is_parent_category:
            parent = targets[0].parent_name or task.category
            return format_display_category_for_filename(parent)
        if len(targets) == 1:
            sub = targets[0]
            parent_disp = format_display_category_for_filename(sub.parent_name) if sub.parent_name else ""
            sub_disp = sub.name.strip()
            if parent_disp:
                # Avoid doubling when subcategory already includes parent word (e.g. Women Jeans)
                parent_root = re.sub(r"[^a-z0-9]", "", parent_disp.lower().replace("'s", ""))
                sub_root = re.sub(r"[^a-z0-9]", "", sub_disp.lower())
                if parent_root and parent_root in sub_root:
                    return sub_disp
                return f"{parent_disp} {sub_disp}"
            return sub_disp

    return format_display_category_for_filename(task.category)


def sanitize_filename_segment(text: str, preserve_case: bool = True) -> str:
    """Remove filesystem-unsafe characters while preserving readable spaces, apostrophes, & and %."""
    cleaned = text.strip()
    if not preserve_case:
        cleaned = format_category_label(cleaned)
    cleaned = re.sub(r'[\\/:*?"<>|]+', " ", cleaned)
    return " ".join(cleaned.split()) or "Report"


def build_output_stem(
    task: ParsedTask,
    display_category: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> str:
    """Build readable filename stem: '<Category> <Discount>%' (without timestamps or person names)."""
    del timestamp  # Timestamps intentionally omitted per naming convention.
    category_label = (
        sanitize_filename_segment(display_category)
        if display_category
        else sanitize_filename_segment(format_display_category_for_filename(task.category))
    )
    return f"{category_label} {task.discount_display}"


def _extract_discount(message: str) -> tuple[Decimal, str]:
    """Extract discount percentage (0 <= discount < 100) and return (discount, remaining_text)."""
    for pattern in _DISCOUNT_PATTERNS:
        matches = list(pattern.finditer(message))
        if not matches:
            continue
        match = matches[-1]
        raw_num = match.group(1)
        try:
            discount = Decimal(raw_num)
        except InvalidOperation as exc:
            raise TaskParseError(f"Invalid discount value: {raw_num!r}") from exc

        if discount < Decimal("0") or discount >= Decimal("100"):
            raise TaskParseError(
                f"Discount percentage must be >= 0% and < 100%, got {discount}%."
            )

        remaining = (message[: match.start()] + " " + message[match.end() :]).strip()
        remaining = re.sub(r"\b(discount|off)\b", "", remaining, flags=re.IGNORECASE)
        remaining = re.sub(r"[\s,\-|;]+$", "", remaining).strip()
        remaining = re.sub(r"^[\s,\-|;]+", "", remaining).strip()
        return discount, remaining

    raise TaskParseError(
        "Could not find a discount percentage in task message. "
        "Expected format: '<Category> <Discount>%', e.g. 'women 25%'."
    )


def parse_task_message(
    message: str,
    known_categories: Optional[Iterable[str]] = None,
) -> ParsedTask:
    """Parse a manual task message in the format '<Category> <Discount>%'."""
    del known_categories
    if not isinstance(message, str) or not message.strip():
        raise TaskParseError("Task message cannot be empty.")

    cleaned = " ".join(message.strip().split())
    discount, remaining = _extract_discount(cleaned)
    raw_category = " ".join(remaining.strip(" -_,|:;").split())

    if not raw_category:
        raise TaskParseError(
            "Missing category in task message. Expected format: '<Category> <Discount>%', e.g. 'women 25%'."
        )

    formatted_category = format_category_label(raw_category)
    return ParsedTask(
        raw_message=message.strip(),
        category=formatted_category,
        discount_percent=discount,
    )


def build_known_category_phrases(settings: dict) -> list[str]:
    """Build known category and parent+subcategory phrases from settings."""
    phrases: set[str] = set(settings.get("categories", {}).keys())
    main_cats = settings.get("main_categories", {})
    sub_keys = list(settings.get("categories", {}).keys())
    for main_info in main_cats.values():
        for alias in main_info.get("aliases", []):
            phrases.add(alias)
            for sub in sub_keys:
                phrases.add(f"{alias} {sub}")
    return sorted(phrases)
