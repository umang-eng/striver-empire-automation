# Striver Empire Product Automation

A full-stack Python 3.11+ and Next.js web application (with CLI support) that parses task messages (e.g. `women 25%`, `beauty and cosmetics 5%`, `men formal pants 12.5%`), discovers main categories and their ordered subcategories on `https://striverempire.com/` using Playwright and BeautifulSoup, extracts every product across all paginated/Load More subcategory listings and individual product detail pages, computes discounted prices with exact `Decimal` arithmetic, and exports matching green-header Excel (`.xlsx`) and single-page landscape PDF (`.pdf`) tables.

## Features

- **Apple Liquid Glass Web UI (`frontend/`)**: Next.js 16 + React + TypeScript + Tailwind CSS interface with a full-screen looping 4K background video, ChatGPT-style central task composer, searchable/tabbed Category Suggestions panel (click-to-insert and copy-to-clipboard), real-time 11-stage SSE/polling progress tracker, and direct Excel/PDF downloads.
- **FastAPI & Playwright Worker (`backend/`)**: Asynchronous task queue with rate limiting, duplicate active-job protection, PostgreSQL/SQLite job persistence, and S3/Vercel Blob/local file storage.
- **Category & Subcategory Classification**: Resolves parent categories (`Men's`, `Women's`, `Beauty and Cosmetics`, `Accessories`, `Winter`, `Home & Living`) into ordered website subcategories so the `Type` column always reflects each product's real subcategory.
- **Clean Spreadsheet Outputs**:
  - Exact 7 columns: `Sr. no. | Product Name | Total Price | Less Price | Real Price | Size | Type`
  - Bright green (`#18B500`) bold black Arial header, clean grid/outer borders, no titles/summaries/footers/page numbers/timestamps inside documents.
  - Comma-free 2-decimal-place numeric prices with no currency symbols (`999.00`, `1699.00`, `749.25`).
  - Strictly 1-page landscape PDF fitting all extracted products without omitting rows.
  - Readable `<Category> <Discount>%` filenames (e.g. `Women's 25%.xlsx`, `Beauty and Cosmetics 5%.pdf`, `Men's Shirt 10%.pdf`) with configurable duplicate-file protection (`prompt`, `number`, `replace`).

## Project Structure

```text
Striver-Empire-automation/
├── main.py                        # CLI & interactive bot entry point
├── Dockerfile                     # Container image for Python Playwright worker
├── pytest.ini                     # Pytest configuration
├── requirements.txt
├── .env.example
├── README.md
├── DEPLOYMENT.md                  # Vercel + Docker worker deployment guide
├── config/
│   └── settings.json              # Site URLs, categories, duplicate policy & PDF styling
├── core/
│   ├── config_loader.py           # JSON + optional env var config loader
│   ├── exceptions.py              # Custom exception hierarchy
│   ├── logger.py                  # Console + rotating file logging setup
│   └── models.py                  # Typed dataclasses for tasks, targets, records, summaries
├── processor/
│   ├── message_parser.py          # '<Category> <Discount>%' parser & filename builder
│   └── price_calculator.py        # Currency parser and Decimal discount calculation
├── scraper/
│   ├── category_scraper.py        # Parent/subcategory discovery, Load More / pagination, dedup
│   └── product_details.py         # Product detail HTML extraction, retries, failure tracking
├── generator/
│   ├── excel_generator.py         # OpenPyXL green-header 7-column table
│   └── pdf_generator.py           # ReportLab single-page landscape green-header table
├── backend/
│   ├── api.py                     # FastAPI REST + SSE + download endpoints
│   ├── worker.py                  # Async ThreadPoolExecutor Playwright job runner
│   ├── job_store.py               # PostgreSQL / SQLite job persistence
│   └── storage.py                 # Local / S3 / Vercel Blob file storage adapter
├── frontend/
│   ├── public/video/              # Background 4K video + poster frame
│   ├── src/app/                   # Next.js App Router page & /api proxy routes
│   ├── src/components/            # Liquid Glass UI components
│   ├── src/lib/                   # Validation, types, proxy helpers
│   └── vercel.json                # Vercel function & framework config
├── tests/                         # Unit tests (pytest)
├── logs/                          # Rotating execution logs
└── output/
    ├── Excel/                     # Generated .xlsx files
    └── PDF/                       # Generated .pdf files
```

## macOS Setup Instructions

### 1. Python Backend & Playwright
```bash
cd /Users/umang/Music/Striver-Empire-automation
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
playwright install chromium
```

### 2. Next.js Frontend
```bash
cd /Users/umang/Music/Striver-Empire-automation/frontend
npm install
```

## Running the Web Application Locally

Terminal 1 — Start the Python FastAPI & Playwright worker (`http://127.0.0.1:8000`):
```bash
cd /Users/umang/Music/Striver-Empire-automation
.venv/bin/uvicorn backend.api:app --host 127.0.0.1 --port 8000 --reload
```

Terminal 2 — Start the Next.js frontend (`http://localhost:3000`):
```bash
cd /Users/umang/Music/Striver-Empire-automation/frontend
npm run dev
```

Open `http://localhost:3000` in your browser. For production deployment on Vercel + Docker worker, see [DEPLOYMENT.md](DEPLOYMENT.md).

## CLI Usage

```bash
# Parent categories (Type = actual discovered subcategory)
.venv/bin/python main.py --task "women 25%"
.venv/bin/python main.py --task "beauty and cosmetics 5%"
.venv/bin/python main.py --task "men 10%"

# Subcategory-specific tasks
.venv/bin/python main.py --task "women formal pant 5%"
.venv/bin/python main.py --task "men formal pants 12.5%"

# Duplicate handling options: prompt (default), number, replace
.venv/bin/python main.py --task "beauty and cosmetics 5%" --on-duplicate number

# Dry-run mode (resolves subcategories & counts unique products without writing files)
.venv/bin/python main.py --task "women 25%" --dry-run

# Interactive bot prompt mode
.venv/bin/python main.py --interactive
```

## Running Tests

```bash
# Python unit & API tests
.venv/bin/pytest -v

# Frontend lint & production build
cd /Users/umang/Music/Striver-Empire-automation/frontend
npm run lint && npm run build
```

## Output Specification

- **Filenames**: `output/Excel/<Category> <Discount>%.xlsx` and `output/PDF/<Category> <Discount>%.pdf` (e.g. `Women's 25%.xlsx`, `Beauty and Cosmetics 5%.pdf`, `Women's Formal Pant 5%.pdf`). Existing reports are never silently overwritten (`prompt` on interactive TTY, numbered `(2)` when non-interactive, or `replace` when configured).
- **Columns (exact order)**: `Sr. no. | Product Name | Total Price | Less Price | Real Price | Size | Type`
- **Values**: Prices formatted as comma-free 2-decimal numbers (`999.00`, `1699.00`, `749.25`) with no currency symbols; discounts kept as percentages (`5%`, `25%`); missing sizes recorded as `NA`.
