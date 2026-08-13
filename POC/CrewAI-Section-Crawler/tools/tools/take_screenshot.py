# Reconstructed during backup cleanup — not present anywhere in the backup. Written to
# match how crawlerservice.py instantiates it (`TakeScreenshot(app_id=..., sync_browser=...)`)
# and its name/usage as a task tool for the crawler agent.
from __future__ import annotations

from typing import Any, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import get_current_page

from utils.util import _save_screenshot


class TakeScreenshotInput(BaseModel):
    step: str = Field(..., description="Testcase step / label this screenshot documents")


class TakeScreenshot(BaseBrowserTool, BaseTool):
    """Take a full-page screenshot of the current browser page and save it under runs/screenshots/."""

    name: str = "take_screenshot"
    description: str = "Take a screenshot of the current page and record its path."
    args_schema: Type[BaseModel] = TakeScreenshotInput

    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")
    images_paths: list = Field(default_factory=list, description="Paths of screenshots taken so far")

    def __init__(self, app_id: str = None, socket_handler: Any = None, **kwargs):
        super().__init__(**kwargs)
        self.app_id = app_id
        self.socket_handler = socket_handler
        self.images_paths = []

    def _run(self, step: str, run_manager: Optional[Any] = None) -> str:
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        path = _save_screenshot(page, "screenshot")
        if path:
            self.images_paths.append(path)
            return f"Screenshot saved to '{path}' for step '{step}'"
        return f"Failed to take screenshot for step '{step}'"
