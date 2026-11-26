"""Unit tests for category/subcategory tree parsing, pagination, deduplication, and product HTML."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from core.exceptions import BlockedAccessError, CategoryAmbiguityError, PriceParseError
from core.logger import setup_logging
from core.models import SubcategoryTarget
from scraper.category_scraper import (
    CategoryScraper,
    canonicalize_url,
    check_for_block,
    extract_category_tree_from_html,
    extract_expected_total_from_html,
    extract_product_candidates_from_html,
    extract_sidebar_subcategories_from_html,
    find_next_pagination_url,
    format_subcategory_label,
)
from scraper.product_details import parse_product_detail_html, parse_product_detail_html_with_category


def test_canonicalize_url_deduplication():
    u1 = canonicalize_url("https://STRIVEREMPIRE.com/product/detail/soap-1/?ref=cat#top")
    u2 = canonicalize_url("/product/detail/soap-1")
    assert u1 == "https://striverempire.com/product/detail/soap-1"
    assert u1 == u2


def test_format_subcategory_label():
    assert format_subcategory_label("Blazers.") == "Blazers"
    assert format_subcategory_label("Formal pant") == "Formal Pant"
    assert format_subcategory_label("Shirt's") == "Shirt's"
    assert format_subcategory_label("Beauty and cosmetic") == "Beauty and Cosmetic"


def test_extract_category_tree_and_sidebar():
    home_html = """
    <header>
      <ul>
        <li class="dropdown">
          <a href="#">Women's</a>
          <ul class="dropdown-menu">
            <li><a class="dropdown-item" href="/product/list/shirts">Shirt's</a></li>
            <li><a class="dropdown-item" href="/product/list/formal-pant">Formal pant</a></li>
            <li><a class="dropdown-item" href="/product/list/blazers-1">Blazers.</a></li>
          </ul>
        </li>
      </ul>
    </header>
    """
    tree = extract_category_tree_from_html(home_html)
    assert "Women's" in tree
    assert [s.name for s in tree["Women's"]] == ["Shirt's", "Formal Pant", "Blazers"]

    sidebar_html = """
    <aside id="filterSidebar">
      <a class="nav-link" href="/product/list/shirts">Shirt's</a>
      <a class="nav-link" href="/product/list/tops">Tops</a>
    </aside>
    """
    subs = extract_sidebar_subcategories_from_html(sidebar_html, parent_name="Women's")
    assert [(s.name, s.parent_name) for s in subs] == [
        ("Shirt's", "Women's"),
        ("Tops", "Women's"),
    ]


def test_extract_product_candidates_deduplicates_cards():
    html = """
    <div class="totall-product"><p>We found <strong>2</strong> items for you!</p></div>
    <div class="product-card">
      <h3><a href="https://striverempire.com/product/detail/item-1">Item 1</a></h3>
      <div class="h5">र 149</div>
    </div>
    <div class="product-card">
      <h3><a href="/product/detail/item-1/?sort=2">Item 1 Duplicate</a></h3>
      <div class="h5">र 149</div>
    </div>
    <div class="product-card">
      <h3><a href="https://striverempire.com/product/detail/item-2">Item 2</a></h3>
      <div class="h5">र 299</div>
    </div>
    """
    assert extract_expected_total_from_html(html) == 2
    items = extract_product_candidates_from_html(html, subcategory="Tops", parent_category="Women's")
    assert [i.url for i in items] == [
        "https://striverempire.com/product/detail/item-1",
        "https://striverempire.com/product/detail/item-2",
    ]
    assert all(i.subcategory == "Tops" for i in items)


def test_find_next_pagination_url_respects_visited():
    html = '<ul class="pagination"><li class="page-item"><a class="page-link" rel="next" href="/product/list/shirt?page=2">Next</a></li></ul>'
    next_url = find_next_pagination_url(html, visited_page_urls=set())
    assert next_url == "https://striverempire.com/product/list/shirt?page=2"
    assert find_next_pagination_url(html, visited_page_urls={next_url}) is None


def test_pagination_loop_with_mocked_playwright_load_more(tmp_path):
    logger = setup_logging(log_dir=tmp_path, level="WARNING")
    settings = {
        "site": {"base_url": "https://striverempire.com"},
        "browser": {"timeout_ms": 5000, "navigation_timeout_ms": 5000},
        "scraping": {
            "request_delay_seconds": 0.0,
            "max_retries": 1,
            "retry_backoff_seconds": 0.0,
            "max_pagination_pages": 10,
            "load_more_wait_ms": 10,
            "block_keywords": ["captcha"],
        },
        "categories": {},
    }
    scraper = CategoryScraper(settings, logger)

    page1_html = """
    <div class="totall-product">We found 3 items for you!</div>
    <div class="product-card"><h3><a href="/product/detail/p1">P1</a></h3></div>
    <div class="product-card"><h3><a href="/product/detail/p2">P2</a></h3></div>
    <button class="btn btn-outline-primary">Load More</button>
    """
    page2_html = """
    <div class="totall-product">We found 3 items for you!</div>
    <div class="product-card"><h3><a href="/product/detail/p1">P1</a></h3></div>
    <div class="product-card"><h3><a href="/product/detail/p2">P2</a></h3></div>
    <div class="product-card"><h3><a href="/product/detail/p3">P3</a></h3></div>
    """

    state = {"step": 1}
    page = MagicMock()
    page.goto.return_value = MagicMock(status=200)
    page.content.side_effect = lambda: page1_html if state["step"] == 1 else page2_html

    def locator_side_effect(selector):
        loc = MagicMock()
        if selector == ".error-content":
            loc.count.return_value = 0
        elif "Load More" in selector:
            loc.first = loc
            loc.count.return_value = 1 if state["step"] == 1 else 0
            loc.is_visible.return_value = state["step"] == 1
            loc.is_enabled.return_value = True

            def click_action(**kwargs):
                state["step"] = 2

            loc.click.side_effect = click_action
        elif selector == ".product-card":
            loc.count.return_value = 2 if state["step"] == 1 else 3
        return loc

    page.locator.side_effect = locator_side_effect

    candidates, expected = scraper.scrape_category_products(
        page, "https://striverempire.com/product/list/beauty-and-cosmetics", subcategory_name="Beauty and Cosmetic"
    )
    assert expected == 3
    assert [c.url for c in candidates] == [
        "https://striverempire.com/product/detail/p1",
        "https://striverempire.com/product/detail/p2",
        "https://striverempire.com/product/detail/p3",
    ]
    assert all(c.subcategory == "Beauty and Cosmetic" for c in candidates)


def test_ambiguous_subcategory_raises_clarification(tmp_path):
    logger = setup_logging(log_dir=tmp_path, level="WARNING")
    settings = {
        "site": {"base_url": "https://striverempire.com"},
        "browser": {"timeout_ms": 5000, "navigation_timeout_ms": 5000},
        "scraping": {
            "request_delay_seconds": 0.0,
            "max_retries": 1,
            "retry_backoff_seconds": 0.0,
            "max_pagination_pages": 10,
            "load_more_wait_ms": 10,
            "block_keywords": ["captcha"],
        },
        "main_categories": {
            "mens": {"label": "Men's", "url": "/product/list/mens", "aliases": ["men", "mens"]},
            "womens": {"label": "Women's", "url": "/product/list/womens", "aliases": ["women", "womens"]},
        },
        "categories": {},
    }
    scraper = CategoryScraper(settings, logger)
    home_html = """
    <header><ul>
      <li class="dropdown"><a href="#">Men's</a><ul class="dropdown-menu">
        <li><a class="dropdown-item" href="/product/list/blazers">Blazers</a></li>
      </ul></li>
      <li class="dropdown"><a href="#">Women's</a><ul class="dropdown-menu">
        <li><a class="dropdown-item" href="/product/list/blazers-1">Blazers.</a></li>
      </ul></li>
    </ul></header>
    """
    page = MagicMock()
    page.goto.return_value = MagicMock(status=200)
    page.content.return_value = home_html

    with pytest.raises(CategoryAmbiguityError):
        scraper.resolve_target_subcategories(page, "blazers")


def test_grouped_subcategory_scraping_preserves_order_and_deduplicates(tmp_path):
    logger = setup_logging(log_dir=tmp_path, level="WARNING")
    settings = {
        "site": {"base_url": "https://striverempire.com"},
        "browser": {"timeout_ms": 5000, "navigation_timeout_ms": 5000},
        "scraping": {
            "request_delay_seconds": 0.0,
            "max_retries": 1,
            "retry_backoff_seconds": 0.0,
            "max_pagination_pages": 10,
            "load_more_wait_ms": 10,
            "block_keywords": [],
        },
        "categories": {},
    }
    scraper = CategoryScraper(settings, logger)
    targets = [
        SubcategoryTarget(name="Shirt's", url="https://striverempire.com/product/list/shirts", parent_name="Women's"),
        SubcategoryTarget(name="Tops", url="https://striverempire.com/product/list/tops", parent_name="Women's"),
    ]

    html_by_url = {
        "https://striverempire.com/product/list/womens": "<div class='totall-product'>We found 3 items for you!</div>",
        "https://striverempire.com/product/list/shirts": (
            "<div class='totall-product'>We found 2 items for you!</div>"
            "<div class='product-card'><h3><a href='/product/detail/s1'>S1</a></h3></div>"
            "<div class='product-card'><h3><a href='/product/detail/shared'>Shared</a></h3></div>"
        ),
        "https://striverempire.com/product/list/tops": (
            "<div class='totall-product'>We found 2 items for you!</div>"
            "<div class='product-card'><h3><a href='/product/detail/shared'>Shared</a></h3></div>"
            "<div class='product-card'><h3><a href='/product/detail/t1'>T1</a></h3></div>"
        ),
    }
    current_url = {"u": ""}
    page = MagicMock()
    page.goto.side_effect = lambda url, **kw: current_url.__setitem__("u", url) or MagicMock(status=200)
    page.content.side_effect = lambda: html_by_url[current_url["u"]]

    def loc_side_effect(sel):
        loc = MagicMock()
        loc.first = loc
        loc.count.return_value = 0
        loc.is_visible.return_value = False
        return loc

    page.locator.side_effect = loc_side_effect

    cands, expected, warnings = scraper.scrape_targets_grouped(
        page,
        primary_url="https://striverempire.com/product/list/womens",
        targets=targets,
        is_parent_category=True,
    )
    assert expected == 3
    assert [(c.url.rsplit("/", 1)[-1], c.subcategory) for c in cands] == [
        ("s1", "Shirt's"),
        ("shared", "Shirt's"),
        ("t1", "Tops"),
    ]
    assert len(warnings) == 1


def test_check_for_block_raises_on_403_or_captcha():
    with pytest.raises(BlockedAccessError):
        check_for_block(403, "<html>Forbidden</html>", "https://striverempire.com")
    with pytest.raises(BlockedAccessError):
        check_for_block(200, "<html>Please verify you are human</html>", "https://striverempire.com")


def test_parse_product_detail_html_with_na_size_and_category():
    html = """
    <html><body>
      <h1 class="h4">Neem Tulsi Aloevera Soap.</h1>
      <div class="h4 d-flex align-items-center my-4">
        <del class="fs-sm">र <span id="category_mrp_1170">199</span></del>
        र <span id="category_dp_1170">149 </span><small>(Inclusive of all taxes)</small>
      </div>
      <div class="pb-3">
        <label class="form-label">Size</label>
        <input type="radio" class="CategoryPricesSelect" id="3180" data-dp="149">
        <label for="3180" class="btn">NA</label>
      </div>
      <ul class="list-unstyled">
        <li class="d-flex"><span>Category :</span> Beauty and cosmetic</li>
      </ul>
    </body></html>
    """
    name, price, size, cat = parse_product_detail_html_with_category(
        html, "https://striverempire.com/product/detail/soap"
    )
    assert name == "Neem Tulsi Aloevera Soap."
    assert price == Decimal("149.00")
    assert size == "NA"
    assert cat == "Beauty and Cosmetic"


def test_parse_product_detail_html_with_multiple_sizes_and_volume_fallback():
    html_sizes = """
    <html><body>
      <h1 class="h4">New Black Belt</h1>
      <div class="h4 d-flex align-items-center"><span id="category_dp_1">699</span></div>
      <input type="radio" class="CategoryPricesSelect" id="10" data-dp="699">
      <label for="10">34</label>
      <input type="radio" class="CategoryPricesSelect" id="11" data-dp="699">
      <label for="11">36</label>
    </body></html>
    """
    name, price, size = parse_product_detail_html(html_sizes, "https://striverempire.com/product/detail/belt")
    assert name == "New Black Belt"
    assert price == Decimal("699.00")
    assert size == "34, 36"

    html_vol = """
    <html><body>
      <h1>Herbal Hair Oil 200 ml</h1>
      <div class="h4 d-flex align-items-center"><span id="category_dp_2">299</span></div>
    </body></html>
    """
    _, _, vol_size = parse_product_detail_html(html_vol, "https://striverempire.com/product/detail/oil")
    assert vol_size == "200 ml"


def test_parse_product_detail_html_missing_price_never_guesses():
    html = "<html><body><h1>Broken Product</h1><div class='h4 d-flex align-items-center'><del>र 499</del></div></body></html>"
    with pytest.raises(PriceParseError):
        parse_product_detail_html(html, "https://striverempire.com/product/detail/broken")
