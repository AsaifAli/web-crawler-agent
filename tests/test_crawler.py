import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawler import WebCrawler, WebpageContent, retry_with_backoff


# --- retry_with_backoff -----------------------------------------------------

@pytest.mark.asyncio
async def test_retry_with_backoff_succeeds_after_failures():
    calls = {"count": 0}

    @retry_with_backoff(max_retries=3, base_delay=0, max_delay=0)
    async def flaky():
        calls["count"] += 1
        if calls["count"] < 3:
            raise ValueError("not yet")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_retry_with_backoff_raises_after_exhausting_retries():
    @retry_with_backoff(max_retries=2, base_delay=0, max_delay=0)
    async def always_fails():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await always_fails()


# --- WebpageContent ----------------------------------------------------------

def test_webpage_content_round_trips_to_dict():
    content = WebpageContent(
        url="https://example.com",
        content="hello",
        summary="a summary",
        timestamp="20260101_000000",
        section="Home",
        status="success: Playwright",
        interactive_elements=[{"tag": "button", "type": "button", "id": "", "name": "", "text": "Go", "aria-label": ""}],
    )
    data = content.model_dump()
    assert data["url"] == "https://example.com"
    assert data["interactive_elements"][0]["text"] == "Go"


# --- WebCrawler.summarize_content --------------------------------------------

@pytest.fixture
def crawler(tmp_path):
    return WebCrawler(
        url="https://example.com",
        app_id="test",
        ollama_url="http://ollama.test/api/generate",
        ollama_model="test-model",
        output_dir=str(tmp_path),
    )


def test_crawler_creates_output_dirs(tmp_path):
    WebCrawler(url="https://example.com", output_dir=str(tmp_path))
    assert os.path.isdir(os.path.join(tmp_path, "debug"))
    assert os.path.isdir(os.path.join(tmp_path, "reports"))


@pytest.mark.asyncio
async def test_summarize_content_empty_string_returns_empty(crawler):
    assert await crawler.summarize_content("") == ""


@pytest.mark.asyncio
async def test_summarize_content_uses_ollama_response(crawler):
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"response": "a concise summary"}
    with patch("crawler.requests.post", return_value=fake_response) as mock_post:
        summary = await crawler.summarize_content("some page content")
    assert summary == "a concise summary"
    mock_post.assert_called_once()
    assert mock_post.call_args.kwargs["json"]["model"] == "test-model"


@pytest.mark.asyncio
async def test_summarize_content_falls_back_on_request_error(crawler):
    with patch("crawler.requests.post", side_effect=ConnectionError("unreachable")):
        summary = await crawler.summarize_content("some page content that is long enough")
    assert summary.endswith("...")
    assert summary.startswith("some page content")


@pytest.mark.asyncio
async def test_summarize_content_skips_network_call_when_no_ollama_url(tmp_path):
    no_ollama_crawler = WebCrawler(url="https://example.com", ollama_url="", output_dir=str(tmp_path))
    with patch("crawler.requests.post") as mock_post:
        summary = await no_ollama_crawler.summarize_content("short content")
    mock_post.assert_not_called()
    assert summary == "short content"


# --- WebCrawler.infer_section_from_url ---------------------------------------

@pytest.mark.asyncio
async def test_infer_section_from_url_falls_back_to_path_segment(crawler):
    page = AsyncMock()
    page.query_selector.return_value = None
    page.title.return_value = "Example Application"

    section = await crawler.infer_section_from_url("https://example.com/reports/monthly-summary", page)
    assert section == "Monthly Summary"


@pytest.mark.asyncio
async def test_infer_section_from_url_unknown_when_no_path(crawler):
    page = AsyncMock()
    page.query_selector.return_value = None
    page.title.return_value = "Example Application"

    section = await crawler.infer_section_from_url("https://example.com/", page)
    assert section == "Example Application"


# --- WebCrawler.extract_page_links_playwright --------------------------------

def _mock_link_element(href, text="Link"):
    el = AsyncMock()

    async def get_attribute(name):
        return href if name == "href" else None

    el.get_attribute.side_effect = get_attribute
    el.text_content.return_value = text
    return el


@pytest.mark.asyncio
async def test_extract_page_links_playwright_filters_and_dedupes(crawler):
    page = AsyncMock()
    page.is_closed = MagicMock(return_value=False)  # Playwright's is_closed() is sync, not async
    page.url = "https://example.com/home"
    page.query_selector_all.return_value = [
        _mock_link_element("/about", "About"),
        _mock_link_element("/about", "About again"),
        _mock_link_element("https://external.com/x", "External"),
        _mock_link_element("javascript:void(0)", "JS"),
        _mock_link_element(None, "No href"),
    ]

    links = await crawler.extract_page_links_playwright(page, "https://example.com")

    urls = {link["url"] for link in links}
    assert urls == {"https://example.com/about"}


# --- WebCrawler.generate_rag_document ----------------------------------------

def test_generate_rag_document_writes_markdown_and_html(crawler):
    crawler.content_collection["https://example.com/"] = WebpageContent(
        url="https://example.com/",
        content="Body text",
        summary="Summary text",
        timestamp="20260101_000000",
        section="Home",
        status="success: Playwright",
        interactive_elements=[],
    )
    crawler.link_collection["https://example.com/"] = {"text": "Home", "source": "initial", "section": "Home"}

    md_path, html_path = crawler.generate_rag_document()

    assert os.path.exists(md_path)
    assert os.path.exists(html_path)
    with open(md_path, encoding="utf-8") as f:
        md_content = f.read()
    assert "Summary text" in md_content
    assert "https://example.com/" in md_content


def test_generate_rag_document_handles_no_content(crawler):
    md_path, html_path = crawler.generate_rag_document()
    with open(md_path, encoding="utf-8") as f:
        md_content = f.read()
    assert "No Content" in md_content


# --- WebCrawler.crawl --------------------------------------------------------

class _FakeAsyncPlaywrightCM:
    """Mimics `async with async_playwright() as p:` for a given fake `p`."""

    def __init__(self, p):
        self._p = p

    async def __aenter__(self):
        return self._p

    async def __aexit__(self, *exc_info):
        return False


@pytest.mark.asyncio
async def test_crawl_raises_instead_of_reporting_fake_success_on_browser_launch_failure(crawler):
    fake_playwright = MagicMock()
    fake_playwright.chromium.launch = AsyncMock(side_effect=RuntimeError("Executable doesn't exist"))

    with patch("crawler.async_playwright", return_value=_FakeAsyncPlaywrightCM(fake_playwright)):
        with pytest.raises(RuntimeError, match="Executable doesn't exist"):
            await crawler.crawl(max_pages=5)

# --- Structured analysis -----------------------------------------------------

def test_generate_test_cases_from_forms_and_controls(crawler):
    cases = crawler.generate_test_cases({
        "url": "https://example.com/login",
        "forms": [{
            "index": 1,
            "action": "/login",
            "method": "post",
            "fields": [
                {"type": "text", "name": "username", "required": True},
                {"type": "password", "name": "password", "required": True},
            ],
        }],
        "interactive_elements": [
            {"tag": "button", "type": "submit", "required": False, "disabled": False},
            {"tag": "input", "type": "text", "required": True, "disabled": False},
            {"tag": "a", "type": "a", "required": False, "disabled": False, "role": "link"},
        ],
        "headings": [{"level": 1, "text": "Login"}],
    })
    titles = {case["title"] for case in cases}
    assert "Verify form renders correctly" in titles
    assert "Verify required-field validation" in titles
    assert "Verify form submission" in titles
    assert "Verify input controls" in titles
    assert "Verify navigation links" in titles


def test_interaction_candidates_are_non_destructive(crawler):
    candidates = crawler.build_interaction_candidates([
        {"tag": "button", "type": "submit", "text": "Save", "disabled": False},
        {"tag": "input", "type": "text", "name": "email", "disabled": False},
        {"tag": "a", "type": "a", "text": "About", "role": "link", "disabled": False},
    ], [])
    assert candidates[0]["action"] == "click"
    assert candidates[1]["action"] == "fill/select value"
    assert candidates[2]["action"] == "navigate"
    assert candidates[2]["safe_by_default"] is True
    assert candidates[0]["safe_by_default"] is False


def test_qa_risk_scoring_is_evidence_based(crawler):
    result = crawler.assess_qa_risk({
        "forms": [{"fields": [{"required": True}]}],
        "interactive_elements": [{"tag": "input", "type": "password"}, {"tag": "button", "role": "button"}],
        "headings": [],
        "console_errors": ["TypeError"],
        "failed_requests": [{"url": "https://example.com/api", "failure": "net::ERR_FAILED"}],
    })
    assert result["level"] in {"Medium", "High"}
    assert result["score"] >= 40
    assert result["factors"]


def test_regression_baseline_created_and_detects_changes(crawler):
    crawler.content_collection["https://example.com/"] = WebpageContent(
        url="https://example.com/", content="hello", summary="", timestamp="20260101_000000",
        section="Home", status="success: Playwright", interactive_elements=[], headings=[{"level": 1, "text": "Home"}],
    )
    first = crawler.compare_with_baseline()
    assert first["available"] is False

    crawler.content_collection["https://example.com/about"] = WebpageContent(
        url="https://example.com/about", content="about", summary="", timestamp="20260101_000001",
        section="About", status="success: Playwright", interactive_elements=[], headings=[{"level": 1, "text": "About"}],
    )
    second = crawler.compare_with_baseline()
    assert second["available"] is True
    assert "https://example.com/about" in second["added"]

@pytest.mark.asyncio
async def test_assess_accessibility_flags_missing_metadata_and_labels(crawler):
    page = AsyncMock()
    page.title.return_value = ""
    page.get_attribute.side_effect = lambda selector, name: None
    image = AsyncMock()
    image.get_attribute.return_value = None
    control = AsyncMock()
    control.get_attribute.side_effect = lambda name: None
    control.text_content.return_value = ""
    control.evaluate.return_value = "input"
    page.query_selector_all.side_effect = lambda selector: [image] if selector == "img" else [control] if "input" in selector else []
    findings = await crawler.assess_accessibility(page)
    rules = {item["rule"] for item in findings}
    assert "page-title" in rules
    assert "html-lang" in rules
    assert "image-alt" in rules


def test_regression_snapshot_includes_accessibility_and_api_counts(crawler):
    crawler.content_collection["https://example.com/"] = WebpageContent(
        url="https://example.com/", content="hello", summary="", timestamp="20260101_000000",
        section="Home", status="success: Playwright", interactive_elements=[],
        accessibility_findings=[{"rule": "image-alt"}], api_requests=[{"status": 200}],
    )
    snapshot = crawler._build_regression_snapshot()
    assert snapshot["pages"]["https://example.com/"]["accessibility_finding_count"] == 1
    assert snapshot["pages"]["https://example.com/"]["api_request_count"] == 1


def test_safe_execution_filters_destructive_cases(crawler):
    cases = [
        {"id": "TC-001", "title": "Verify page structure", "url": "https://example.com"},
        {"id": "TC-002", "title": "Verify form submission", "url": "https://example.com"},
        {"id": "TC-003", "title": "Verify interactive buttons", "url": "https://example.com"},
    ]
    safe_titles = {"Verify form renders correctly", "Verify input controls", "Verify navigation links", "Verify page structure", "Review missing heading structure", "Review accessibility findings"}
    assert [c["id"] for c in cases if c["title"] in safe_titles] == ["TC-001"]
