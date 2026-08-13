# Web Crawler Agent

A Streamlit web-crawling and QA-analysis application built around Playwright.
It crawls same-domain pages, optionally authenticates, extracts structured DOM
information, summarizes page content with optional Ollama, generates QA test
plans, and exports Markdown, HTML, DOCX, JSON, and CSV results.

The production application intentionally **does not use vision/screenshot
analysis**. The useful ideas from the older POCs were refactored into the main
Playwright pipeline instead of adding multiple crawler frameworks.

## 🚀 Deployment

**Status:** Deployed

The application is deployed as a public portfolio demonstration.

**Architecture:** GitHub Actions → Docker → Cloud deployment

> Live demo access is provided selectively for evaluation/interviews.

## What the main app now does

```text
URL
 ↓
Playwright browser
 ↓
Authentication / popup handling
 ↓
Same-domain crawl
 ↓
Structured DOM analysis
 ├── page title + meta description
 ├── heading hierarchy
 ├── sections
 ├── forms + fields
 ├── links
 └── interactive controls
 ↓
Interaction candidates (analysis only)
 ↓
Evidence-based QA risk assessment
 ↓
Prioritized QA test generation
 ↓
Browser health signals (console + failed requests)
 ↓
Regression baseline comparison
 ↓
Optional Ollama page summary
 ↓
Reports / exports
```

### Important safety behavior

The crawler **discovers and plans interactions but does not automatically click
arbitrary buttons or submit forms**. This keeps a documentation crawl from
creating records, deleting data, sending messages, or triggering other
business actions. Generated interaction candidates can later be used by a
separate explicitly authorized test-execution workflow.

## Project layout

```text
crawler.py          # production Playwright crawler + structured analysis
app.py              # Streamlit UI
POC/                # historical prototypes kept for reference
 tests/             # automated tests
Dockerfile
docker-compose.yml
requirements.txt
requirements-dev.txt
```

## Key features brought forward from the POCs

- Structured page analysis instead of plain text-only scraping
- Form and form-field discovery
- Heading and section extraction
- Rich interactive-element metadata
- Interaction candidates for click/fill/navigate/submit workflows
- Evidence-grounded QA test-case generation with objectives, steps, expected results, and evidence
- Page-level QA risk scoring based only on observed signals
- Browser console-error and failed-network-request detection
- Lightweight regression baselines for detecting added, removed, or structurally changed pages
- DOCX reporting
- Existing Markdown, HTML, JSON, and CSV exports
- Optional local Ollama summaries
- Playwright-only browser automation in the production path

## Run locally

```bash
pip install -r requirements-dev.txt
playwright install --with-deps chromium

cp .env.example .env
streamlit run app.py
```

Open `http://localhost:8501`, enter a start URL, and click **Start crawl**.

Ollama is optional. If configured, the sidebar can generate richer page
summaries. Without Ollama, the crawler still performs all structural analysis
and QA test generation.

## Run tests

```bash
pytest
```

The tests mock Playwright pages and Ollama HTTP calls, so browser/network
access is not required for the unit suite.

## Docker

Without Ollama:

```bash
docker compose up --build
```

With the bundled Ollama profile:

```bash
docker compose --profile ollama up --build
docker compose exec ollama ollama pull qwen3:0.6b
```

Generated reports and debug output are written to the configured output
folder, which is bind-mounted by Docker Compose.

## Portfolio positioning

This project is designed as an **AI-powered web application QA intelligence
platform**, not just a crawler. The core portfolio story is:

```text
Discover → Analyze → Assess risk → Generate QA plan → Compare regressions → Report
```

The generated QA scenarios are grounded in observed DOM structure and browser
health signals. The passive crawl remains safe by default: it does not submit
forms or execute arbitrary business actions.

## Future direction

A separate, explicitly authorized interaction runner can consume the generated
QA scenarios and execute selected tests with Playwright, collecting PASS/FAIL
results and evidence. Keeping that runner separate preserves the safety and
determinism of the crawl pipeline.

## Portfolio engineering highlights

- Playwright-based dynamic-site crawling with same-domain boundaries.
- Evidence-grounded QA plan and prioritized test generation.
- Deterministic risk scoring from observed application signals.
- Lightweight accessibility checks and XHR/fetch/JSON request inventory.
- Safe QA execution for non-destructive checks with screenshots and execution evidence.
- Baseline regression comparison for structural and QA-risk changes.
- Environment-driven configuration; no application credentials are embedded in source.
- GitHub Actions CI for linting, compilation, browser setup, and tests.

### Safety model

The crawler does not submit forms or activate arbitrary buttons during a normal crawl. The QA execution engine only runs explicitly classified non-destructive checks. Authentication credentials are supplied through the UI/environment and are not written into generated reports.

## CI scope

GitHub Actions validates the deployable Streamlit crawler (`app.py`, `crawler.py`) and the automated tests. The repository also contains historical crawler experiments under `POC/`; those are retained as reference material but are intentionally excluded from the production CI quality gate because they are not part of the Render runtime.
