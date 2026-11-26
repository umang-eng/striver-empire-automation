"""CLI and interactive bot interface for Striver Empire Product Automation."""

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Callable, Optional

from playwright.sync_api import sync_playwright

from core.config_loader import load_settings
from core.exceptions import (
    BlockedAccessError,
    CategoryAmbiguityError,
    CategoryNotFoundError,
    StriverAutomationError,
    TaskParseError,
)
from core.logger import setup_logging
from core.models import ExtractionSummary, ParsedTask
from generator import resolve_header_color
from generator.excel_generator import generate_excel_report
from generator.pdf_generator import generate_pdf_report
from processor.message_parser import (
    build_known_category_phrases,
    build_output_stem,
    parse_task_message,
    resolve_filename_category_label,
)
from scraper.category_scraper import CategoryScraper
from scraper.product_details import ProductDetailsScraper


def _numbered_paths(excel_dir: Path, pdf_dir: Path, stem: str) -> tuple[Path, Path]:
    """Find the next unused numbered filename pair '<stem> (N).xlsx/.pdf'."""
    suffix = 2
    while True:
        excel_path = excel_dir / f"{stem} ({suffix}).xlsx"
        pdf_path = pdf_dir / f"{stem} ({suffix}).pdf"
        if not excel_path.exists() and not pdf_path.exists():
            return excel_path, pdf_path
        suffix += 1


def resolve_output_paths(
    excel_dir: Path,
    pdf_dir: Path,
    stem: str,
    policy: str = "prompt",
    prompt_fn: Optional[Callable[[str], str]] = None,
    logger: Optional[Any] = None,
) -> tuple[Path, Path]:
    """Resolve matching Excel and PDF paths without silently overwriting existing reports.

    policy:
      - 'replace': overwrite existing file if present
      - 'number' : create numbered alternative '<stem> (2).xlsx/.pdf'
      - 'prompt' : ask user on TTY whether to replace or number; fall back to 'number' if non-interactive
    """
    excel_path = excel_dir / f"{stem}.xlsx"
    pdf_path = pdf_dir / f"{stem}.pdf"

    if not excel_path.exists() and not pdf_path.exists():
        return excel_path, pdf_path

    normalized_policy = (policy or "prompt").strip().lower()
    if normalized_policy == "replace":
        if logger:
            logger.info("Duplicate file policy='replace': overwriting %s.*", stem)
        return excel_path, pdf_path

    if normalized_policy == "prompt":
        can_prompt = prompt_fn is not None or sys.stdin.isatty()
        if can_prompt:
            asker = prompt_fn or input
            while True:
                choice = asker(
                    f"Report '{stem}' already exists in output/. [R]eplace existing or create [N]umbered alternative? (r/n): "
                ).strip().lower()
                if choice in {"r", "replace"}:
                    return excel_path, pdf_path
                if choice in {"n", "number", "numbered", ""}:
                    return _numbered_paths(excel_dir, pdf_dir, stem)
                print("Please enter 'r' to replace or 'n' for a numbered alternative.")

        if logger:
            logger.warning(
                "Report '%s' already exists and no interactive terminal is available; "
                "creating numbered alternative instead of overwriting.",
                stem,
            )

    return _numbered_paths(excel_dir, pdf_dir, stem)


def run_task(
    task_message: str,
    settings: dict[str, Any],
    logger,
    dry_run: bool = False,
    limit: int = 0,
    duplicate_policy: Optional[str] = None,
) -> tuple[ExtractionSummary, Optional[Path], Optional[Path]]:
    """Execute one full automation run (or dry-run) for a submitted task message."""
    known_categories = build_known_category_phrases(settings)
    task: ParsedTask = parse_task_message(task_message, known_categories=known_categories)

    started_at = datetime.now()
    excel_dir = Path(settings["output"]["excel_dir"])
    pdf_dir = Path(settings["output"]["pdf_dir"])
    policy = duplicate_policy or settings.get("output", {}).get("duplicate_file_policy", "prompt")

    logger.info(
        "Parsed task -> Category=%r | Discount=%s",
        task.category,
        task.discount_display,
    )

    browser_cfg = settings["browser"]
    category_scraper = CategoryScraper(settings, logger)
    details_scraper = ProductDetailsScraper(settings, logger)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=bool(browser_cfg.get("headless", True)))
        context = browser.new_context(
            viewport=browser_cfg.get("viewport", {"width": 1440, "height": 900}),
            user_agent=browser_cfg.get("user_agent"),
        )
        page = context.new_page()
        page.set_default_timeout(int(browser_cfg.get("timeout_ms", 30000)))

        try:
            primary_url, targets, is_parent = category_scraper.resolve_target_subcategories(
                page, task.category
            )
            display_category = resolve_filename_category_label(
                task, targets=targets, is_parent_category=is_parent
            )
            stem = build_output_stem(task, display_category=display_category)

            logger.info(
                "Resolved primary URL: %s | Subcategories (%d): %s | Output stem: %s",
                primary_url,
                len(targets),
                [t.name for t in targets],
                stem,
            )

            candidates, expected_total, cat_warnings = category_scraper.scrape_targets_grouped(
                page,
                primary_url=primary_url,
                targets=targets,
                is_parent_category=is_parent,
            )
            if limit > 0 and len(candidates) > limit:
                logger.info("Applying --limit=%d (discovered %d total).", limit, len(candidates))
                candidates = candidates[:limit]

            summary = ExtractionSummary(
                task=task,
                category_url=primary_url,
                started_at=started_at,
                expected_total_from_site=expected_total,
                discovered_count=len(candidates),
                subcategories_scraped=[t.name for t in targets],
                warnings=cat_warnings,
            )

            if dry_run:
                summary.completed_at = datetime.now()
                logger.info(
                    "[DRY-RUN] Resolved %d subcategory(s) and %d unique product(s). "
                    "Would write Excel=%s and PDF=%s.",
                    len(targets),
                    len(candidates),
                    excel_dir / f"{stem}.xlsx",
                    pdf_dir / f"{stem}.pdf",
                )
                return summary, None, None

            records, failures = details_scraper.scrape_all_products(page, candidates, task)
            summary.records = records
            summary.failures = failures
            summary.completed_at = datetime.now()

            if expected_total is not None and limit == 0 and len(candidates) != expected_total:
                warning_msg = (
                    f"Site reported {expected_total} items, but discovered {len(candidates)} unique product URLs."
                )
                summary.warnings.append(warning_msg)
                logger.warning(warning_msg)

        finally:
            context.close()
            browser.close()

    excel_path, pdf_path = resolve_output_paths(
        excel_dir, pdf_dir, stem, policy=policy, logger=logger
    )
    run_header_color = resolve_header_color(settings)
    generated_excel = generate_excel_report(
        summary, excel_path, settings, header_color=run_header_color
    )
    generated_pdf = generate_pdf_report(
        summary, pdf_path, settings, logger=logger, header_color=run_header_color
    )

    logger.info("Generated Excel report: %s", generated_excel)
    logger.info("Generated PDF report:   %s", generated_pdf)
    return summary, generated_excel, generated_pdf


def _print_summary(
    summary: ExtractionSummary,
    excel_path: Optional[Path],
    pdf_path: Optional[Path],
    dry_run: bool,
) -> None:
    """Print a concise human-readable summary to stdout (never written into Excel/PDF)."""
    print("\n=== Extraction Summary ===")
    print(f"Category        : {summary.task.category}")
    print(f"Discount        : {summary.task.discount_display}")
    print(f"Category URL    : {summary.category_url}")
    print(f"Subcategories   : {', '.join(summary.subcategories_scraped)}")
    print(f"Products Found  : {summary.discovered_count}")
    if dry_run:
        print("Mode            : DRY-RUN (no product detail pages fetched, no files written)")
        return
    print(f"Succeeded       : {summary.succeeded_count}")
    print(f"Failed          : {summary.failed_count}")
    if excel_path:
        print(f"Excel File      : {excel_path}")
    if pdf_path:
        print(f"PDF File        : {pdf_path}")
    if summary.failures:
        print("\nFailed Products:")
        for idx, fail in enumerate(summary.failures, start=1):
            print(f"  {idx}. {fail.name_hint} ({fail.url}) -> {fail.reason}")
    if summary.warnings:
        print("\nWarnings:")
        for w in summary.warnings:
            print(f"  - {w}")


def _interactive_loop(
    settings: dict[str, Any],
    logger,
    dry_run: bool,
    limit: int,
    duplicate_policy: Optional[str],
) -> int:
    """Simple interactive bot-style CLI interface for submitting tasks."""
    print("Striver Empire Product Automation — Interactive Bot Mode")
    print("Enter a task (e.g. 'women 25%') or type 'exit' to quit.\n")
    while True:
        try:
            raw = input("Task> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return 0

        if not raw:
            continue
        if raw.lower() in {"exit", "quit", "q"}:
            print("Goodbye.")
            return 0

        try:
            summary, excel_path, pdf_path = run_task(
                raw,
                settings=settings,
                logger=logger,
                dry_run=dry_run,
                limit=limit,
                duplicate_policy=duplicate_policy,
            )
            _print_summary(summary, excel_path, pdf_path, dry_run=dry_run)
            print()
        except BlockedAccessError as exc:
            logger.error("Blocked by target website: %s", exc)
            print(f"\n[BLOCKED] {exc}\n", file=sys.stderr)
            return 2
        except CategoryAmbiguityError as exc:
            logger.warning("Category clarification needed: %s", exc)
            print(f"\n[CLARIFICATION NEEDED] {exc}\n")
        except (TaskParseError, CategoryNotFoundError, StriverAutomationError) as exc:
            logger.error("Task failed: %s", exc)
            print(f"\n[ERROR] {exc}\n", file=sys.stderr)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="striver-empire-automation",
        description="Striver Empire Product Automation — scrape category products and export Excel & PDF.",
    )
    parser.add_argument(
        "--task",
        type=str,
        help="Task message, e.g. 'women 25%'",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch interactive bot prompt to submit one or more tasks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse task, resolve category/subcategories, and list discovered product count without writing Excel/PDF.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/settings.json",
        help="Path to JSON configuration file (default: config/settings.json).",
    )
    parser.add_argument(
        "--on-duplicate",
        choices=["prompt", "number", "replace"],
        default=None,
        help="Behavior when output filename already exists (default: from settings.json).",
    )
    parser.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=None,
        help="Run browser in headless mode.",
    )
    parser.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Run browser with visible UI window.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Override browser timeout in milliseconds.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=None,
        help="Override polite delay between requests in seconds.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional max number of products to inspect (0 = all products).",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    settings = load_settings(args.config)
    if args.headless is not None:
        settings["browser"]["headless"] = args.headless
    if args.timeout is not None:
        settings["browser"]["timeout_ms"] = args.timeout
        settings["browser"]["navigation_timeout_ms"] = max(args.timeout, 15000)
    if args.delay is not None:
        settings["scraping"]["request_delay_seconds"] = args.delay

    log_cfg = settings.get("logging", {})
    logger = setup_logging(
        log_dir=log_cfg.get("log_dir", "logs"),
        file_name=log_cfg.get("file_name", "striver_automation.log"),
        level=log_cfg.get("level", "INFO"),
    )

    if args.interactive or not args.task:
        return _interactive_loop(
            settings,
            logger,
            dry_run=args.dry_run,
            limit=args.limit,
            duplicate_policy=args.on_duplicate,
        )

    try:
        summary, excel_path, pdf_path = run_task(
            args.task,
            settings=settings,
            logger=logger,
            dry_run=args.dry_run,
            limit=args.limit,
            duplicate_policy=args.on_duplicate,
        )
        _print_summary(summary, excel_path, pdf_path, dry_run=args.dry_run)
        return 0
    except BlockedAccessError as exc:
        logger.error("Blocked by website protection: %s", exc)
        print(f"ERROR (Blocked): {exc}", file=sys.stderr)
        return 2
    except CategoryAmbiguityError as exc:
        logger.warning("Category clarification needed: %s", exc)
        print(f"CLARIFICATION NEEDED: {exc}", file=sys.stderr)
        return 1
    except StriverAutomationError as exc:
        logger.error("Automation failed: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
