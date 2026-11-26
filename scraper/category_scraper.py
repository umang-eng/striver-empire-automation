"""Category/subcategory discovery, Load More pagination, and canonical URL deduplication."""

import difflib
import logging
import re
import time
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page

from core.exceptions import (
    BlockedAccessError,
    CategoryAmbiguityError,
    CategoryNotFoundError,
    ScrapingError,
)
from core.models import ProductCandidate, SubcategoryTarget

_DEFAULT_BLOCK_KEYWORDS = (
    "cf-browser-verification",
    "verify you are human",
    "attention required! | cloudflare",
    "just a moment...",
    "g-recaptcha",
    "hcaptcha",
    "access denied",
)

_CONNECTOR_WORDS = {"and", "or", "of", "for", "the", "in", "on", "to", "with", "&"}


def canonicalize_url(url: str, base_url: str = "https://striverempire.com") -> str:
    """Normalize a product or category URL for reliable deduplication."""
    absolute = urljoin(base_url.rstrip("/") + "/", url.strip())
    parsed = urlparse(absolute)
    clean_path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            "",
            "",
            "",
        )
    )


def normalize_category_key(text: str) -> str:
    """Normalize category name/slug for resilient matching."""
    cleaned = text.lower().replace("&", " and ").replace("-", " ")
    cleaned = re.sub(r"['’.,]", "", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s]+", " ", cleaned)
    return " ".join(cleaned.split())


def format_subcategory_label(raw_name: str) -> str:
    """Clean website subcategory label (e.g. 'Blazers.' -> 'Blazers', 'Formal pant' -> 'Formal Pant')."""
    cleaned = " ".join(raw_name.strip().rstrip(".,").split())
    if not cleaned:
        return "NA"
    words = cleaned.split()
    out: list[str] = []
    for idx, word in enumerate(words):
        low = word.lower()
        if idx > 0 and low in _CONNECTOR_WORDS:
            out.append("and" if low == "&" else low)
        elif word.islower():
            out.append(word[:1].upper() + word[1:])
        else:
            out.append(word)
    return " ".join(out)


def check_for_block(
    status_code: Optional[int],
    html: str,
    url: str,
    block_keywords: Optional[list[str]] = None,
) -> None:
    """Detect HTTP access blocks, CAPTCHAs, or anti-bot interstitials and stop cleanly."""
    if status_code in (401, 403, 429):
        raise BlockedAccessError(
            f"Access blocked with HTTP {status_code} at {url}. "
            "Stopping without attempting to bypass site protections."
        )

    lower_html = (html or "").lower()
    keywords = block_keywords if block_keywords is not None else list(_DEFAULT_BLOCK_KEYWORDS)
    for kw in keywords:
        if kw.lower() in lower_html:
            raise BlockedAccessError(
                f"Detected anti-bot or CAPTCHA gate ({kw!r}) at {url}. "
                "Stopping without attempting to bypass site protections."
            )


def extract_expected_total_from_html(html: str) -> Optional[int]:
    """Parse 'We found N items for you!' counter from rendered category page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    counter = soup.select_one(".totall-product")
    if not counter:
        return None
    text = " ".join(counter.get_text(" ", strip=True).split())
    match = re.search(r"(\d+)\s+items?", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_category_tree_from_html(
    html: str,
    base_url: str = "https://striverempire.com",
) -> dict[str, list[SubcategoryTarget]]:
    """Parse main categories and their ordered subcategories from homepage header HTML."""
    soup = BeautifulSoup(html, "html.parser")
    tree: dict[str, list[SubcategoryTarget]] = {}

    for li in soup.select("header li.dropdown"):
        top_a = li.select_one(":scope > a")
        if not top_a:
            continue
        parent_label = " ".join(top_a.get_text(" ", strip=True).split())
        if not parent_label:
            continue

        subs: list[SubcategoryTarget] = []
        seen_urls: set[str] = set()
        for sub_a in li.select("ul.dropdown-menu a.dropdown-item[href*='/product/list/']"):
            href = (sub_a.get("href") or "").strip()
            if not href:
                continue
            canon = canonicalize_url(href, base_url=base_url)
            if canon in seen_urls:
                continue
            seen_urls.add(canon)
            sub_name = " ".join(sub_a.get_text(" ", strip=True).split())
            subs.append(
                SubcategoryTarget(
                    name=format_subcategory_label(sub_name or canon.rsplit("/", 1)[-1]),
                    url=canon,
                    parent_name=parent_label,
                )
            )
        if subs:
            tree[parent_label] = subs

    return tree


def extract_sidebar_subcategories_from_html(
    html: str,
    parent_name: str,
    base_url: str = "https://striverempire.com",
) -> list[SubcategoryTarget]:
    """Extract ordered subcategories from a main category page's #filterSidebar."""
    soup = BeautifulSoup(html, "html.parser")
    subs: list[SubcategoryTarget] = []
    seen: set[str] = set()
    for anchor in soup.select("#filterSidebar a.nav-link[href*='/product/list/']"):
        href = (anchor.get("href") or "").strip()
        if not href:
            continue
        canon = canonicalize_url(href, base_url=base_url)
        if canon in seen:
            continue
        seen.add(canon)
        label = " ".join(anchor.get_text(" ", strip=True).split())
        subs.append(
            SubcategoryTarget(
                name=format_subcategory_label(label or canon.rsplit("/", 1)[-1]),
                url=canon,
                parent_name=parent_name,
            )
        )
    return subs


def extract_product_candidates_from_html(
    html: str,
    base_url: str = "https://striverempire.com",
    subcategory: str = "",
    parent_category: str = "",
) -> list[ProductCandidate]:
    """Extract deduplicated ProductCandidate entries from rendered category/subcategory HTML."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    candidates: list[ProductCandidate] = []

    cards = soup.select(".product-card")
    for card in cards:
        link = card.select_one("h3 a[href]") or card.select_one("a[href*='/product/detail/']")
        if not link:
            continue
        href = (link.get("href") or "").strip()
        if not href or "/product/detail/" not in href:
            continue

        canon = canonicalize_url(href, base_url=base_url)
        if canon in seen:
            continue
        seen.add(canon)

        name_hint = " ".join(link.get_text(" ", strip=True).split())
        price_el = card.select_one(".h5")
        price_hint = " ".join(price_el.get_text(" ", strip=True).split()) if price_el else None
        candidates.append(
            ProductCandidate(
                url=canon,
                name_hint=name_hint,
                price_hint=price_hint,
                subcategory=subcategory,
                parent_category=parent_category,
            )
        )

    if not candidates:
        for link in soup.select("a[href*='/product/detail/']"):
            href = (link.get("href") or "").strip()
            if not href:
                continue
            canon = canonicalize_url(href, base_url=base_url)
            if canon in seen:
                continue
            seen.add(canon)
            name_hint = " ".join(link.get_text(" ", strip=True).split())
            candidates.append(
                ProductCandidate(
                    url=canon,
                    name_hint=name_hint,
                    subcategory=subcategory,
                    parent_category=parent_category,
                )
            )

    return candidates


def find_next_pagination_url(
    html: str,
    visited_page_urls: set[str],
    base_url: str = "https://striverempire.com",
) -> Optional[str]:
    """Check traditional pagination links if the site renders numbered/next links."""
    soup = BeautifulSoup(html, "html.parser")
    selectors = [
        "a[rel='next']",
        ".pagination a.page-link[aria-label*='Next' i]",
        ".pagination li.page-item:not(.disabled) a.page-link",
    ]
    for sel in selectors:
        for anchor in soup.select(sel):
            href = (anchor.get("href") or "").strip()
            if not href or href == "#" or href.lower().startswith("javascript:"):
                continue
            abs_url = urljoin(base_url.rstrip("/") + "/", href)
            if abs_url not in visited_page_urls:
                return abs_url
    return None


class CategoryScraper:
    """Discovers main categories & subcategories and scrapes all paginated product URLs."""

    def __init__(self, settings: dict[str, Any], logger: logging.Logger) -> None:
        self.settings = settings
        self.logger = logger
        self.base_url: str = settings["site"]["base_url"].rstrip("/")
        self.timeout_ms: int = int(settings["browser"]["timeout_ms"])
        self.nav_timeout_ms: int = int(settings["browser"]["navigation_timeout_ms"])
        self.request_delay: float = float(settings["scraping"]["request_delay_seconds"])
        self.max_retries: int = int(settings["scraping"]["max_retries"])
        self.retry_backoff: float = float(settings["scraping"]["retry_backoff_seconds"])
        self.max_pages: int = int(settings["scraping"]["max_pagination_pages"])
        self.load_more_wait_ms: int = int(settings["scraping"]["load_more_wait_ms"])
        self.block_keywords: list[str] = list(settings["scraping"].get("block_keywords", []))

    def _goto_with_retry(self, page: Page, url: str, wait_until: str = "domcontentloaded") -> None:
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = page.goto(url, wait_until=wait_until, timeout=self.nav_timeout_ms)
                status = response.status if response else None
                html = page.content()
                check_for_block(status, html, url, self.block_keywords)
                if status is not None and status >= 400:
                    raise ScrapingError(f"HTTP {status} returned while loading {url}")
                return
            except BlockedAccessError:
                raise
            except (PlaywrightError, ScrapingError) as exc:
                last_exc = exc
                self.logger.warning(
                    "Attempt %d/%d failed loading %s: %s",
                    attempt,
                    self.max_retries,
                    url,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff * attempt)
        raise ScrapingError(f"Failed to load {url} after {self.max_retries} attempts: {last_exc}")

    def _wait_for_category_render(self, page: Page) -> None:
        """Wait for Vue AJAX product load (cards, empty state, or total counter)."""
        try:
            page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
        except PlaywrightError:
            pass

        try:
            page.wait_for_selector(
                ".product-card, .error-content, .totall-product strong",
                timeout=self.timeout_ms,
            )
        except PlaywrightError:
            self.logger.warning("Timed out waiting for product grid selector on category page.")

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(400)

    def _build_main_category_registry(
        self,
        html: str,
    ) -> tuple[dict[str, tuple[str, str]], dict[str, list[SubcategoryTarget]], dict[str, str]]:
        """Discover main categories, their subcategories, and all flat category URLs from homepage."""
        tree = extract_category_tree_from_html(html, base_url=self.base_url)

        # Map normalized alias -> (canonical_parent_label, parent_url)
        main_lookup: dict[str, tuple[str, str]] = {}
        for slug, info in self.settings.get("main_categories", {}).items():
            label = info["label"]
            url = canonicalize_url(info["url"], base_url=self.base_url)
            main_lookup[normalize_category_key(slug)] = (label, url)
            main_lookup[normalize_category_key(label)] = (label, url)
            for alias in info.get("aliases", []):
                main_lookup[normalize_category_key(alias)] = (label, url)

        # Also inspect homepage category tiles/links
        soup = BeautifulSoup(html, "html.parser")
        flat_lookup: dict[str, str] = {}
        for name, path in self.settings.get("categories", {}).items():
            full_url = canonicalize_url(path, base_url=self.base_url)
            flat_lookup[normalize_category_key(name)] = full_url
            flat_lookup[normalize_category_key(full_url.rsplit("/", 1)[-1])] = full_url

        for anchor in soup.select("a[href*='/product/list/']"):
            href = (anchor.get("href") or "").strip()
            if not href:
                continue
            full_url = canonicalize_url(href, base_url=self.base_url)
            slug = full_url.rsplit("/", 1)[-1]
            if slug:
                flat_lookup[normalize_category_key(slug)] = full_url
            label = " ".join(anchor.get_text(" ", strip=True).split())
            if label and label.lower() != "view all":
                flat_lookup[normalize_category_key(label)] = full_url

        # Ensure every dropdown parent label is also registered in main_lookup
        for parent_label, subs in tree.items():
            norm_parent = normalize_category_key(parent_label)
            if norm_parent not in main_lookup:
                guessed_url = flat_lookup.get(norm_parent, "")
                if guessed_url:
                    main_lookup[norm_parent] = (parent_label, guessed_url)

        return main_lookup, tree, flat_lookup

    def _match_subcategories_in_scope(
        self,
        sub_query: str,
        subcategories: list[SubcategoryTarget],
    ) -> list[SubcategoryTarget]:
        """Match a subcategory query against a list of SubcategoryTarget objects."""
        norm_q = normalize_category_key(sub_query)
        exact: list[SubcategoryTarget] = []
        for sub in subcategories:
            slug = sub.url.rsplit("/", 1)[-1]
            if normalize_category_key(sub.name) == norm_q or normalize_category_key(slug) == norm_q:
                exact.append(sub)
        if exact:
            return exact

        # Singular/plural match (only when no exact match existed)
        variants = [norm_q[:-1]] if norm_q.endswith("s") else [norm_q + "s"]
        plural_matches: list[SubcategoryTarget] = []
        for sub in subcategories:
            slug = sub.url.rsplit("/", 1)[-1]
            sub_keys = {normalize_category_key(sub.name), normalize_category_key(slug)}
            if any(v in sub_keys for v in variants):
                plural_matches.append(sub)
        if plural_matches:
            return plural_matches

        # Substring / fuzzy fallback within scope
        partial = [
            sub
            for sub in subcategories
            if norm_q in normalize_category_key(sub.name)
            or normalize_category_key(sub.name) in norm_q
        ]
        if partial:
            partial.sort(key=lambda s: abs(len(normalize_category_key(s.name)) - len(norm_q)))
            return [partial[0]]

        return []

    def resolve_target_subcategories(
        self,
        page: Page,
        requested_category: str,
    ) -> tuple[str, list[SubcategoryTarget], bool]:
        """Resolve requested category into (primary_url, ordered_subcategory_targets, is_parent_category).

        Raises CategoryAmbiguityError when a subcategory is ambiguous across multiple parents.
        """
        self.logger.info("Discovering live category/subcategory tree from %s ...", self.base_url)
        self._goto_with_retry(page, self.base_url, wait_until="domcontentloaded")
        home_html = page.content()
        main_lookup, tree, flat_lookup = self._build_main_category_registry(home_html)

        norm_req = normalize_category_key(requested_category)

        # 1. Direct match to a main/parent category (e.g. 'Women', 'Men', 'Beauty and Cosmetics')
        if norm_req in main_lookup:
            parent_label, parent_url = main_lookup[norm_req]
            self.logger.info("Matched main category %r -> %s", parent_label, parent_url)
            self._goto_with_retry(page, parent_url, wait_until="domcontentloaded")
            self._wait_for_category_render(page)
            sidebar_subs = extract_sidebar_subcategories_from_html(
                page.content(), parent_name=parent_label, base_url=self.base_url
            )
            if sidebar_subs:
                subs = sidebar_subs
            else:
                # Fallback to homepage dropdown subcategories for this parent
                subs = []
                for k, v in tree.items():
                    if normalize_category_key(k) == normalize_category_key(parent_label):
                        subs = v
                        break
            if not subs:
                subs = [
                    SubcategoryTarget(
                        name=format_subcategory_label(parent_label),
                        url=parent_url,
                        parent_name=parent_label,
                    )
                ]
            self.logger.info(
                "Discovered %d ordered subcategory(s) under %s: %s",
                len(subs),
                parent_label,
                [s.name for s in subs],
            )
            return parent_url, subs, True

        # 2. Parent-qualified subcategory (e.g. "Women's Shirt", "Men's Blazers", "Women Formal Pant")
        req_words = norm_req.split()
        sorted_aliases = sorted(main_lookup.keys(), key=lambda s: len(s.split()), reverse=True)
        for alias in sorted_aliases:
            alias_words = alias.split()
            k = len(alias_words)
            if len(req_words) > k and req_words[:k] == alias_words:
                parent_label, parent_url = main_lookup[alias]
                sub_query = " ".join(req_words[k:])
                self.logger.info(
                    "Detected parent-qualified subcategory: parent=%r, sub=%r",
                    parent_label,
                    sub_query,
                )
                self._goto_with_retry(page, parent_url, wait_until="domcontentloaded")
                self._wait_for_category_render(page)
                subs = extract_sidebar_subcategories_from_html(
                    page.content(), parent_name=parent_label, base_url=self.base_url
                )
                if not subs:
                    for p_name, p_subs in tree.items():
                        if normalize_category_key(p_name) == normalize_category_key(parent_label):
                            subs = p_subs
                            break
                matched = self._match_subcategories_in_scope(sub_query, subs)
                if len(matched) == 1:
                    return matched[0].url, matched, False
                if len(matched) > 1:
                    opts = ", ".join(f"{m.parent_name} -> {m.name}" for m in matched)
                    raise CategoryAmbiguityError(
                        f"Category {requested_category!r} matched multiple subcategories: {opts}. "
                        "Please clarify which subcategory you want."
                    )

        # 3. Unqualified subcategory lookup across all parents
        all_subs: list[SubcategoryTarget] = [sub for subs in tree.values() for sub in subs]
        matched_global = self._match_subcategories_in_scope(norm_req, all_subs)
        unique_by_url: dict[str, SubcategoryTarget] = {}
        for m in matched_global:
            unique_by_url[m.url] = m
        distinct = list(unique_by_url.values())

        if len(distinct) == 1:
            target = distinct[0]
            self.logger.info(
                "Matched subcategory %r (%s -> %s)",
                target.name,
                target.parent_name,
                target.url,
            )
            return target.url, [target], False

        if len(distinct) > 1:
            options = ", ".join(f"{m.parent_name} -> {m.name}" for m in distinct)
            raise CategoryAmbiguityError(
                f"Subcategory {requested_category!r} is ambiguous across parent categories: {options}. "
                "Please specify the parent category (e.g., \"Men's ...\" or \"Women's ...\")."
            )

        # 4. Flat URL / fuzzy fallback
        if norm_req in flat_lookup:
            url = flat_lookup[norm_req]
            target = SubcategoryTarget(name=format_subcategory_label(requested_category), url=url)
            return url, [target], False

        close = difflib.get_close_matches(norm_req, list(flat_lookup.keys()), n=1, cutoff=0.82)
        if close:
            url = flat_lookup[close[0]]
            target = SubcategoryTarget(name=format_subcategory_label(close[0]), url=url)
            return url, [target], False

        raise CategoryNotFoundError(
            f"Category {requested_category!r} could not be matched on {self.base_url}."
        )

    def resolve_category_url(self, page: Page, requested_category: str) -> str:
        """Backward-compatible helper returning the primary URL for a category query."""
        primary_url, _, _ = self.resolve_target_subcategories(page, requested_category)
        return primary_url

    def scrape_category_products(
        self,
        page: Page,
        category_url: str,
        subcategory_name: str = "",
        parent_category: str = "",
    ) -> tuple[list[ProductCandidate], Optional[int]]:
        """Extract all deduplicated product candidates across Load More / pagination for one page."""
        self.logger.info("Navigating to listing page: %s", category_url)
        self._goto_with_retry(page, category_url, wait_until="domcontentloaded")
        self._wait_for_category_render(page)

        expected_total = extract_expected_total_from_html(page.content())
        if expected_total is not None:
            self.logger.info("Listing reports %d total item(s).", expected_total)

        seen_urls: set[str] = set()
        all_candidates: list[ProductCandidate] = []
        visited_page_urls: set[str] = {category_url}

        def merge_current_dom() -> int:
            added = 0
            for candidate in extract_product_candidates_from_html(
                page.content(),
                base_url=self.base_url,
                subcategory=subcategory_name,
                parent_category=parent_category,
            ):
                if candidate.url not in seen_urls:
                    seen_urls.add(candidate.url)
                    all_candidates.append(candidate)
                    added += 1
            return added

        initial_added = merge_current_dom()
        self.logger.info("Page 1 loaded: %d unique product(s) collected.", initial_added)

        if page.locator(".error-content").count() > 0 and page.locator(".error-content").first.is_visible():
            self.logger.warning("Listing page shows 'Product not Found' state.")
            return all_candidates, expected_total

        stagnant_clicks = 0
        for step in range(2, self.max_pages + 1):
            load_more_btn = page.locator("button:has-text('Load More')").first
            if load_more_btn.count() > 0 and load_more_btn.is_visible():
                if not load_more_btn.is_enabled():
                    self.logger.info("Load More button is disabled; stopping pagination.")
                    break

                prev_dom_count = page.locator(".product-card").count()
                self.logger.info("Clicking 'Load More' (step %d)...", step)
                load_more_btn.scroll_into_view_if_needed()
                time.sleep(self.request_delay)

                try:
                    load_more_btn.click(timeout=self.timeout_ms)
                except PlaywrightError as exc:
                    self.logger.warning("Failed clicking Load More at step %d: %s", step, exc)
                    break

                try:
                    page.wait_for_function(
                        "(prev) => document.querySelectorAll('.product-card').length > prev "
                        "|| !document.querySelector(\"button.btn-outline-primary\")",
                        arg=prev_dom_count,
                        timeout=max(self.load_more_wait_ms * 3, 6000),
                    )
                except PlaywrightError:
                    pass

                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except PlaywrightError:
                    pass

                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                page.wait_for_timeout(300)
                check_for_block(None, page.content(), page.url, self.block_keywords)

                newly_added = merge_current_dom()
                self.logger.info(
                    "After Load More step %d: +%d new unique product(s) (total %d).",
                    step,
                    newly_added,
                    len(all_candidates),
                )
                if newly_added == 0:
                    stagnant_clicks += 1
                    if stagnant_clicks >= 2:
                        self.logger.info("No new products after consecutive Load More attempts; stopping.")
                        break
                else:
                    stagnant_clicks = 0
                continue

            next_url = find_next_pagination_url(page.content(), visited_page_urls, base_url=self.base_url)
            if next_url:
                visited_page_urls.add(next_url)
                self.logger.info("Following pagination link (page %d): %s", step, next_url)
                time.sleep(self.request_delay)
                self._goto_with_retry(page, next_url, wait_until="domcontentloaded")
                self._wait_for_category_render(page)
                newly_added = merge_current_dom()
                self.logger.info(
                    "Pagination page %d: +%d new unique product(s) (total %d).",
                    step,
                    newly_added,
                    len(all_candidates),
                )
                if newly_added == 0:
                    self.logger.info("No new products on pagination page %d; stopping.", step)
                    break
                continue

            break

        return all_candidates, expected_total

    def scrape_targets_grouped(
        self,
        page: Page,
        primary_url: str,
        targets: list[SubcategoryTarget],
        is_parent_category: bool,
        progress_callback: Optional[Any] = None,
    ) -> tuple[list[ProductCandidate], Optional[int], list[str]]:
        """Scrape all subcategory targets in order, preserving grouping and deduplicating URLs."""
        ordered_candidates: list[ProductCandidate] = []
        seen_by_url: dict[str, str] = {}
        warnings: list[str] = []

        expected_parent_total: Optional[int] = None
        if is_parent_category:
            # Capture main-category expected total to cross-check completeness
            self._goto_with_retry(page, primary_url, wait_until="domcontentloaded")
            self._wait_for_category_render(page)
            expected_parent_total = extract_expected_total_from_html(page.content())

        sum_sub_totals = 0
        total_targets = max(len(targets), 1)
        for idx, target in enumerate(targets, start=1):
            self.logger.info(
                "=== Subcategory [%d/%d]: %s (%s) ===",
                idx,
                len(targets),
                target.name,
                target.url,
            )
            if progress_callback:
                progress_callback(
                    subcategory=target.name,
                    sub_index=idx,
                    sub_total=total_targets,
                    discovered=len(ordered_candidates),
                )
            if idx > 1 and self.request_delay > 0:
                time.sleep(self.request_delay)

            sub_candidates, sub_expected = self.scrape_category_products(
                page,
                target.url,
                subcategory_name=target.name,
                parent_category=target.parent_name,
            )
            if sub_expected is not None:
                sum_sub_totals += sub_expected

            for cand in sub_candidates:
                if cand.url in seen_by_url:
                    first_type = seen_by_url[cand.url]
                    msg = (
                        f"Duplicate product URL across subcategories: {cand.url} "
                        f"(already classified as {first_type!r}; also appeared in {target.name!r}). "
                        f"Keeping primary Type={first_type!r}."
                    )
                    self.logger.warning(msg)
                    warnings.append(msg)
                    continue
                seen_by_url[cand.url] = cand.subcategory or target.name
                ordered_candidates.append(cand)

            if progress_callback:
                progress_callback(
                    subcategory=target.name,
                    sub_index=idx,
                    sub_total=total_targets,
                    discovered=len(ordered_candidates),
                )

        expected_total = expected_parent_total if expected_parent_total is not None else (
            sum_sub_totals if targets else None
        )

        # Safety check: if a parent category reports more items than discovered across subcategories,
        # scan main category pagination to catch any uncategorized/orphan products without losing them.
        if (
            is_parent_category
            and expected_parent_total is not None
            and len(ordered_candidates) < expected_parent_total
        ):
            self.logger.warning(
                "Parent category %s reported %d items but subcategories yielded %d; scanning main category for remaining items.",
                primary_url,
                expected_parent_total,
                len(ordered_candidates),
            )
            main_candidates, _ = self.scrape_category_products(
                page,
                primary_url,
                subcategory_name="",
                parent_category=targets[0].parent_name if targets else "",
            )
            for cand in main_candidates:
                if cand.url not in seen_by_url:
                    seen_by_url[cand.url] = ""
                    ordered_candidates.append(cand)

        return ordered_candidates, expected_total, warnings
