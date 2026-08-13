# Reconstructed during backup cleanup — not present anywhere in the backup. Written to
# match how crawlerservice.py instantiates it (`SequentialClickTool(tree=..., sub_section=...,
# index=..., app_id=..., is_crawler=..., sync_browser=...)`, identical to ClickTool) and
# what its name implies: click through a list of selectors in order, reusing ClickTool's
# own `_run` for each one so the two tools can't drift in behavior.
from __future__ import annotations

from typing import Any, List, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool

from tools.tools.click import ClickTool


class SequentialClickToolInput(BaseModel):
    selectors: List[str] = Field(..., description="Ordered list of selectors/labels to click, one after another")
    step: str = Field(..., description="Testcase step executing using this tool.")


class SequentialClickTool(BaseBrowserTool, BaseTool):
    """Click through a sequence of elements in order, e.g. a multi-step wizard or menu path."""

    name: str = "sequential_click_elements"
    description: str = "Click a sequence of elements, one after another, in the given order."
    args_schema: Type[BaseModel] = SequentialClickToolInput

    tree: Optional[Any] = Field(None, description="Tree structure used in navigation")
    sub_section: List[Any] = Field(default_factory=list, description="List of subsections for navigation")
    index: int = Field(0, description="Index value for tracking navigation steps")
    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")
    is_crawler: bool = Field(True, description="Flag to indicate if this is a crawler instance")

    def __init__(self, tree, sub_section, index, app_id: str = None, socket_handler: Any = None, is_crawler: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.tree = tree
        self.sub_section = sub_section
        self.index = index
        self.app_id = app_id
        self.socket_handler = socket_handler
        self.is_crawler = is_crawler

    def _run(self, selectors: List[str], step: str, run_manager: Optional[Any] = None) -> str:
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")

        click_tool = ClickTool(
            tree=self.tree,
            sub_section=self.sub_section,
            index=self.index,
            app_id=self.app_id,
            socket_handler=self.socket_handler,
            is_crawler=self.is_crawler,
            sync_browser=self.sync_browser,
        )

        results = []
        for selector in selectors:
            results.append(click_tool._run(selector=selector, step=step))
        return " | ".join(results)
