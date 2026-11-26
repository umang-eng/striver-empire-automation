"""FastAPI web server exposing task submission, SSE/polling progress, and secure downloads."""

import asyncio
from collections import defaultdict, deque
import json
import os
import re
import time
from typing import Any, Optional
import uuid

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.job_store import JobStore
from backend.storage import StorageManager
from backend.worker import TaskRunner
from core.config_loader import load_settings
from core.exceptions import TaskParseError
from core.logger import setup_logging
from processor.message_parser import build_known_category_phrases, parse_task_message

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.I)


class _RateLimiter:
    """Simple sliding-window per-IP rate limiter."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, client_ip: str) -> None:
        now = time.monotonic()
        bucket = self._hits[client_ip]
        while bucket and (now - bucket[0]) > self.window_seconds:
            bucket.popleft()
        if len(bucket) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please wait a moment before submitting again.",
            )
        bucket.append(now)


class CreateTaskRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=200)


def _validate_task_id(task_id: str) -> str:
    if not _UUID_RE.match(task_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid task ID format.")
    return task_id


def _sanitize_job_response(job: dict[str, Any]) -> dict[str, Any]:
    """Strip internal filesystem/storage keys before returning job state to clients."""
    return {
        "task_id": job["task_id"],
        "raw_message": job["raw_message"],
        "category": job["category"],
        "discount_percent": job["discount_percent"],
        "status": job["status"],
        "stage": job["stage"],
        "stage_index": job["stage_index"],
        "total_stages": job["total_stages"],
        "progress_percent": job["progress_percent"],
        "products_discovered": job["products_discovered"],
        "products_extracted": job["products_extracted"],
        "failed_products": job["failed_products"],
        "current_subcategory": job["current_subcategory"],
        "subcategories": job["subcategories"],
        "failures": job["failures"],
        "warnings": job["warnings"],
        "excel_filename": job["excel_filename"],
        "pdf_filename": job["pdf_filename"],
        "excel_ready": bool(job["excel_storage_key"]),
        "pdf_ready": bool(job["pdf_storage_key"]),
        "error_message": job["error_message"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "updated_at": job["updated_at"],
    }


def _build_category_catalog(settings: dict[str, Any]) -> dict[str, Any]:
    """Return structured main categories & subcategory templates matching the live site."""
    groups = [
        {
            "id": "mens",
            "label": "Men's",
            "main_templates": ["men 5%", "men 10%", "men 15%"],
            "subcategories": [
                {"name": "Shirt", "template": "men shirt 5%"},
                {"name": "Formal Pants", "template": "men formal pants 5%"},
                {"name": "T-shirt", "template": "men t-shirt 5%"},
                {"name": "Jeans", "template": "men jeans 5%"},
                {"name": "Shorts", "template": "men shorts 5%"},
                {"name": "Lower", "template": "men lower 5%"},
                {"name": "Blazers", "template": "men blazers 5%"},
                {"name": "Sando", "template": "men sando 5%"},
                {"name": "Basket Jacket", "template": "men basket jacket 5%"},
                {"name": "Co-ord Sets", "template": "men co-ord sets 5%"},
            ],
        },
        {
            "id": "womens",
            "label": "Women's",
            "main_templates": ["women 5%", "women 10%", "women 15%"],
            "subcategories": [
                {"name": "Shirt's", "template": "women shirts 5%"},
                {"name": "Formal Pant", "template": "women formal pants 5%"},
                {"name": "Tops", "template": "women tops 5%"},
                {"name": "Women Jeans", "template": "women jeans 5%"},
                {"name": "Blazers", "template": "women blazers 5%"},
            ],
        },
        {
            "id": "beauty-and-cosmetics",
            "label": "Beauty & Cosmetics",
            "main_templates": [
                "beauty and cosmetics 5%",
                "beauty and cosmetics 10%",
                "beauty and cosmetics 15%",
            ],
            "subcategories": [
                {"name": "Beauty and Cosmetic", "template": "beauty and cosmetic 5%"},
            ],
        },
        {
            "id": "accessories",
            "label": "Accessories",
            "main_templates": ["accessories 5%", "accessories 10%", "accessories 15%"],
            "subcategories": [
                {"name": "Belts", "template": "accessories belts 5%"},
                {"name": "Ties", "template": "accessories ties 5%"},
                {"name": "Socks", "template": "accessories socks 5%"},
                {"name": "Cap", "template": "accessories cap 5%"},
            ],
        },
        {
            "id": "winter",
            "label": "Winter",
            "main_templates": ["winter 5%", "winter 10%", "winter 15%"],
            "subcategories": [
                {"name": "Sweater", "template": "winter sweater 5%"},
                {"name": "Hoodie", "template": "winter hoodie 5%"},
                {"name": "Jacket", "template": "winter jacket 5%"},
                {"name": "High Neck", "template": "winter high neck 5%"},
            ],
        },
        {
            "id": "home-living",
            "label": "Home & Living",
            "main_templates": [
                "home and living 5%",
                "home and living 10%",
                "home and living 15%",
            ],
            "subcategories": [
                {"name": "Bedsheets", "template": "home and living bedsheets 5%"},
                {"name": "Towels", "template": "home and living towels 5%"},
                {"name": "Foot Mat", "template": "home and living foot mat 5%"},
            ],
        },
    ]
    return {"groups": groups, "site": settings["site"]["base_url"]}


def create_app(
    config_path: str = "config/settings.json",
    database_url: Optional[str] = None,
    sqlite_path: str = "data/jobs.db",
) -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = load_settings(config_path)
    log_cfg = settings.get("logging", {})
    logger = setup_logging(
        log_dir=log_cfg.get("log_dir", "logs"),
        file_name=log_cfg.get("file_name", "striver_automation.log"),
        level=log_cfg.get("level", "INFO"),
    )
    job_store = JobStore(database_url=database_url, sqlite_path=sqlite_path)
    storage = StorageManager()
    runner = TaskRunner(settings=settings, logger=logger, job_store=job_store, storage=storage)
    submit_limiter = _RateLimiter(
        max_requests=int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "20")),
        window_seconds=int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
    )
    api_key = (os.getenv("BACKEND_API_KEY") or "").strip()

    app = FastAPI(title="Striver Empire Automation API", version="1.0.0")

    allowed_origins = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-API-Key"],
    )

    def verify_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
        if api_key and x_api_key != api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized.")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "storage_mode": storage.mode}

    @app.get("/api/categories")
    def get_categories(_: None = Depends(verify_api_key)) -> dict[str, Any]:
        return _build_category_catalog(settings)

    @app.post("/api/tasks", status_code=status.HTTP_202_ACCEPTED)
    def create_task(
        payload: CreateTaskRequest,
        request: Request,
        _: None = Depends(verify_api_key),
    ) -> dict[str, Any]:
        client_ip = request.client.host if request.client else "unknown"
        submit_limiter.check(client_ip)

        known = build_known_category_phrases(settings)
        try:
            parsed = parse_task_message(payload.message, known_categories=known)
        except TaskParseError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        job, deduplicated = runner.submit(parsed)
        data = _sanitize_job_response(job)
        data["deduplicated"] = deduplicated
        return data

    @app.get("/api/tasks/{task_id}")
    def get_task(task_id: str, _: None = Depends(verify_api_key)) -> dict[str, Any]:
        _validate_task_id(task_id)
        job = job_store.get_job(task_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        return _sanitize_job_response(job)

    @app.get("/api/tasks/{task_id}/progress")
    def get_task_progress(task_id: str, _: None = Depends(verify_api_key)) -> dict[str, Any]:
        _validate_task_id(task_id)
        job = job_store.get_job(task_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        return _sanitize_job_response(job)

    @app.get("/api/tasks/{task_id}/events")
    async def stream_task_progress(
        task_id: str,
        request: Request,
        _: None = Depends(verify_api_key),
    ) -> StreamingResponse:
        _validate_task_id(task_id)
        if not job_store.get_job(task_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")

        async def event_stream():
            last_payload = ""
            while True:
                if await request.is_disconnected():
                    break
                job = job_store.get_job(task_id)
                if not job:
                    yield f"event: error\ndata: {json.dumps({'detail': 'Task deleted'})}\n\n"
                    break
                sanitized = _sanitize_job_response(job)
                encoded = json.dumps(sanitized)
                if encoded != last_payload:
                    last_payload = encoded
                    yield f"data: {encoded}\n\n"
                if sanitized["status"] in ("completed", "failed"):
                    break
                await asyncio.sleep(0.8)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    @app.get("/api/tasks/{task_id}/download/excel")
    def download_excel(task_id: str, _: None = Depends(verify_api_key)) -> Response:
        _validate_task_id(task_id)
        job = job_store.get_job(task_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if job["status"] != "completed" or not job["excel_storage_key"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Excel report is not ready yet.")
        content = storage.read_bytes(job["excel_storage_key"])
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Excel file not found in storage.")
        filename = job["excel_filename"] or f"{task_id}.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.get("/api/tasks/{task_id}/download/pdf")
    def download_pdf(task_id: str, _: None = Depends(verify_api_key)) -> Response:
        _validate_task_id(task_id)
        job = job_store.get_job(task_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        if job["status"] != "completed" or not job["pdf_storage_key"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PDF report is not ready yet.")
        content = storage.read_bytes(job["pdf_storage_key"])
        if content is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found in storage.")
        filename = job["pdf_filename"] or f"{task_id}.pdf"
        return Response(
            content=content,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.delete("/api/tasks/{task_id}")
    def delete_task(task_id: str, _: None = Depends(verify_api_key)) -> dict[str, Any]:
        _validate_task_id(task_id)
        job = job_store.get_job(task_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
        runner.cancel(task_id)
        storage.delete_file(job.get("excel_storage_key", ""))
        storage.delete_file(job.get("pdf_storage_key", ""))
        job_store.delete_job(task_id)
        return {"deleted": True, "task_id": task_id}

    return app


app = create_app()
