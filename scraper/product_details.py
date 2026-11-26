"""Individual product detail scraping, HTML parsing, retries, and failure tracking."""

import logging
import re
import time
from decimal import Decimal
from typing import Any, Optional

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from core.exceptions import BlockedAccessError, PriceParseError, ScrapingError
from core.models import FailedProduct, ParsedTask, ProductCandidate, ProductRecord
from processor.price_calculator import build_product_record, parse_price
from scraper.category_scraper import check_for_block, format_subcategory_label

_EMPTY_SIZE_TOKENS = {"", "na", "n/a", "none", "null", "-", "--"}

_SPEC_SIZE_LINE_RE = re.compile(
    r"(?:^|\n|\b)(?:size|volume|quantity|qty|net\s*wt\.?|net\s*weight|weight|pack\s*size)\s*[:\-]\s*([^\n\r;|]{1,40})",
    re.IGNORECASE,
)
_UNIT_IN_TEXT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?\s*(?:ml|mL|l|L|ltr|g|gm|gms|kg|mg|oz|pcs|pieces|capsules|tablets))\b"
)


def _extract_product_name(soup: BeautifulSoup) -> str:
    """Extract exact product name from product detail HTML."""
    for selector in ("h1", ".product-title", "[itemprop='name']"):
        el = soup.select_one(selector)
        if el:
            text = " ".join(el.get_text(" ", strip=True).split())
            if text:
                return text
    raise ScrapingError("Product name element (<h1>) is missing or empty.")


def _extract_selling_price(soup: BeautifulSoup) -> Decimal:
    """Extract displayed selling price (never falling back to strikethrough MRP)."""
    dp_span = soup.select_one("span[id^='category_dp_']")
    if dp_span:
        txt = dp_span.get_text(" ", strip=True)
        if txt:
            return parse_price(txt)

    for container_sel in ("div.h4.d-flex.align-items-center", ".product-price", "[itemprop='price']"):
        container = soup.select_one(container_sel)
        if not container:
            continue
        clone = BeautifulSoup(str(container), "html.parser")
        for tag in clone.select("del, small, s"):
            tag.decompose()
        txt = " ".join(clone.get_text(" ", strip=True).split())
        if txt:
            try:
                return parse_price(txt)
            except PriceParseError:
                pass

    checked_radio = soup.select_one("input.CategoryPricesSelect:checked[data-dp]")
    if checked_radio and checked_radio.get("data-dp"):
        return parse_price(checked_radio["data-dp"])

    first_radio = soup.select_one("input.CategoryPricesSelect[data-dp]")
    if first_radio and first_radio.get("data-dp"):
        return parse_price(first_radio["data-dp"])

    select_opt = soup.select_one("select[id^='PricesSelect_'] option[selected][data-dp]") or soup.select_one(
        "select[id^='PricesSelect_'] option[data-dp]"
    )
    if select_opt and select_opt.get("data-dp"):
        return parse_price(select_opt["data-dp"])

    raise PriceParseError("Displayed selling price could not be found on product detail page.")


def _extract_size(soup: BeautifulSoup, product_name: str) -> str:
    """Extract size/quantity/volume if explicitly present; otherwise return 'NA'."""
    sizes: list[str] = []
    seen: set[str] = set()

    def add_size(raw: str) -> None:
        cleaned = " ".join(raw.split())
        if cleaned.lower() in _EMPTY_SIZE_TOKENS:
            return
        if cleaned.lower() not in seen:
            seen.add(cleaned.lower())
            sizes.append(cleaned)

    for radio in soup.select("input.CategoryPricesSelect"):
        rid = radio.get("id")
        if rid:
            lbl = soup.select_one(f"label[for='{rid}']")
            if lbl:
                add_size(lbl.get_text(" ", strip=True))
        elif radio.get("data-size"):
            add_size(str(radio["data-size"]))

    if not sizes:
        for opt in soup.select("select[id^='PricesSelect_'] option"):
            if opt.get("disabled"):
                continue
            txt = opt.get_text(" ", strip=True)
            if "select" in txt.lower():
                continue
            add_size(txt)

    if sizes:
        return ", ".join(sizes)

    desc_parts: list[str] = []
    for sel in ("#description-tab", "#specification-tab", ".product-details", "ul.list-unstyled"):
        el = soup.select_one(sel)
        if el:
            desc_parts.append(el.get_text("\n", strip=True))
    combined_desc = "\n".join(desc_parts)

    spec_match = _SPEC_SIZE_LINE_RE.search(combined_desc)
    if spec_match:
        candidate = spec_match.group(1).strip(" .,:;-")
        if candidate.lower() not in _EMPTY_SIZE_TOKENS:
            return candidate

    for text_source in (product_name, combined_desc):
        unit_match = _UNIT_IN_TEXT_RE.search(text_source)
        if unit_match:
            return " ".join(unit_match.group(1).split())

    return "NA"


def _extract_detail_category(soup: BeautifulSoup) -> str:
    """Extract product's own 'Category : <name>' metadata from detail page if present."""
    for li in soup.select("ul.list-unstyled li"):
        text = " ".join(li.get_text(" ", strip=True).split())
        if text.lower().startswith("category"):
            parts = text.split(":", 1)
            if len(parts) == 2 and parts[1].strip():
                return format_subcategory_label(parts[1].strip())
    return ""


def parse_product_detail_html(html: str, url: str) -> tuple[str, Decimal, str]:
    """Parse rendered product detail HTML into (product_name, selling_price, size)."""
    if not html or not html.strip():
        raise ScrapingError(f"Empty HTML received from {url}")

    soup = BeautifulSoup(html, "html.parser")
    name = _extract_product_name(soup)
    selling_price = _extract_selling_price(soup)
    size = _extract_size(soup, name)
    return name, selling_price, size


def parse_product_detail_html_with_category(html: str, url: str) -> tuple[str, Decimal, str, str]:
    """Parse rendered product detail HTML into (product_name, selling_price, size, detail_category)."""
    if not html or not html.strip():
        raise ScrapingError(f"Empty HTML received from {url}")

    soup = BeautifulSoup(html, "html.parser")
    name = _extract_product_name(soup)
    selling_price = _extract_selling_price(soup)
    size = _extract_size(soup, name)
    detail_category = _extract_detail_category(soup)
    return name, selling_price, size, detail_category


class ProductDetailsScraper:
    """Visits individual product detail pages with retries and records any failures."""

    def __init__(self, settings: dict[str, Any], logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.timeout_ms: int = int(settings["browser"]["timeout_ms"])
        self.nav_timeout_ms: int = int(settings["browser"]["navigation_timeout_ms"])
        self.request_delay: float = float(settings["scraping"]["request_delay_seconds"])
        self.max_retries: int = int(settings["scraping"]["max_retries"])
        self.retry_backoff: float = float(settings["scraping"]["retry_backoff_seconds"])
        self.block_keywords: list[str] = list(settings["scraping"].get("block_keywords", []))

    def fetch_product_fields(self, page: Page, url: str) -> tuple[str, Decimal, str, str]:
        """Load one product detail page with retries and return (name, selling_price, size, detail_category)."""
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=self.nav_timeout_ms)
                status = response.status if response else None
                try:
                    page.wait_for_selector("h1", timeout=self.timeout_ms)
                except PlaywrightError:
                    pass
                html = page.content()
                check_for_block(status, html, url, self.block_keywords)
                if status is not None and status >= 400:
                    raise ScrapingError(f"HTTP {status} returned for {url}")
                return parse_product_detail_html_with_category(html, url)
            except BlockedAccessError:
                raise
            except (PlaywrightError, ScrapingError, PriceParseError) as exc:
                last_exc = exc
                self.logger.warning(
                    "Product extraction attempt %d/%d failed for %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * attempt)

        raise ScrapingError(f"Failed after {self.max_retries} attempts: {last_exc}")

    def scrape_all_products(
        self,
        page: Page,
        candidates: list[ProductCandidate],
        task: ParsedTask,
        progress_callback: Optional[Any] = None,
    ) -> tuple[list[ProductRecord], list[FailedProduct]]:
        """Visit every product URL and return (successful_records, failed_products)."""
        records: list[ProductRecord] = []
        failures: list[FailedProduct] = []
        total = len(candidates)

        for idx, candidate in enumerate(candidates, start=1):
            self.logger.info("[%d/%d] Inspecting product: %s", idx, total, candidate.url)
            if idx > 1 and self.request_delay > 0:
                time.sleep(self.request_delay)

            if progress_callback:
                progress_callback(
                    index=idx,
                    total=total,
                    extracted=len(records),
                    failed=len(failures),
                    subcategory=candidate.subcategory or task.category,
                    phase="extracting",
                )

            try:
                name, total_price, size, detail_category = self.fetch_product_fields(page, candidate.url)
                resolved_type = candidate.subcategory or detail_category or task.category
                sr_no = len(records) + 1
                record = build_product_record(
                    sr_no=sr_no,
                    name=name,
                    total_price=total_price,
                    discount_percent=task.discount_percent,
                    size=size,
                    category_type=resolved_type,
                    url=candidate.url,
                )
                records.append(record)
                if progress_callback:
                    progress_callback(
                        index=idx,
                        total=total,
                        extracted=len(records),
                        failed=len(failures),
                        subcategory=resolved_type,
                        phase="calculated",
                    )
                self.logger.info(
                    "  -> Extracted: %s | Total=%s | %s -> Real=%s | Size=%s | Type=%s",
                    record.name,
                    record.total_price,
                    record.less_price_display,
                    record.real_price,
                    record.size,
                    record.category_type,
                )
            except BlockedAccessError:
                raise
            except Exception as exc:
                reason = str(exc)
                self.logger.error("Failed extracting product %s: %s", candidate.url, reason)
                failures.append(
                    FailedProduct(
                        url=candidate.url,
                        name_hint=candidate.name_hint or "Unknown",
                        reason=reason,
                        subcategory=candidate.subcategory,
                    )
                )
                if progress_callback:
                    progress_callback(
                        index=idx,
                        total=total,
                        extracted=len(records),
                        failed=len(failures),
                        subcategory=candidate.subcategory or task.category,
                        phase="failed_item",
                    )

        return records, failures
