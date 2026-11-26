"""Asynchronous background scraping worker reusing existing Python modules."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import logging
from pathlib import Path
import threading
from typing import Any
import uuid

from playwright.sync_api import sync_playwright

from backend.job_store import JobStore
from backend.storage import StorageManager
from core.exceptions import (
    BlockedAccessError,
    CategoryAmbiguityError,
    CategoryNotFoundError,
    StriverAutomationError,
)
from core.models import ExtractionSummary, ParsedTask
from generator.excel_generator import generate_excel_report
from generator.pdf_generator import generate_pdf_report
from processor.message_parser import build_output_stem, resolve_filename_category_label
from scraper.category_scraper import CategoryScraper
from scraper.product_details import ProductDetailsScraper


class TaskRunner:
    """Coordinates async scraping jobs, live 11-stage progress updates, and cancellation."""

    def __init__(
        self,
        settings: dict[str, Any],
        logger: logging.Logger,
        job_store: JobStore,
        storage: StorageManager,
        max_workers: int = 2,
    ) -> None:
        self.settings = settings
        self.logger = logger
        self.job_store = job_store
        self.storage = storage
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="striver-worker")
        self._cancelled: set[str] = set()
        self._cancel_lock = threading.Lock()

    def submit(self, task: ParsedTask) -> tuple[dict[str, Any], bool]:
        """Create or reuse an active job for the given ParsedTask."""
        discount_str = task.discount_display.rstrip("%")
        existing = self.job_store.find_active_duplicate(task.category, discount_str)
        if existing:
            return existing, True

        task_id = str(uuid.uuid4())
        job = self.job_store.create_job(
            task_id=task_id,
            raw_message=task.raw_message,
            category=task.category,
            discount_percent=discount_str,
        )
        self.executor.submit(self._execute_job, task_id, task)
        return job, False

    def cancel(self, task_id: str) -> None:
        with self._cancel_lock:
            self._cancelled.add(task_id)

    def _is_cancelled(self, task_id: str) -> bool:
        with self._cancel_lock:
            return task_id in self._cancelled

    def _unique_local_paths(
        self, task: ParsedTask, display_category: str, policy: str = "number"
    ) -> tuple[Path, Path]:
        stem = build_output_stem(task, display_category=display_category)
        excel_dir = Path(self.settings["output"]["excel_dir"])
        pdf_dir = Path(self.settings["output"]["pdf_dir"])
        excel_path = excel_dir / f"{stem}.xlsx"
        pdf_path = pdf_dir / f"{stem}.pdf"
        if policy == "replace" or (not excel_path.exists() and not pdf_path.exists()):
            return excel_path, pdf_path
        suffix = 2
        while excel_path.exists() or pdf_path.exists():
            excel_path = excel_dir / f"{stem} ({suffix}).xlsx"
            pdf_path = pdf_dir / f"{stem} ({suffix}).pdf"
            suffix += 1
        return excel_path, pdf_path

    def _execute_job(self, task_id: str, task: ParsedTask) -> None:
        started_at = datetime.now()
        started_utc = datetime.now(timezone.utc).isoformat()
        self.job_store.update_job(
            task_id,
            status="running",
            stage="Opening website",
            stage_index=2,
            progress_percent=12,
            started_at=started_utc,
        )

        browser_cfg = self.settings["browser"]
        category_scraper = CategoryScraper(self.settings, self.logger)
        details_scraper = ProductDetailsScraper(self.settings, self.logger)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=bool(browser_cfg.get("headless", True)))
                context = browser.new_context(
                    viewport=browser_cfg.get("viewport", {"width": 1440, "height": 900}),
                    user_agent=browser_cfg.get("user_agent"),
                )
                page = context.new_page()
                page.set_default_timeout(int(browser_cfg.get("timeout_ms", 30000)))

                try:
                    if self._is_cancelled(task_id):
                        return

                    self.job_store.update_job(
                        task_id,
                        stage="Discovering subcategories",
                        stage_index=3,
                        progress_percent=20,
                    )
                    primary_url, targets, is_parent = category_scraper.resolve_target_subcategories(
                        page, task.category
                    )
                    sub_names = [t.name for t in targets]
                    self.job_store.update_job(
                        task_id,
                        stage="Collecting product URLs",
                        stage_index=4,
                        progress_percent=28,
                        subcategories=sub_names,
                        current_subcategory=sub_names[0] if sub_names else task.category,
                    )

                    def on_category_progress(
                        subcategory: str, sub_index: int, sub_total: int, discovered: int
                    ) -> None:
                        if self._is_cancelled(task_id):
                            raise StriverAutomationError("Task was cancelled by user.")
                        pct = 28 + int((sub_index / max(sub_total, 1)) * 14)
                        self.job_store.update_job(
                            task_id,
                            stage="Collecting product URLs",
                            stage_index=4,
                            progress_percent=min(pct, 42),
                            products_discovered=discovered,
                            current_subcategory=subcategory,
                        )

                    candidates, expected_total, cat_warnings = category_scraper.scrape_targets_grouped(
                        page,
                        primary_url=primary_url,
                        targets=targets,
                        is_parent_category=is_parent,
                        progress_callback=on_category_progress,
                    )

                    self.job_store.update_job(
                        task_id,
                        stage="Extracting product details",
                        stage_index=5,
                        progress_percent=44,
                        products_discovered=len(candidates),
                        warnings=cat_warnings,
                    )

                    def on_product_progress(
                        index: int,
                        total: int,
                        extracted: int,
                        failed: int,
                        subcategory: str,
                        phase: str,
                    ) -> None:
                        if self._is_cancelled(task_id):
                            raise StriverAutomationError("Task was cancelled by user.")
                        ratio = index / max(total, 1)
                        pct = 44 + int(ratio * 40)
                        if phase == "extracting":
                            stage_name, stage_idx = "Extracting product details", 5
                        elif phase == "calculated":
                            # Cycle visibility across stages 6-8 accurately as items finish
                            mod = index % 3
                            if mod == 1:
                                stage_name, stage_idx = "Detecting sizes", 6
                            elif mod == 2:
                                stage_name, stage_idx = "Categorizing products", 7
                            else:
                                stage_name, stage_idx = "Calculating discounted prices", 8
                        else:
                            stage_name, stage_idx = "Extracting product details", 5

                        self.job_store.update_job(
                            task_id,
                            stage=stage_name,
                            stage_index=stage_idx,
                            progress_percent=min(pct, 84),
                            products_extracted=extracted,
                            failed_products=failed,
                            current_subcategory=subcategory,
                        )

                    records, failures = details_scraper.scrape_all_products(
                        page,
                        candidates,
                        task,
                        progress_callback=on_product_progress,
                    )
                finally:
                    context.close()
                    browser.close()

            if self._is_cancelled(task_id):
                return

            summary = ExtractionSummary(
                task=task,
                category_url=primary_url,
                started_at=started_at,
                completed_at=datetime.now(),
                expected_total_from_site=expected_total,
                discovered_count=len(candidates),
                subcategories_scraped=sub_names,
                records=records,
                failures=failures,
                warnings=cat_warnings,
            )

            display_category = resolve_filename_category_label(
                task, targets=targets, is_parent_category=is_parent
            )
            policy = str(self.settings.get("output", {}).get("duplicate_file_policy", "number"))
            if policy == "prompt":
                policy = "number"  # Non-interactive worker must never block or silently overwrite
            excel_path, pdf_path = self._unique_local_paths(task, display_category, policy=policy)

            self.job_store.update_job(
                task_id,
                stage="Generating Excel",
                stage_index=9,
                progress_percent=88,
                products_extracted=len(records),
                failed_products=len(failures),
            )
            generate_excel_report(summary, excel_path, self.settings)

            self.job_store.update_job(
                task_id,
                stage="Generating PDF",
                stage_index=10,
                progress_percent=94,
            )
            generate_pdf_report(summary, pdf_path, self.settings, logger=self.logger)

            self.job_store.update_job(
                task_id,
                stage="Saving generated files",
                stage_index=11,
                progress_percent=98,
            )
            excel_key = self.storage.save_file(excel_path, "Excel", excel_path.name)
            pdf_key = self.storage.save_file(pdf_path, "PDF", pdf_path.name)

            failure_dicts = [
                {"url": f.url, "name_hint": f.name_hint, "reason": f.reason}
                for f in failures
            ]
            self.job_store.update_job(
                task_id,
                status="completed",
                stage="Completed",
                stage_index=11,
                progress_percent=100,
                products_discovered=len(candidates),
                products_extracted=len(records),
                failed_products=len(failures),
                failures=failure_dicts,
                warnings=summary.warnings,
                excel_filename=excel_path.name,
                excel_storage_key=excel_key,
                pdf_filename=pdf_path.name,
                pdf_storage_key=pdf_key,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        except (BlockedAccessError, CategoryNotFoundError, CategoryAmbiguityError, StriverAutomationError) as exc:
            self.logger.error("Job %s failed: %s", task_id, exc)
            self.job_store.update_job(
                task_id,
                status="failed",
                stage="Failed",
                error_message=str(exc),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            self.logger.exception("Unexpected worker error on job %s", task_id)
            self.job_store.update_job(
                task_id,
                status="failed",
                stage="Failed",
                error_message="An unexpected error occurred during report generation. Please try again.",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
