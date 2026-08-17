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

st.set_page_config(page_title="Web crawler", page_icon=":material/travel_explore:", layout="wide")

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

# --- Header -------------------------------------------------------------

st.title(":material/travel_explore: Web crawler", anchor=False)
st.caption(
    "Crawls a web application with Playwright, analyzes its structure and health, "
    "and generates an evidence-based QA plan with prioritized test scenarios."
)

# --- Sidebar: connection + run history -----------------------------------

with st.sidebar:
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

# --- Crawl form -----------------------------------------------------------

with st.form("crawl_form", border=True):
    st.subheader(":material/link: Target", anchor=False)
    url = st.text_input("Start URL", placeholder="https://example.com")

    col1, col2 = st.columns(2)
    with col1:
        username = st.text_input("Username (optional)", icon=":material/person:")
        app_id = st.text_input("Run label", value="crawl", icon=":material/label:")
    with col2:
        password = st.text_input("Password (optional)", type="password", icon=":material/lock:")
        max_pages = st.slider("Max pages", min_value=1, max_value=100, value=10)

    sections_raw = st.text_input(
        "Extra section paths (comma-separated, optional)", placeholder="/about, /contact"
    )

    submitted = st.form_submit_button(
        "Start crawl", icon=":material/play_arrow:", type="primary", width="stretch"
    )

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
            st.session_state.result = result
            st.session_state.error = None
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
        st.caption("Runs only non-destructive checks such as page structure, form rendering, input discovery, navigation-link presence, and accessibility checks. It does not submit forms or activate arbitrary buttons.")
        safe_titles = {"Verify form renders correctly", "Verify input controls", "Verify navigation links", "Verify page structure", "Review missing heading structure", "Review accessibility findings"}
        safe_cases = [c for c in test_cases if c.get("title") in safe_titles]
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric("Executable safe tests", len(safe_cases))
        ec2.metric("Executed", len(st.session_state.execution_results))
        passed = sum(r.get("status") == "PASSED" for r in st.session_state.execution_results)
        ec3.metric("Passed", passed)
        if safe_cases:
            selected_ids = st.multiselect("Select safe tests", [f"{c['id']} — {c['title']}" for c in safe_cases], default=[f"{c['id']} — {c['title']}" for c in safe_cases[:10]])
            if st.button("Run selected safe tests", icon=":material/play_arrow:", type="primary"):
                selected = {item.split(" — ", 1)[0] for item in selected_ids}
                chosen = [c for c in safe_cases if c["id"] in selected]
                crawler = WebCrawler(url=summary["base_url"], app_id="qa_execution", output_dir=OUTPUT_DIR)
                with st.spinner("Executing safe QA checks with Playwright..."):
                    st.session_state.execution_results = asyncio.run(crawler.execute_safe_qa_tests(chosen, headless=True, max_tests=len(chosen)))
        else:
            st.info("No non-destructive automated checks are available for this crawl.", icon=":material/info:")
        if st.session_state.execution_results:
            execution_df = pd.DataFrame(st.session_state.execution_results)
            st.dataframe(execution_df[["id", "title", "status", "duration_ms", "actual_result"]], width="stretch", hide_index=True)
            for execution in st.session_state.execution_results:
                icon = ":material/check_circle:" if execution["status"] == "PASSED" else ":material/error:"
                with st.expander(f"{icon} {execution['id']} — {execution['title']} — {execution['status']}"):
                    st.write(execution.get("actual_result", ""))
                    st.caption(f"Duration: {execution.get('duration_ms', 0)} ms · URL: {execution.get('url', '')}")
                    if execution.get("evidence"):
                        st.markdown("**Evidence**")
                        for item in execution["evidence"]:
                            st.markdown(f"- {item}")
                    screenshot = execution.get("screenshot_path", "")
                    if screenshot and os.path.exists(screenshot):
                        st.image(screenshot, caption="Execution evidence", width="stretch")

    with tab_regression:
        regression = result.get("regression", {})
        st.subheader(":material/compare_arrows: Crawl regression", anchor=False)
        st.caption("Compares page structure, forms, interactions, links, status, and QA risk with the previous crawl baseline. Content is not stored in the baseline.")
        if not regression.get("available"):
            st.info(regression.get("message", "Baseline created for future comparisons."), icon=":material/schedule:")
        else:
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Added pages", len(regression.get("added", [])))
            rc2.metric("Removed pages", len(regression.get("removed", [])))
            rc3.metric("Changed pages", len(regression.get("changed", [])))
            if regression.get("added"):
                st.markdown("### Added pages")
                for item in regression["added"]:
                    st.markdown(f"- `{item}`")
            if regression.get("removed"):
                st.markdown("### Removed pages")
                for item in regression["removed"]:
                    st.markdown(f"- `{item}`")
            if regression.get("changed"):
                st.markdown("### Changed pages")
                st.dataframe(regression["changed"], width="stretch", hide_index=True)
            if not any(regression.get(k) for k in ("added", "removed", "changed")):
                st.success("No structural regression detected compared with the previous baseline.", icon=":material/check_circle:")

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
    st.divider()
    with st.container(key="empty_state_container"):
        st.info("Enter a URL above and start a crawl to see results here.", icon=":material/travel_explore:")
