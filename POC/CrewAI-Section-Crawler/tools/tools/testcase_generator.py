# Reconstructed during backup cleanup — not present anywhere in the backup. Written to
# match its no-arg instantiation (`TestCaseGenerator()`) in crawlerservice.py and its name.
# Note: in crawlerservice.py this tool is instantiated but never attached to an agent's
# tools list or a Task — it may have been vestigial even in the original. Kept as a plain
# CrewAI tool (no browser dependency) so it's usable standalone if wired in later.
from __future__ import annotations

from typing import List, Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class TestCaseGeneratorInput(BaseModel):
    section: str = Field(..., description="Section name the test cases are for")
    elements: List[str] = Field(default_factory=list, description="Interactive elements found in the section (labels/selectors)")


class TestCaseGenerator(BaseTool):
    """Turn a list of discovered interactive elements into a simple structured test case outline."""

    name: str = "generate_testcases"
    description: str = "Generate a structured list of test case steps for a section, given its interactive elements."
    args_schema: Type[BaseModel] = TestCaseGeneratorInput

    def _run(self, section: str, elements: Optional[List[str]] = None, run_manager: Optional[object] = None) -> str:
        elements = elements or []
        if not elements:
            return f"No interactive elements were provided for section '{section}'; nothing to generate."

        lines = [f"Test Cases: {section}", "=" * (13 + len(section))]
        for i, el in enumerate(elements, start=1):
            lines.append(f"{i}. Verify that interacting with '{el}' in the '{section}' section behaves as expected.")
            lines.append(f"   - Navigate to the '{section}' section.")
            lines.append(f"   - Locate element: {el}")
            lines.append("   - Perform the expected interaction (click/fill) and verify the resulting state.")
        return "\n".join(lines)
