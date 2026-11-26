# Deployment & Local Development Guide

## Architecture Overview

- **Frontend + Vercel API Proxy (`frontend/`)**: Next.js 16 + React + TypeScript + Tailwind CSS deployed on **Vercel**. Includes server-side `/api/*` proxy routes so browser clients never communicate directly with internal worker secrets.
- **Python Scraping Worker (`backend/api.py` + existing `core/`, `processor/`, `scraper/`, `generator/`)**: FastAPI + Uvicorn running Playwright Chromium asynchronously via `ThreadPoolExecutor`, persisting job state to **PostgreSQL** (`DATABASE_URL`, or SQLite locally) and generated Excel/PDF artifacts to **S3/R2** or **Vercel Blob** (or `output/` locally).

## Local Development (macOS)

Terminal 1 — Start Python FastAPI & Playwright Worker:
```bash
cd /Users/umang/Music/Striver-Empire-automation
.venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — Start Next.js Frontend:
```bash
cd /Users/umang/Music/Striver-Empire-automation/frontend
npm run dev
```

Open http://localhost:3000 in your browser.

## Production Deployment

### 1. Deploy the Python Playwright Worker (Railway / Render / Fly.io)
Use the root `Dockerfile`:
- Set environment variables:
  - `BACKEND_API_KEY` (strong random secret)
  - `ALLOWED_ORIGINS` (your Vercel domain, e.g. `https://striver-automation.vercel.app`)
  - `DATABASE_URL` (PostgreSQL connection string, e.g. Neon / Supabase / Railway Postgres)
  - Object storage (either `BLOB_READ_WRITE_TOKEN` for Vercel Blob, OR `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`)

### 2. Deploy the Frontend on Vercel
- Set Vercel **Root Directory** to `frontend`.
- Configure Environment Variables in Vercel Project Settings:
  - `PYTHON_WORKER_URL=https://your-python-worker.up.railway.app`
  - `BACKEND_API_KEY=<same secret as worker>`
- Deploy (`vercel --prod` or Git integration).
