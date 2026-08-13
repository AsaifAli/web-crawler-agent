# Reconstructed during backup cleanup — not present anywhere in the backup. Written to
# match how crawlerservice.py instantiates it (`ExtractHyperlinksTool(app_id=..., sync_browser=...)`).
# Modeled closely on LangChain's own built-in ExtractHyperlinksTool (same library already
# used elsewhere in this project), scoped to a given selector.
from __future__ import annotations

from typing import Any, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import get_current_page


class ExtractHyperlinksToolInput(BaseModel):
    selector: str = Field("a", description="CSS selector to scope link extraction to (default: all <a> tags)")


class ExtractHyperlinksTool(BaseBrowserTool, BaseTool):
    """Extract all hyperlinks (text + absolute href) from the current page, or a section of it."""

    name: str = "extract_hyperlinks"
    description: str = "Extract all hyperlinks and their visible text from the current page."
    args_schema: Type[BaseModel] = ExtractHyperlinksToolInput

    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")

    def __init__(self, app_id: str = None, socket_handler: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.app_id = app_id
        self.socket_handler = socket_handler

    def _run(self, selector: str = "a", run_manager: Optional[Any] = None) -> str:
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        try:
            links = page.eval_on_selector_all(
                selector,
                "(els) => els.map(el => ({text: (el.innerText || '').trim(), href: el.href})).filter(l => l.href)",
            )
            return str(links)
        except Exception as e:
            return f"Failed to extract hyperlinks for selector '{selector}': {e}"
