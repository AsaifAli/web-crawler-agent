# Reconstructed during backup cleanup — not present anywhere in the backup. Written to
# match how crawlerservice.py instantiates it (`ExtractTextTool(app_id=..., sync_browser=...)`).
# Modeled closely on LangChain's own built-in ExtractTextTool (same library already used
# elsewhere in this project).
from __future__ import annotations

from typing import Any, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import get_current_page


class ExtractTextToolInput(BaseModel):
    selector: Optional[str] = Field(None, description="Optional CSS selector to scope extraction to; omit for the whole page")


class ExtractTextTool(BaseBrowserTool, BaseTool):
    """Extract visible text from the current page (or a scoped selector)."""

    name: str = "extract_text"
    description: str = "Extract the visible text content of the current page."
    args_schema: Type[BaseModel] = ExtractTextToolInput

    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")

    def __init__(self, app_id: str = None, socket_handler: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.app_id = app_id
        self.socket_handler = socket_handler

    def _run(self, selector: Optional[str] = None, run_manager: Optional[Any] = None) -> str:
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        try:
            if selector:
                return page.eval_on_selector(selector, "(el) => el.innerText") or ""
            return page.evaluate("() => document.body.innerText") or ""
        except Exception as e:
            return f"Failed to extract text: {e}"
