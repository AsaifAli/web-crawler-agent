import asyncio
import csv
import io
import json
import os
import time
from urllib.parse import urlparse

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from crawler import WebCrawler

load_dotenv()

st.set_page_config(page_title="WebQA · Web Intelligence & QA", page_icon=":material/travel_explore:", layout="wide", initial_sidebar_state="expanded")

# Shared premium visual layer (presentation-only).
from ui_theme import apply_theme
from sidebar_toggle import render_sidebar_toggle
apply_theme()
render_sidebar_toggle()


st.html("""
<style>
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(14px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes popIn {
  0%   { opacity: 0; transform: scale(0.85); }
  70%  { opacity: 1; transform: scale(1.03); }
  100% { opacity: 1; transform: scale(1); }
}

/* Result & history cards animate in and lift slightly on hover */
div[class*="st-key-page_card_"],
div[class*="st-key-history_card_"] {
  animation: fadeInUp 0.35s ease-out both;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  border-radius: 8px;
}
div[class*="st-key-page_card_"]:hover,
div[class*="st-key-history_card_"]:hover {
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.12);
}

/* Metrics pop in with a staggered delay */
div[data-testid="stMetric"] { animation: popIn 0.45s ease-out both; }
div[data-testid="stMetric"]:nth-of-type(1) { animation-delay: 0.00s; }
div[data-testid="stMetric"]:nth-of-type(2) { animation-delay: 0.06s; }
div[data-testid="stMetric"]:nth-of-type(3) { animation-delay: 0.12s; }
div[data-testid="stMetric"]:nth-of-type(4) { animation-delay: 0.18s; }

/* Tabs and the empty-state illustration fade in */
div[data-testid="stTabs"] { animation: fadeIn 0.4s ease-out both; }
div[class*="st-key-empty_state_"] { animation: fadeIn 0.6s ease-out both; }

/* Primary button gets a little lift on hover */
div[data-testid="stFormSubmitButton"] button {
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
div[data-testid="stFormSubmitButton"] button:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 10px rgba(0,0,0,0.15);
}

/* Neutral "processing" indicator: three dots pulsing in sequence */
@keyframes dotPulse {
  0%, 80%, 100% { opacity: 0.25; transform: scale(0.8); }
  40%           { opacity: 1;    transform: scale(1); }
}
.processing-dots {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 28px;
  margin: 4px 0 10px 0;
}
.processing-dots .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
  animation: dotPulse 1.2s ease-in-out infinite;
}
.processing-dots .dot:nth-child(2) { animation-delay: 0.15s; }
.processing-dots .dot:nth-child(3) { animation-delay: 0.30s; }

/* Shimmering skeleton placeholders shown while a crawl is in progress */
@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position: 400px 0; }
}
.skeleton-card {
  border: 1px solid rgba(128,128,128,0.25);
  border-radius: 8px;
  padding: 14px;
  margin-bottom: 10px;
}
.skeleton-line {
  height: 12px;
  border-radius: 4px;
  margin-bottom: 8px;
  background: linear-gradient(
    90deg,
    rgba(128,128,128,0.15) 25%,
    rgba(128,128,128,0.3) 37%,
    rgba(128,128,128,0.15) 63%
  );
  background-size: 800px 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}
.skeleton-line.title { width: 45%; height: 14px; }
.skeleton-line.wide { width: 80%; }
.skeleton-line.medium { width: 60%; }
</style>
""")

st.html("""
<style>
.qa-suite-summary { display:flex; align-items:center; gap:8px; padding:10px 14px; border:1px solid rgba(100,120,150,.22); border-radius:12px; background:rgba(100,120,150,.06); }
.qa-suite-dot { width:8px; height:8px; border-radius:50%; background:#14b8a6; box-shadow:0 0 0 4px rgba(20,184,166,.12); }
.qa-section-label { margin:22px 0 10px; font-size:.72rem; letter-spacing:.18em; font-weight:800; opacity:.68; }
.qa-result-pill { display:inline-flex; align-items:center; justify-content:center; padding:5px 10px; border-radius:999px; font-size:.72rem; font-weight:800; letter-spacing:.05em; }
.qa-status-pass { color:#16a34a; background:rgba(22,163,74,.12); border:1px solid rgba(22,163,74,.24); }
.qa-status-fail { color:#d97706; background:rgba(217,119,6,.12); border:1px solid rgba(217,119,6,.24); }
.qa-status-error { color:#dc2626; background:rgba(220,38,38,.12); border:1px solid rgba(220,38,38,.24); }
.qa-status-neutral { color:#64748b; background:rgba(100,116,139,.12); border:1px solid rgba(100,116,139,.24); }
.qa-actual { margin:12px 0; padding:12px 14px; border-radius:10px; background:rgba(100,116,139,.06); border:1px solid rgba(100,116,139,.12); }
.regression-hero { display:flex; justify-content:space-between; align-items:center; gap:18px; padding:20px 22px; border:1px solid rgba(20,184,166,.25); border-radius:16px; background:linear-gradient(135deg, rgba(20,184,166,.08), rgba(59,130,246,.06)); margin:8px 0 18px; }
.regression-hero h3 { margin:.15rem 0 .3rem; }
.regression-hero p { margin:0; opacity:.74; }
.regression-state { white-space:nowrap; border:1px solid rgba(20,184,166,.28); color:#0f766e; background:rgba(20,184,166,.08); padding:7px 10px; border-radius:999px; font-size:.7rem; font-weight:800; letter-spacing:.08em; }
.regression-clean,.regression-warning { display:flex; gap:10px; align-items:center; padding:12px 14px; border-radius:12px; margin:14px 0; }
.regression-clean { border:1px solid rgba(22,163,74,.2); background:rgba(22,163,74,.08); }
.regression-warning { border:1px solid rgba(217,119,6,.22); background:rgba(217,119,6,.08); }
.regression-clean span,.regression-warning span { opacity:.72; }
@media (max-width: 800px) { .regression-hero { flex-direction:column; align-items:flex-start; } }

/* QA multiselect tokens follow the product palette instead of Streamlit error red */
div[data-baseweb="select"] span[data-baseweb="tag"] {
  background: rgba(20,184,166,.14) !important;
  border: 1px solid rgba(20,184,166,.28) !important;
  color: inherit !important;
}
</style>
""")

OUTPUT_DIR = os.getenv("CRAWLER_OUTPUT_DIR", "output")

STATUS_STYLE = {
    "success": (":material/check_circle:", "green"),
    "failed": (":material/error:", "red"),
}


def status_style(status: str):
    key = "success" if status.startswith("success") else "failed"
    return STATUS_STYLE[key]


def normalize_url(raw: str) -> str | None:
    """Adds a scheme if the user typed a bare domain (e.g. "www.google.com").
    Returns None if the result still isn't a navigable http(s) URL."""
    candidate = raw.strip()
    if not candidate or any(c.isspace() for c in candidate):
        return None
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    host = parsed.netloc.split(":")[0]
    if host != "localhost" and "." not in host:
        return None
    return candidate


def pages_to_csv(pages: list) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "url", "title", "section", "status", "summary", "word_count",
            "heading_count", "section_count", "form_count", "interactive_element_count",
            "test_case_count", "qa_risk_score", "qa_risk_level",
            "console_errors", "failed_requests", "accessibility_findings", "api_requests", "page_load_ms",
        ],
    )
    writer.writeheader()
    for page in pages:
        writer.writerow(
            {
                "url": page["url"],
                "title": page.get("title", ""),
                "section": page["section"],
                "status": page["status"],
                "summary": page["summary"],
                "word_count": page.get("word_count", 0),
                "heading_count": len(page.get("headings", [])),
                "section_count": len(page.get("sections", [])),
                "form_count": len(page.get("forms", [])),
                "interactive_element_count": len(page["interactive_elements"]),
                "test_case_count": len(page.get("generated_test_cases", [])),
                "qa_risk_score": page.get("qa_risk_score", 0),
                "qa_risk_level": page.get("qa_risk_level", "Low"),
                "console_errors": len(page.get("console_errors", [])),
                "failed_requests": len(page.get("failed_requests", [])),
                "accessibility_findings": len(page.get("accessibility_findings", [])),
                "api_requests": len(page.get("api_requests", [])),
                "page_load_ms": page.get("page_load_ms", 0),
            }
        )
    return buffer.getvalue()


def skeleton_cards_html(count: int = 3) -> str:
    card = (
        '<div class="skeleton-card">'
        '<div class="skeleton-line title"></div>'
        '<div class="skeleton-line wide"></div>'
        '<div class="skeleton-line medium"></div>'
        "</div>"
    )
    return card * count


def animate_count(placeholder, label: str, icon: str, target: int, duration: float = 0.35, steps: int = 10):
    """Counts a metric up from 0 to `target` in place, then settles on the exact value."""
    for step in range(steps + 1):
        placeholder.metric(f"{icon} {label}", int(target * step / steps))
        time.sleep(duration / steps)
    placeholder.metric(f"{icon} {label}", target)


if "result" not in st.session_state:
    st.session_state.result = None
if "error" not in st.session_state:
    st.session_state.error = None
if "history" not in st.session_state:
    st.session_state.history = []
if "execution_results" not in st.session_state:
    st.session_state.execution_results = []

# Portfolio handoff: the portfolio passes a short-lived gateway JWT when this
# app is launched from a portfolio project page. Capture it once into the
# Streamlit session and remove it from the visible URL.
portfolio_token = str(st.query_params.get("portfolio_llm_session", "")).strip()
if portfolio_token:
    st.session_state.llm_gateway_session_token = portfolio_token
    try:
        del st.query_params["portfolio_llm_session"]
    except Exception:
        pass

# --- Product hero -------------------------------------------------------

summary_count = len(st.session_state.get("history", []))
st.html(f"""
<div class="webqa-hero">
  <div class="webqa-hero-main">
    <div class="premium-kicker">WEBQA · WEB INTELLIGENCE & QA</div>
    <h1>Turn a web app into an evidence-backed QA plan.</h1>
    <p>Crawl dynamic sites with Playwright, understand structure and health, surface risk, and generate safe test scenarios — without turning the crawler into a black box.</p>
    <div class="chip-row">
      <span class="premium-chip">● Playwright crawling</span>
      <span class="premium-chip">● Structural analysis</span>
      <span class="premium-chip">● Risk detection</span>
      <span class="premium-chip">● Evidence-based QA</span>
    </div>
  </div>
  <div class="webqa-hero-flow">
    <div class="premium-kicker">HOW WEBQA WORKS</div>
    <div class="flow-step"><b>01</b><div><strong>Crawl</strong><span>Discover pages, forms, links and network signals.</span></div></div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step"><b>02</b><div><strong>Understand</strong><span>Normalize structure, accessibility, errors and risk.</span></div></div>
    <div class="flow-arrow">↓</div>
    <div class="flow-step"><b>03</b><div><strong>Generate</strong><span>Create prioritized QA scenarios with evidence.</span></div></div>
  </div>
</div>
<div class="webqa-ready-strip">
  <div><span class="status-dot"></span><strong>Workspace ready</strong><span class="webqa-muted"> · Safe-by-default crawling</span></div>
  <div class="webqa-ready-metrics">
    <span><small>SESSION RUNS</small><b>{summary_count}</b></span>
    <span><small>ENGINE</small><b>Playwright</b></span>
    <span><small>QA MODE</small><b>Evidence-backed</b></span>
  </div>
</div>
""")

# --- Sidebar: connection + run history -----------------------------------

with st.sidebar:
    st.markdown('<div class="sidebar-brand"><div class="sidebar-brand-mark">◉</div><div><strong>WebQA</strong><span>WEB INTELLIGENCE</span></div></div>', unsafe_allow_html=True)
    st.markdown('<div class="premium-kicker">RESEARCH & QA WORKSPACE</div>', unsafe_allow_html=True)
    st.caption("Crawl → understand → test. Safe by default.")
    st.subheader(":material/smart_toy: AI summaries", anchor=False)

    # Local development can keep using the LiteLLM gateway. Cloud deployments
    # can bypass it and call any OpenAI-compatible endpoint directly (for
    # example OpenRouter) by setting OPENAI_BASE_URL / OPENAI_API_KEY.
    gateway_url = os.getenv("LLM_GATEWAY_URL", "")
    gateway_key = st.session_state.get("llm_gateway_session_token", "") or os.getenv("LLM_GATEWAY_API_KEY", "")
    direct_url = os.getenv("OPENAI_BASE_URL", "")
    direct_key = os.getenv("OPENAI_API_KEY", "")
    gateway_enabled = (
        os.getenv("LLM_GATEWAY_ENABLED", "").lower() == "true"
        or bool(gateway_key)
        or bool(direct_key)
    )

    use_ai = st.toggle(
        "Generate AI summary",
        value=gateway_enabled,
        help="Uses the configured OpenAI-compatible LLM endpoint. Local development can use LiteLLM; cloud deployments can use OpenRouter directly.",
    )

    if use_ai and (gateway_key or direct_key):
        llm_base_url = gateway_url or direct_url or "https://openrouter.ai/api/v1"
        llm_api_key = gateway_key or direct_key
        llm_model = (
            ("" if st.session_state.get("llm_gateway_session_token") else os.getenv("LLM_GATEWAY_MODEL", ""))
            or os.getenv("LLM_MODEL", "")
            or os.getenv("OPENAI_MODEL", "")
            or os.getenv("OPENAI_MODEL_ID", "")
            or "openrouter/free"
        )
        ollama_url = os.getenv("OLLAMA_URL", "")
        ollama_model = os.getenv("OLLAMA_MODEL", "")
    else:
        llm_base_url, llm_api_key, llm_model = "", "", "openrouter/free"
        ollama_url = (
            os.getenv("OLLAMA_URL", "")
            if os.getenv("USE_OLLAMA_FALLBACK", "false").lower() == "true"
            else ""
        )
        ollama_model = os.getenv("OLLAMA_MODEL", "")
        st.caption("AI summaries are optional. Without an LLM key, the crawler uses a short text excerpt.")

    st.divider()
    st.subheader(":material/history: Run history", anchor=False)
    if not st.session_state.history:
        st.caption("Past crawls in this session will show up here.")
    else:
        for i, run in enumerate(reversed(st.session_state.history)):
            with st.container(border=True, key=f"history_card_{i}"):
                st.markdown(f":material/language: **{run['app_id']}**")
                st.caption(run["base_url"])
                b1, b2 = st.columns(2)
                b1.metric("Pages", run["pages_visited_count"], label_visibility="collapsed")
                b2.caption(run["crawl_duration"].split(".")[0])
                if st.button("View", key=f"history_{i}", icon=":material/visibility:", width="stretch"):
                    st.session_state.result = run["_full_result"]
                    st.rerun()

# --- Crawl workspace ------------------------------------------------------

st.html("""<div class="workspace-kicker">CRAWL WORKSPACE</div><div class="workspace-title">Target a web application</div><div class="workspace-subtitle">Configure the crawl, keep it bounded, and let WebQA turn the result into an actionable QA plan.</div>""")

with st.form("crawl_form", border=True):
    st.markdown('<div class="form-section-label">01 · Target</div>', unsafe_allow_html=True)
    url = st.text_input("Start URL", placeholder="https://example.com")

    col1, col2 = st.columns(2)
    with col1:
        app_id = st.text_input("Run label", value="crawl", icon=":material/label:")
        username = st.text_input("Username (optional)", icon=":material/person:")
    with col2:
        max_pages = st.slider("Max pages", min_value=1, max_value=100, value=10)
        password = st.text_input("Password (optional)", type="password", icon=":material/lock:")

    sections_raw = st.text_input("Extra section paths (comma-separated, optional)", placeholder="/about, /contact")
    st.markdown('<div class="form-footer">Same-domain crawl · non-destructive by default · evidence retained in-session</div>', unsafe_allow_html=True)
    submitted = st.form_submit_button("Start crawl", icon=":material/rocket_launch:", type="primary", width="stretch")

# --- Run crawl --------------------------------------------------------------

if submitted:
    normalized_url = normalize_url(url) if url else None
    if not url or not url.strip():
        st.session_state.error = "Enter a start URL."
        st.session_state.result = None
    elif normalized_url is None:
        st.session_state.error = f"'{url.strip()}' doesn't look like a valid URL. Try something like https://example.com."
        st.session_state.result = None
    else:
        sections = [s.strip() for s in sections_raw.split(",") if s.strip()]
        crawler = WebCrawler(
            url=normalized_url,
            section="Home",
            sections=sections,
            app_id=app_id.strip() or "crawl",
            username=username.strip(),
            password=password,
            ollama_url=ollama_url.strip(),
            ollama_model=ollama_model.strip(),
            llm_base_url=llm_base_url.strip(),
            llm_api_key=llm_api_key.strip(),
            llm_model=llm_model.strip(),
            output_dir=OUTPUT_DIR,
        )

        st.toast("Crawl started", icon=":material/rocket_launch:")
        status_area = st.status("Launching browser...", expanded=True)
        dots_slot = status_area.empty()
        dots_slot.html('<div class="processing-dots"><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>')
        progress_bar = status_area.progress(0.0)
        log_lines = []
        log_slot = status_area.empty()

        skeleton_slot = st.empty()
        skeleton_slot.html(skeleton_cards_html(3))

        def on_progress(visited, total, current_url):
            progress_bar.progress(min(visited / total, 1.0))
            log_lines.append(f"`{visited}/{total}` visited **{current_url}**")
            log_slot.markdown("  \n".join(log_lines[-6:]))
            status_area.update(label=f"Crawling... {visited}/{total} pages visited")

        start = time.time()
        try:
            result = asyncio.run(
                crawler.crawl_and_process(max_pages=int(max_pages), headless=True, progress_cb=on_progress)
            )
            result["app_id"] = app_id.strip() or "crawl"
            st.session_state.result = result
            st.session_state.error = None
            st.session_state.execution_results = []
            summary = result["crawl_summary"]
            st.session_state.history.append({**summary, "app_id": app_id.strip() or "crawl", "_full_result": result})
            dots_slot.empty()
            skeleton_slot.empty()
            status_area.update(
                label=f"Done in {time.time() - start:.1f}s — {summary['pages_visited_count']} pages visited",
                state="complete",
            )

            count_cols = status_area.columns(3)
            count_slots = [c.empty() for c in count_cols]
            animate_count(count_slots[0], "Pages visited", ":material/description:", summary["pages_visited_count"])
            animate_count(count_slots[1], "Links found", ":material/link:", summary["link_count"])
            animate_count(count_slots[2], "Successful", ":material/task_alt:", summary["successful_scrapes"])

            st.toast("Report ready", icon=":material/task_alt:")
        except Exception as e:
            dots_slot.empty()
            skeleton_slot.empty()
            status_area.update(label="Crawl failed", state="error")
            st.session_state.error = str(e)
            st.session_state.result = None

if st.session_state.error:
    st.error(st.session_state.error, icon=":material/error:")

# --- Results ----------------------------------------------------------------

result = st.session_state.result
if result:
    summary = result["crawl_summary"]
    rag = result["rag_document"]

    st.divider()
    risk_level = "High attention" if summary.get("high_risk_pages", 0) else ("Review" if summary.get("medium_risk_pages", 0) else "Healthy")
    st.html(f"""<div class="result-banner"><div><div class="premium-kicker">CRAWL COMPLETE</div><div class="result-title">{summary['base_url']}</div><div class="result-subtitle">{summary['pages_visited_count']} pages analyzed · {summary.get('test_case_count', 0)} QA scenarios · {risk_level}</div></div><div class="result-badges"><span class="result-badge"><b>{summary['pages_visited_count']}</b><small>PAGES</small></span><span class="result-badge"><b>{summary.get('high_risk_pages', 0)}</b><small>HIGH RISK</small></span><span class="result-badge"><b>{summary.get('accessibility_finding_count', 0)}</b><small>A11Y</small></span></div></div>""")

    banner_col, chart_col = st.columns([2, 1])
    with banner_col:
        st.markdown(f":material/language: **{summary['base_url']}**")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric(":material/description: Pages visited", summary["pages_visited_count"])
        m2.metric(":material/link: Links found", summary["link_count"])
        m3.metric(":material/dynamic_form: Forms", summary.get("form_count", 0))
        m4.metric(":material/bug_report: Test cases", summary.get("test_case_count", 0))
        r1, r2, r3 = st.columns(3)
        r1.metric("High-risk pages", summary.get("high_risk_pages", 0))
        r2.metric("Console errors", summary.get("console_error_count", 0))
        r3.metric("Failed requests", summary.get("failed_request_count", 0))
        a1, a2 = st.columns(2)
        a1.metric("Accessibility findings", summary.get("accessibility_finding_count", 0))
        a2.metric("API/XHR responses", summary.get("api_request_count", 0))
    with chart_col:
        failed_count = summary["pages_visited_count"] - summary["successful_scrapes"]
        chart_data = pd.DataFrame(
            {"Pages": [summary["successful_scrapes"], failed_count]}, index=["Successful", "Failed"]
        )
        st.bar_chart(chart_data, width="stretch", height=160, color=["#22C55E"])

    tab_pages, tab_qa, tab_execution, tab_regression, tab_report, tab_export = st.tabs(
        [":material/web: Pages", ":material/bug_report: QA plan", ":material/play_circle: Execution", ":material/compare_arrows: Regression", ":material/article: Report", ":material/download: Export"]
    )

    with tab_pages:
        filter_col, search_col = st.columns([1, 2])
        with filter_col:
            show_failed_only = st.toggle("Show failed only", value=False)
        with search_col:
            search_query = st.text_input(
                "Search pages",
                placeholder="Filter by URL or section...",
                icon=":material/search:",
                label_visibility="collapsed",
            )

        pages = result["pages"]
        if show_failed_only:
            pages = [p for p in pages if not p["status"].startswith("success")]
        if search_query.strip():
            q = search_query.strip().lower()
            pages = [p for p in pages if q in p["url"].lower() or q in (p["section"] or "").lower()]

        if not pages:
            st.info("No pages match this filter.", icon=":material/info:")

        for i, page in enumerate(pages):
            icon, color = status_style(page["status"])
            with st.container(border=True, key=f"page_card_{i}"):
                title_col, badge_col = st.columns([4, 1], vertical_alignment="center")
                with title_col:
                    st.markdown(f"**{page['section'] or 'Homepage'}**")
                    st.caption(page["url"])
                with badge_col:
                    st.markdown(f":{color}[{icon} {page['status'].split(':')[0]}]")
                risk_level = page.get("qa_risk_level", "Low")
                risk_score = page.get("qa_risk_score", 0)
                risk_icon = {"High": ":material/error:", "Medium": ":material/warning:", "Low": ":material/check_circle:"}.get(risk_level, ":material/help:")
                st.markdown(f"{risk_icon} **QA risk: {risk_level} ({risk_score}/100)**")
                if page.get("summary"):
                    st.write(page["summary"])
                st.caption(
                    f"{page.get('word_count', 0)} words · "
                    f"{len(page.get('headings', []))} headings · "
                    f"{len(page.get('forms', []))} forms · "
                    f"{len(page.get('interactive_elements', []))} interactive elements"
                )
                with st.expander(f"Page structure ({len(page.get('sections', []))} sections)"):
                    if page.get("headings"):
                        st.markdown("**Headings**")
                        st.dataframe(page["headings"], width="stretch", hide_index=True)
                    if page.get("sections"):
                        st.markdown("**Sections**")
                        st.dataframe(page["sections"], width="stretch", hide_index=True)
                with st.expander(f"Forms ({len(page.get('forms', []))})"):
                    if page.get("forms"):
                        st.json(page["forms"])
                    else:
                        st.caption("No forms found.")
                with st.expander(f"Interactive elements ({len(page['interactive_elements'])})"):
                    if page["interactive_elements"]:
                        st.dataframe(page["interactive_elements"], width="stretch", hide_index=True)
                    else:
                        st.caption("None found.")
                with st.expander(f"Interaction candidates ({len(page.get('interaction_candidates', []))})"):
                    if page.get("interaction_candidates"):
                        st.dataframe(page["interaction_candidates"], width="stretch", hide_index=True)
                        st.caption("Actions are analyzed only; form submission/click execution is not performed during a crawl.")
                    else:
                        st.caption("No interaction candidates found.")
                with st.expander(f"Accessibility findings ({len(page.get('accessibility_findings', []))})"):
                    if page.get("accessibility_findings"):
                        st.dataframe(page["accessibility_findings"], width="stretch", hide_index=True)
                    else:
                        st.success("No lightweight accessibility findings detected.", icon=":material/check_circle:")
                with st.expander(f"API / network inventory ({len(page.get('api_requests', []))})"):
                    if page.get("api_requests"):
                        st.dataframe(page["api_requests"], width="stretch", hide_index=True)
                    else:
                        st.caption("No XHR/fetch/JSON responses captured on this page.")

    with tab_qa:
        test_cases = result.get("test_cases", [])
        pages = result.get("pages", [])
        st.subheader(":material/bug_report: Evidence-based QA plan", anchor=False)
        st.caption(
            "Prioritized scenarios are grounded in the forms, controls, navigation, structure, and browser health signals actually discovered during the crawl. "
            "The crawler does not submit forms or trigger destructive actions."
        )
        qa_cols = st.columns(4)
        qa_cols[0].metric("Test cases", len(test_cases))
        qa_cols[1].metric("High priority", sum(c.get("priority") == "High" for c in test_cases))
        qa_cols[2].metric("Medium priority", sum(c.get("priority") == "Medium" for c in test_cases))
        qa_cols[3].metric("QA coverage", f"{sum(bool(p.get('generated_test_cases')) for p in pages)}/{len(pages) or 0}")
        if test_cases:
            st.dataframe(
                test_cases, width="stretch", hide_index=True,
                column_config={
                    "objective": st.column_config.TextColumn("Objective", width="large"),
                    "url": st.column_config.LinkColumn("URL"),
                    "steps": st.column_config.ListColumn("Steps"),
                    "evidence": st.column_config.ListColumn("Evidence"),
                },
            )
            st.markdown("### Test details")
            for case in test_cases:
                with st.expander(f"{case['id']} · {case['title']} · {case['priority']}"):
                    st.markdown(f"**Objective:** {case['objective']}")
                    st.markdown("**Preconditions**")
                    for item in case.get("preconditions", []): st.markdown(f"- {item}")
                    st.markdown("**Steps**")
                    for idx, step in enumerate(case.get("steps", []), 1): st.markdown(f"{idx}. {step}")
                    st.markdown(f"**Expected result:** {case.get('expected_result', '')}")
                    st.markdown("**Evidence**")
                    for item in case.get("evidence", []): st.markdown(f"- {item}")
        else:
            st.info("No test cases were generated from the crawled pages.", icon=":material/info:")

        st.markdown("### Risk distribution")
        risk_df = pd.DataFrame({"Pages": [summary.get("high_risk_pages", 0), summary.get("medium_risk_pages", 0), summary.get("low_risk_pages", 0)]}, index=["High", "Medium", "Low"])
        st.bar_chart(risk_df, width="stretch")

    with tab_execution:
        test_cases = result.get("test_cases", [])
        st.subheader(":material/play_circle: Safe QA execution", anchor=False)
        st.caption("Run only non-destructive browser checks discovered by WebQA. Forms are not submitted and arbitrary buttons are never activated.")
        safe_titles = {
            "Verify form renders correctly", "Verify input controls", "Verify navigation links",
            "Verify page structure", "Review missing heading structure", "Review accessibility findings",
        }
        safe_cases = [c for c in test_cases if c.get("title") in safe_titles]
        results = st.session_state.execution_results or []
        passed = sum(r.get("status") == "PASSED" for r in results)
        failed = sum(r.get("status") == "FAILED" for r in results)
        errors = sum(r.get("status") == "ERROR" for r in results)

        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("Available", len(safe_cases))
        ec2.metric("Executed", len(results))
        ec3.metric("Passed", passed)
        ec4.metric("Needs review", failed + errors)

        if safe_cases:
            labels = [f"{idx} · {case['title']} · {case.get('url', summary['base_url'])}" for idx, case in enumerate(safe_cases)]
            default_labels = labels[:10]
            selected_labels = st.multiselect(
                "Safe test suite",
                labels,
                default=default_labels,
                placeholder="Choose non-destructive checks…",
                help="Only checks marked safe by WebQA are executable. Selecting a row identifies the exact test case even when IDs repeat across pages.",
            )
            selected_indexes = {int(label.split(" · ", 1)[0]) for label in selected_labels}
            chosen = [case for idx, case in enumerate(safe_cases) if idx in selected_indexes]

            action_col, info_col = st.columns([1, 2])
            with action_col:
                run_clicked = st.button("Run selected safe tests", icon=":material/play_arrow:", type="primary", width="stretch", disabled=not chosen)
            with info_col:
                st.markdown(
                    f'<div class="qa-suite-summary"><span class="qa-suite-dot"></span><strong>{len(chosen)} checks selected</strong><span>·</span><span>non-destructive only</span><span>·</span><span>Playwright</span></div>',
                    unsafe_allow_html=True,
                )

            if run_clicked:
                # Stay on the Execution tab after the action and render the live results
                # in the same Streamlit run. A rerun here can reset st.tabs() to the
                # first tab, which makes it look like the execution view disappeared.
                st.html(
                    """<div id=\"qa-execution-live\" style=\"display:flex;align-items:center;gap:.6rem;padding:.72rem .9rem;margin:.7rem 0 1rem;border:1px solid rgba(34,197,94,.28);background:rgba(34,197,94,.08);border-radius:12px;\">"
                    <span style=\"width:9px;height:9px;border-radius:999px;background:#22c55e;box-shadow:0 0 0 5px rgba(34,197,94,.12);animation:dotPulse 1.1s ease-in-out infinite;\"></span>"
                    <strong>Tests running</strong>"
                    <span style=\"opacity:.72;\">Safe, non-destructive browser checks are executing now.</span>"
                    </div>"""
                )
                crawler = WebCrawler(url=summary["base_url"], app_id="qa_execution", output_dir=OUTPUT_DIR)
                status = st.status("Running safe QA checks…", expanded=True)
                status.write(f"Executing {len(chosen)} selected checks with Playwright")
                with status:
                    st.session_state.execution_results = asyncio.run(
                        crawler.execute_safe_qa_tests(chosen, headless=True, max_tests=len(chosen))
                    )
                status.update(label="Safe QA execution complete", state="complete")
                st.toast("Safe QA execution complete", icon=":material/task_alt:")
                results = st.session_state.execution_results or []
        else:
            st.info("No non-destructive automated checks are available for this crawl.", icon=":material/info:")

        if results:
            st.markdown('<div class="qa-section-label">EXECUTION RESULTS</div>', unsafe_allow_html=True)
            for idx, execution in enumerate(results):
                status_value = execution.get("status", "UNKNOWN")
                status_class = {
                    "PASSED": "qa-status-pass",
                    "FAILED": "qa-status-fail",
                    "ERROR": "qa-status-error",
                }.get(status_value, "qa-status-neutral")
                icon = {
                    "PASSED": ":material/check_circle:",
                    "FAILED": ":material/warning:",
                    "ERROR": ":material/error:",
                }.get(status_value, ":material/help:")
                duration = execution.get("duration_ms", 0)
                with st.container(border=True):
                    top_left, top_mid, top_right = st.columns([4, 1, 1], vertical_alignment="center")
                    with top_left:
                        st.markdown(f"**{execution.get('id', 'TEST')} · {execution.get('title', 'Safe QA check')}**")
                        st.caption(execution.get("url", summary["base_url"]))
                    with top_mid:
                        st.markdown(f'<span class="qa-result-pill {status_class}">{status_value}</span>', unsafe_allow_html=True)
                    with top_right:
                        st.caption(f"{duration} ms")
                    st.markdown(f"<div class=\"qa-actual\"><strong>Observed:</strong> {execution.get('actual_result', 'No result returned.')}</div>", unsafe_allow_html=True)
                    meta_cols = st.columns(3)
                    meta_cols[0].caption(f"Console errors · {sum('Console errors:' in x and not x.endswith(': 0') for x in execution.get('evidence', []))}")
                    meta_cols[1].caption(f"Evidence items · {len(execution.get('evidence', []))}")
                    meta_cols[2].caption("Safe · no destructive actions")
                    with st.expander("Evidence & screenshot"):
                        if execution.get("evidence"):
                            for item in execution["evidence"]:
                                st.markdown(f"- {item}")
                        screenshot = execution.get("screenshot_path", "")
                        if screenshot and os.path.exists(screenshot):
                            st.image(screenshot, caption="Execution evidence", width="stretch")

            st.download_button(
                "Download execution results",
                data=json.dumps(results, indent=2),
                file_name="webqa_safe_execution_results.json",
                mime="application/json",
                icon=":material/download:",
            )

    with tab_regression:
        regression = result.get("regression", {})
        st.subheader(":material/compare_arrows: Crawl regression", anchor=False)
        st.caption("Compare the current crawl against a retained structural baseline. The baseline contains page shape, forms, links, interactions, status and QA signals — never page content.")

        if regression.get("baseline_created"):
            st.markdown(
                '<div class="regression-hero"><div><div class="premium-kicker">BASELINE ESTABLISHED</div><h3>This crawl is now your reference point.</h3><p>Run the same crawl again later to detect structural drift, new pages, removed pages, or changed QA signals.</p></div><span class="regression-state">READY FOR COMPARISON</span></div>',
                unsafe_allow_html=True,
            )
        elif not regression.get("available"):
            st.info(regression.get("message", "No baseline is available yet."), icon=":material/schedule:")
        else:
            added = regression.get("added", [])
            removed = regression.get("removed", [])
            changed = regression.get("changed", [])
            changed_count = len(added) + len(removed) + len(changed)
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Added", len(added))
            rc2.metric("Removed", len(removed))
            rc3.metric("Changed", len(changed))
            rc4.metric("Regression score", "Clean" if changed_count == 0 else f"{changed_count} change{'s' if changed_count != 1 else ''}")

            if changed_count == 0:
                st.markdown('<div class="regression-clean"><strong>✓ No structural regression detected.</strong><span>The current crawl matches the stored baseline across tracked signals.</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="regression-warning"><strong>Changes detected.</strong><span>Review the affected pages below before updating the baseline.</span></div>', unsafe_allow_html=True)

            if added:
                with st.expander(f"Added pages · {len(added)}", expanded=True):
                    for item in added:
                        st.markdown(f"- `{item}`")
            if removed:
                with st.expander(f"Removed pages · {len(removed)}", expanded=True):
                    for item in removed:
                        st.markdown(f"- `{item}`")
            if changed:
                with st.expander(f"Changed pages · {len(changed)}", expanded=True):
                    st.dataframe(changed, width="stretch", hide_index=True)

            st.divider()
            col_update, col_help = st.columns([1, 2], vertical_alignment="center")
            with col_update:
                if st.button("Update baseline", icon=":material/bookmark_add:", type="primary", width="stretch"):
                    # Rebuild the baseline directly from the current result without a second crawl.
                    snapshot = {
                        "base_url": summary["base_url"],
                        "pages": {
                            page["url"]: {
                                "title": page.get("title", ""),
                                "status": page.get("status", "").split(":", 1)[0],
                                "form_count": len(page.get("forms", [])),
                                "interactive_element_count": len(page.get("interactive_elements", [])),
                                "heading_count": len(page.get("headings", [])),
                                "link_count": page.get("link_count", 0),
                                "qa_risk_level": page.get("qa_risk_level", "Low"),
                                "accessibility_finding_count": len(page.get("accessibility_findings", [])),
                                "api_request_count": len(page.get("api_requests", [])),
                            }
                            for page in result.get("pages", [])
                        },
                    }
                    baseline_app_id = result.get("app_id", "crawl")
                    baseline_path = os.path.join(OUTPUT_DIR, "reports", f"{baseline_app_id}_baseline.json")
                    os.makedirs(os.path.dirname(baseline_path), exist_ok=True)
                    with open(baseline_path, "w", encoding="utf-8") as handle:
                        json.dump(snapshot, handle, indent=2)
                    result["regression"] = {
                        "available": True,
                        "baseline_created": False,
                        "baseline_updated": True,
                        "baseline_pages": len(snapshot.get("pages", {})),
                        "current_pages": len(snapshot.get("pages", {})),
                        "message": "Current crawl is now the stored baseline.",
                        "added": [], "removed": [], "changed": [],
                    }
                    st.session_state.result = result
                    st.success("Baseline updated to the current crawl.", icon=":material/bookmark_added:")
                    st.rerun()
            with col_help:
                st.caption("Keep the current baseline when investigating drift. Update it only after you have reviewed the detected changes.")

    with tab_report:
        if rag["markdown_path"] and os.path.exists(rag["markdown_path"]):
            with open(rag["markdown_path"], "r", encoding="utf-8") as f:
                md_text = f.read()
            dl1, dl2, dl3 = st.columns(3)
            with dl1:
                st.download_button(
                    "Download Markdown",
                    data=md_text,
                    file_name=os.path.basename(rag["markdown_path"]),
                    mime="text/markdown",
                    icon=":material/download:",
                    width="stretch",
                )
            with dl2:
                if rag["html_path"] and os.path.exists(rag["html_path"]):
                    with open(rag["html_path"], "r", encoding="utf-8") as f:
                        html_text = f.read()
                    st.download_button(
                        "Download HTML",
                        data=html_text,
                        file_name=os.path.basename(rag["html_path"]),
                        mime="text/html",
                        icon=":material/download:",
                        width="stretch",
                    )
            with dl3:
                if rag.get("docx_path") and os.path.exists(rag["docx_path"]):
                    with open(rag["docx_path"], "rb") as f:
                        st.download_button(
                            "Download DOCX",
                            data=f.read(),
                            file_name=os.path.basename(rag["docx_path"]),
                            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                            icon=":material/download:",
                            width="stretch",
                        )
            with st.container(border=True, height=500):
                st.markdown(md_text)
        else:
            st.caption("No report generated.")

    with tab_export:
        st.caption("Raw crawl data, for feeding into another tool or spreadsheet.")
        ex1, ex2 = st.columns(2)
        with ex1:
            st.download_button(
                "Download pages as CSV",
                data=pages_to_csv(result["pages"]),
                file_name=f"{summary['base_url'].replace('://', '_').replace('/', '_')}_pages.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
            )
        with ex2:
            st.download_button(
                "Download pages as JSON",
                data=json.dumps(result["pages"], indent=2),
                file_name=f"{summary['base_url'].replace('://', '_').replace('/', '_')}_pages.json",
                mime="application/json",
                icon=":material/download:",
                width="stretch",
            )
        st.dataframe(result["pages"], width="stretch")
        if st.session_state.execution_results:
            st.download_button(
                "Download QA execution results",
                data=json.dumps(st.session_state.execution_results, indent=2),
                file_name="qa_execution_results.json",
                mime="application/json",
                icon=":material/download:",
                width="stretch",
            )
else:
    st.html("""<div class="empty-webqa"><div class="empty-icon">⌁</div><div><div class="premium-kicker">READY WHEN YOU ARE</div><h3>Start with a URL. Finish with a QA plan.</h3><p>WebQA discovers what is on the site, what looks risky, and which safe checks are worth running next.</p></div><div class="empty-points"><span>Same-domain crawl</span><span>Structural evidence</span><span>Safe QA execution</span></div></div>""")
