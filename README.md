# WebQA / Web Crawler Agent

> **AI-powered web application QA intelligence built on Playwright: discover → analyze → assess risk → generate QA plans → execute explicitly authorized safe tests → compare regressions → report.**

The production application crawls same-domain web applications, optionally authenticates, extracts structured DOM information, generates evidence-backed QA tests, detects browser health signals, manages regression baselines, and exports reports.

## What changed in the portfolio-ready release

### Faster crawler

The crawler was optimized for multi-page workloads without changing its safety model:

- Parallel Playwright page workers with configurable concurrency
- Duplicate-navigation removal
- Reduced fixed settle delays
- Batched browser-side DOM extraction to reduce Python↔browser IPC
- Network blocking for unnecessary heavy media such as images/video/fonts during analysis
- Synchronous optional LLM summaries moved off the async event loop

Tune hosted concurrency with environment variables such as:

```env
CRAWLER_CONCURRENCY=4
CRAWLER_SETTLE_MS=100
```

### Regression workflow

Regression is a real baseline workflow rather than an automatic baseline overwrite:

```text
First crawl → establish baseline

Next crawl → compare current vs baseline
             ↓
        added / removed / changed pages
             ↓
          review changes
             ↓
       explicitly update baseline
```

### Safe QA execution

The crawler discovers and plans interactions without automatically submitting arbitrary forms or triggering destructive business actions. Generated safe tests can later be run through the explicitly authorized execution workflow.

The execution workspace now keeps the user on the **Execution** view while tests run and presents structured results with status, duration, evidence, and expandable diagnostics.

### UI / hosted behavior

- Premium QA workbench UI
- System-aware light/dark theme adaptation
- Hosted-safe Streamlit sidebar collapse/reopen behavior
- Clear crawl, results, regression, execution, report, and export states

## What the main app does

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
 ├── title + meta
 ├── headings / sections
 ├── forms + fields
 ├── links
 └── interactive controls
 ↓
Interaction candidates
 ↓
Evidence-based QA risk assessment
 ↓
Prioritized QA test generation
 ↓
Browser health signals
 ├── console errors
 └── failed requests
 ↓
Safe test execution (explicit)
 ↓
Regression baseline comparison
 ↓
Reports / exports
```

## Important safety behavior

The crawler **does not arbitrarily click buttons or submit forms during discovery**. The production pipeline is intentionally safe by default so a documentation/analysis crawl cannot create records, delete data, send messages, or trigger unrelated business actions.

## Key features

- Same-domain Playwright crawling
- Optional authentication
- Structured page analysis
- Form and control discovery
- QA risk scoring from observed signals
- Evidence-grounded test-case generation
- Safe explicit test execution
- Browser console / failed-request analysis
- Regression baselines
- Markdown / HTML / DOCX / JSON / CSV exports
- Optional local Ollama summaries
- Docker deployment

## Run locally

```bash
pip install -r requirements-dev.txt
playwright install --with-deps chromium
cp .env.example .env
streamlit run app.py
```

## Run tests

```bash
pytest
```

## Docker

```bash
docker compose up --build
```

The optional Ollama profile can be enabled using the repository's documented compose configuration.

## Portfolio positioning

**QA intelligence workbench** — fast browser analysis, evidence-backed test planning, safe execution, and regression visibility rather than a generic web scraper.

## Portfolio website + shared Gateway launch

Hosted WebQA demonstrations are launched from the AI Engineering Studio website. The website owns BYOK, provider selection, and credential custody; WebQA receives only a short-lived project-scoped session after exchanging a single-use handoff code.

Configure the hosted Streamlit deployment:

- `PORTFOLIO_SESSION_GATEWAY_URL`: shared Portfolio LLM Gateway root URL.
- `LLM_GATEWAY_URL`: OpenAI-compatible inference base URL for the Gateway (normally ends in `/v1`).
- `LLM_GATEWAY_MODEL`: approved Gateway model identifier (default `portfolio-free`).

Do not configure user provider keys or reusable shared provider credentials in the hosted WebQA service. `WEBQA_ALLOW_LOCAL_LLM=true` exists only for an explicitly local development setup; leave it false in the hosted portfolio deployment.

The one-time `portfolio_llm_handoff` code is removed from the URL before exchange. The returned bearer remains in Streamlit server-side session state until its Gateway expiry. The legacy reusable `portfolio_llm_session` URL parameter is rejected. Crawl discovery, safe execution policy, regression baselines, and report generation remain unchanged.

