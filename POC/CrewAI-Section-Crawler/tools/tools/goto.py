from __future__ import annotations

from typing import Any, List, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)

from utils.util import send_post_action_screenshot


class GotoInput(BaseModel):
    """Input for Goto."""
    url: str = Field(..., description="The URL to navigate to")
    step: str = Field(..., description="Testcase step executing using this tool.")


class Goto(BaseBrowserTool, BaseTool):
    """Tool for navigating the browser to a given URL.

    Rewritten to match the CrewAI + LangChain `BaseBrowserTool` pattern used by
    `click.py`/`fill.py` in this same package — the original file mixed in Agno's tool
    framework (`agno.tools.BaseTool`, `agno.workflows.state.State`) even though
    `crawlerservice.py` instantiates and uses it exactly like the CrewAI tools
    (`Goto(app_id=..., is_crawler=..., sync_browser=...)`, added into the same
    `Agent.tools` / `Task.tools` lists as `ClickTool`/`FillTool`). Two different tool
    frameworks can't coexist in a single CrewAI agent's tool list, so this brings it in
    line with the rest of the crawler stack.
    """

    name: str = "goto"
    description: str = "Navigate to a specified URL in the browser."
    args_schema: Type[BaseModel] = GotoInput

    steps: Optional[List[str]] = Field(default_factory=list, description="List of executed steps")
    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")
    is_crawler: bool = Field(True, description="Flag to indicate if this is a crawler instance")

    def __init__(self, app_id: str = None, socket_handler: Any = None, is_crawler: bool = True, **kwargs):
        """Initialize the Goto tool with an instance-specific app_id."""
        super().__init__(**kwargs)
        self.app_id = app_id
        self.socket_handler = socket_handler
        self.is_crawler = is_crawler
        self.steps = []

    def _run(
        self,
        url: str,
        step: str,
        run_manager: Optional[Any] = None,
    ) -> str:
        """Navigate the synchronous browser to the given URL."""
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")

        try:
            if self.socket_handler:
                self.socket_handler.send_console_message(self.app_id, f"I'm navigating to {url} now.")

            page = get_current_page(self.sync_browser)
            response = page.goto(url)
            status = response.status if response else "unknown"

            if self.socket_handler:
                self.socket_handler.send_console_message(self.app_id, f"I've successfully navigated to {url}. All set!")

            if not self.is_crawler:
                current_step = f"page.goto('{url}')"
                self.steps.append(current_step)
                send_post_action_screenshot(
                    page=page,
                    current_step=current_step,
                    steps=self.steps,
                    socket_handler=self.socket_handler,
                    step=step,
                    action=None,
                    app_id=self.app_id,
                )

            return f"Navigating to {url} returned status code {status}"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"

    async def _arun(
        self,
        url: str,
        step: str,
        run_manager: Optional[Any] = None,
    ) -> str:
        """Navigate the asynchronous browser to the given URL."""
        if self.async_browser is None:
            raise ValueError(f"Asynchronous browser not provided to {self.name}")

        try:
            if self.socket_handler:
                self.socket_handler.send_console_message(self.app_id, f"I'm navigating to {url} now.")

            page = await aget_current_page(self.async_browser)
            response = await page.goto(url)
            await page.wait_for_load_state("networkidle")
            status = response.status if response else "unknown"

            if self.socket_handler:
                self.socket_handler.send_console_message(self.app_id, f"I've successfully navigated to {url}. All set!")

            return f"Navigating to {url} returned status code {status}"
        except Exception as e:
            return f"Error navigating to {url}: {str(e)}"
