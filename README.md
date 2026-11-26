# Striver Empire Product Automation

A Vercel-ready full-stack web application (Next.js 16 + FastAPI + Playwright) with CLI support that parses task messages (e.g. `women 25%`, `beauty and cosmetics 5%`, `men formal pants 12.5%`), discovers main categories and ordered subcategories on `https://striverempire.com/`, extracts every product across paginated/Load More listings and individual detail pages, computes discounted prices with exact `Decimal` arithmetic, and exports matching green/randomized-header Excel (`.xlsx`) and single-page landscape PDF (`.pdf`) tables.

## Vercel-First Project Structure

```text
Striver-Empire-automation/
├── package.json                   # Root Next.js app (zero-config Vercel detection)
├── next.config.ts                 # Next.js + Turbopack + inline video headers
├── vercel.json                    # Vercel framework, API function maxDuration & security headers
├── .vercelignore                  # Excludes Python venv, tests, and local runtime files from Vercel
├── tsconfig.json
├── eslint.config.mjs
├── public/
│   └── video/                     # Full-screen 4K looping background video + poster
├── src/
│   ├── app/                       # Next.js App Router page & Vercel /api/* proxy routes
│   ├── components/                # Apple Liquid Glass UI components
│   └── lib/                       # Validation, types, proxy helpers
├── main.py                        # CLI & interactive bot entry point
├── Dockerfile                     # Docker image for Python Playwright worker
├── render.yaml                    # Render blueprint for Python Playwright worker
├── DEPLOYMENT.md                  # Step-by-step Vercel + Worker deployment guide
├── pytest.ini
├── requirements.txt
├── .env.example
├── config/
│   └── settings.json              # Site URLs, categories, duplicate policy & report settings
├── core/                          # Config loader, exceptions, logging, dataclasses
├── processor/                     # '<Category> <Discount>%' parser & Decimal calculator
├── scraper/                       # Category/subcategory tree & product detail scrapers
├── generator/                     # OpenPyXL Excel & single-page ReportLab PDF generators
├── backend/                       # FastAPI REST + SSE + download + PostgreSQL/S3/Blob adapters
├── tests/                         # Python unit & API tests (pytest)
├── logs/                          # Rotating execution logs
└── output/
    ├── Excel/                     # Generated .xlsx files
    └── PDF/                       # Generated .pdf files
```

## Setup Instructions (macOS)

```bash
cd /Users/umang/Music/Striver-Empire-automation

# 1. Python backend & Playwright
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium

# 2. Next.js web frontend (root)
npm install
```

## Running Locally

Terminal 1 — Python FastAPI & Playwright worker (`http://127.0.0.1:8000`):
```bash
.venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — Next.js web server (`http://localhost:3000`):
```bash
npm run dev
```

Open `http://localhost:3000` in your browser. See [DEPLOYMENT.md](DEPLOYMENT.md) to host on **Vercel** + Render/Railway.

## CLI Usage & Tests

```bash
# Run CLI extractions
.venv/bin/python main.py --task "women 25%"
.venv/bin/python main.py --task "beauty and cosmetics 5%"
.venv/bin/python main.py --task "women formal pant 5%" --on-duplicate number

# Run all Python tests
.venv/bin/pytest -v

# Lint & production build for Vercel web app
npm run lint && npm run build
```
