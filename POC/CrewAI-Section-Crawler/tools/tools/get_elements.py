# Reconstructed during backup cleanup — not present anywhere in the backup. Written to
# match how crawlerservice.py instantiates it (`GetElementsTool(app_id=..., sync_browser=...)`)
# and its listed usage as one of the crawler agent's tools.
from __future__ import annotations

from typing import Any, List, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import get_current_page

DEFAULT_SELECTORS = ["a", "button", "input", "select", "textarea", "[role=button]"]


class GetElementsToolInput(BaseModel):
    selector: str = Field(
        "a, button, input, select, textarea, [role=button]",
        description="CSS selector for the elements to list (defaults to common interactive elements)",
    )


class GetElementsTool(BaseBrowserTool, BaseTool):
    """List interactive elements on the current page (tag, visible text, id, name, type)."""

    name: str = "get_elements"
    description: str = "Get a list of interactive elements (links, buttons, inputs, ...) visible on the current page."
    args_schema: Type[BaseModel] = GetElementsToolInput

    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")

    def __init__(self, app_id: str = None, socket_handler: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.app_id = app_id
        self.socket_handler = socket_handler

    def _run(self, selector: str = "a, button, input, select, textarea, [role=button]", run_manager: Optional[Any] = None) -> str:
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        try:
            elements = page.eval_on_selector_all(
                selector,
                """(els) => els.slice(0, 200).map(el => ({
                    tag: el.tagName.toLowerCase(),
                    text: (el.innerText || el.value || '').trim().slice(0, 80),
                    id: el.id || null,
                    name: el.getAttribute('name'),
                    type: el.getAttribute('type'),
                    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
                }))""",
            )
            return str(elements)
        except Exception as e:
            return f"Failed to get elements for selector '{selector}': {e}"
