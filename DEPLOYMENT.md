# Vercel & Worker Deployment Guide

This repository uses a **Vercel-first root layout** so importing the GitHub repo into Vercel works immediately with default settings (`Root Directory: .`), while keeping the Python Playwright worker and CLI intact.

## Architecture

- **Vercel Web App & Serverless API Proxy (repo root: `src/`, `public/`, `package.json`, `vercel.json`)**:
  - Serves the Next.js 16 Apple Liquid Glass interface and `public/video/background.mp4`.
  - Exposes `/api/health`, `/api/categories`, `/api/tasks`, `/api/tasks/[taskId]/progress`, `/api/tasks/[taskId]/events`, and `/api/tasks/[taskId]/download/{excel,pdf}` as Vercel functions.
- **Python Playwright Worker (`backend/`, `core/`, `processor/`, `scraper/`, `generator/`, `Dockerfile`, `render.yaml`)**:
  - Runs headless Chromium + BeautifulSoup + OpenPyXL + ReportLab (outside Vercel's 250 MB serverless bundle and timeout limits).
  - Persists job state in PostgreSQL (`DATABASE_URL`) and files in Vercel Blob (`BLOB_READ_WRITE_TOKEN`) or S3/R2.

## Deploy in 2 Steps

### Step 1: Deploy the Python Playwright Worker (Render or Railway)
1. Create a new Web Service from `https://github.com/umang-eng/striver-empire-automation` using `Dockerfile` (or import `render.yaml` on Render).
2. Configure environment variables:
   - `BACKEND_API_KEY` — long random secret
   - `ALLOWED_ORIGINS` — `https://<your-vercel-app>.vercel.app`
   - `DATABASE_URL` — PostgreSQL URL (e.g. Neon / Supabase / Render Postgres)
   - `BLOB_READ_WRITE_TOKEN` (Vercel Blob) **or** `S3_BUCKET`, `S3_ENDPOINT_URL`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`

### Step 2: Deploy the Web Page on Vercel
1. Import `https://github.com/umang-eng/striver-empire-automation` in Vercel with default **Root Directory** (`.`) and **Framework Preset: Next.js**.
2. Add Environment Variables in Vercel Project Settings:
   - `PYTHON_WORKER_URL` = `https://<your-worker-url>`
   - `BACKEND_API_KEY` = same secret as Step 1
3. Click **Deploy**.

## Local Development (macOS)

Terminal 1 — Python FastAPI & Playwright Worker (`http://127.0.0.1:8000`):
```bash
cd /Users/umang/Music/Striver-Empire-automation
.venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — Next.js Web Server (`http://localhost:3000`):
```bash
cd /Users/umang/Music/Striver-Empire-automation
npm run dev
```
