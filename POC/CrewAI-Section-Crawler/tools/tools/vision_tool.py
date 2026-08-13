# Reconstructed during backup cleanup — not present anywhere in the backup, and never
# instantiated in crawlerservice.py either (imported but unused there, same as
# TestCaseGenerator) — so its exact intended interface is a guess based on the name and
# project context (crawler takes screenshots, document_creator writes docs from them).
# Uses OpenAI's vision-capable chat completions to describe a screenshot; requires
# OPENAI_API_KEY. Returns a clear error string (not an exception) if unset, so importing
# this module never breaks a run that doesn't use it.
from __future__ import annotations

import base64
import os
from typing import Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool


class VisionToolInput(BaseModel):
    image_path: str = Field(..., description="Path to a screenshot image file to analyze")
    question: str = Field(
        "Describe the UI elements, layout, and any text visible in this screenshot.",
        description="What to ask the vision model about the image",
    )


class VisionTool(BaseTool):
    """Describe a screenshot using an OpenAI vision-capable chat model."""

    name: str = "analyze_screenshot"
    description: str = "Analyze a screenshot image and describe its UI content using a vision-capable LLM."
    args_schema: Type[BaseModel] = VisionToolInput
    model: str = "gpt-4o-mini"

    def _run(self, image_path: str, question: Optional[str] = None, run_manager: Optional[object] = None) -> str:
        if not os.getenv("OPENAI_API_KEY"):
            return "VisionTool: OPENAI_API_KEY is not set; cannot analyze image."
        if not os.path.isfile(image_path):
            return f"VisionTool: image not found at '{image_path}'."

        try:
            from openai import OpenAI

            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            client = OpenAI()
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": question or "Describe this screenshot."},
                            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                        ],
                    }
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            return f"VisionTool failed: {e}"
