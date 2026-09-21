"""Safe Playwright smoke contract for the Agent Harness.

Runs the real WebCrawler DOM-analysis/risk/test-generation code against a
controlled in-memory page. No external site is crawled and no form is submitted.
"""
from __future__ import annotations

from fastapi import FastAPI
from playwright.async_api import async_playwright

from crawler import WebCrawler

app = FastAPI(title="WebQA Harness Adapter", version="1.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "webqa-harness"}


@app.post("/harness/smoke")
async def smoke(payload: dict | None = None):
    fixture = """\n    <!doctype html>\n    <html lang='en'>\n      <head><title>WebQA Harness Fixture</title></head>\n      <body>\n        <main>\n          <h1>Harness Fixture</h1>\n          <section><h2>Contact</h2><form><label for='email'>Email</label><input id='email' name='email' required><button type='submit'>Send</button></form></section>\n          <nav><a href='https://example.com/'>Example</a></nav>\n        </main>\n      </body>\n    </html>\n    """
    crawler = WebCrawler("https://smoke.local")
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.set_content(fixture)
        structure = await crawler.extract_page_structure(page)
        interactive = await crawler.extract_interactive_elements(page)
        accessibility = await crawler.assess_accessibility(page)
        page_data = {
            "url": "https://smoke.local",
            **structure,
            "interactive_elements": interactive,
            "console_errors": [],
            "failed_requests": [],
            "accessibility_findings": accessibility,
        }
        candidates = crawler.build_interaction_candidates(interactive, structure.get("forms", []))
        risk = crawler.assess_qa_risk(page_data)
        tests = crawler.generate_test_cases(page_data)
        await browser.close()

    checks = {
        "playwright": True,
        "dom_structure": bool(structure.get("headings")),
        "interactive_elements": len(interactive) > 0,
        "accessibility_analysis": isinstance(accessibility, list),
        "risk_analysis": isinstance(risk, dict) and "score" in risk,
        "test_generation": len(tests) > 0,
        "safe_execution_boundary": all(item.get("safe_by_default") is not False for item in candidates if item.get("action") == "navigate"),
    }
    core_pass = all(checks.values())
    return {
        "status": "completed" if core_pass else "failed",
        "service": "webqa",
        "workflow": "harness_smoke",
        "checks": checks,
        "observed": {
            "headings": len(structure.get("headings", [])),
            "interactive_elements": len(interactive),
            "accessibility_findings": len(accessibility),
            "qa_risk_score": risk.get("score"),
            "generated_tests": len(tests),
        },
        "payload_received": bool(payload),
    }
