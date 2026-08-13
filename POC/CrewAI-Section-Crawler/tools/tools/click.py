from __future__ import annotations

import json
import re
from typing import Any, ClassVar, List, Optional, Type

from langchain_core.callbacks import (
    CallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)
from typing import Optional

from utils.util import highlight_element, remove_highlight, send_pre_action_screenshot


class ClickToolInput(BaseModel):
    """
    Input schema for the ClickTool.

    Attributes:
        selector (str): CSS selector or button/text to identify the clickable element.
        example (str): An example text to show how the selector could be used (default: "Login").
    """
    selector: str = Field(..., description="use only when you need to click link or button. You need to pass the link or button text/label")
    step: str = Field (..., description="Testcase step executing using this tool.")


class ClickTool(BaseBrowserTool, BaseTool):
    """
    Tool for interacting with and clicking on elements within a browser.

    This tool clicks on an element with a given CSS selector, and supports additional
    functionality such as handling visible elements, Playwright's strict mode, and timeout configurations.

    Attributes:
        socket_handler (ClassVar[any]): A class-level variable for socket handler.
        steps (ClassVar[list]): A class-level variable for storing steps.
        name (str): Name of the tool (default: "click_element").
        description (str): Description of the tool's functionality (default: "Click on an element with the given Text").
        args_schema (Type[BaseModel]): Input schema for this tool (default: ClickToolInput).
        visible_only (bool): Whether to click only visible elements (default: True).
        playwright_strict (bool): Whether to use Playwright's strict mode for selecting elements (default: False).
        playwright_timeout (float): Timeout in milliseconds for waiting for elements to be ready (default: 2000ms).
    """
    name: str = "click_element"
    description: str = "Click on an element with the given Text"
    args_schema: Type[BaseModel] = ClickToolInput

    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when clicking on elements."""
    playwright_timeout: float = 3_000
    """Timeout (in ms) for Playwright to wait for element to be ready."""


    steps: Optional[List[str]] = Field(default_factory=list, description="List of steps executed")
    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")
    is_crawler: bool = Field(True, description="Flag to indicate if this is a crawler instance")
    tree: Optional[Any] = Field(None, description="Tree structure used in navigation")
    sub_section: List[Any] = Field(default_factory=list, description="List of subsections for navigation")
    index: int = Field(0, description="Index value for tracking navigation steps")
    step : Optional[str] = Field(None, description="Current step which is going to execute")
    child_links_texts : Optional[str] = Field(None, description="Current link sub sections")

    def __init__(self,tree, sub_section, index, step: str = None, app_id: str = None, socket_handler: Any =None, is_crawler: bool =True, **kwargs):
        """
        Initialize the Goto tool with an instance-specific app_id.
        """
        super().__init__(**kwargs)  
        self.app_id = app_id 
        self.socket_handler = socket_handler
        self.steps = []
        self.is_crawler = is_crawler
        self.tree = tree
        self.sub_section = sub_section
        self.index = index
        self.step = step
        self.child_links_texts = []

    def _selector_effective(self, selector: str) -> str:
        """
        Modify the selector to consider visibility constraints if enabled.

        Args:
            selector (str): The original CSS selector to modify.

        Returns:
            str: The modified selector string.
        """
        if not self.visible_only:
            return selector
        return f"{selector} >> visible=1"

    def _run(
        self,
        selector: str,
        step: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Executes the tool to click on the element identified by the selector.

        Args:
            selector (str): The CSS selector of the element to click.
            run_manager (Optional[CallbackManagerForToolRun]): Optional callback manager to track tool execution.

        Returns:
            str: A message indicating whether the click action was successful.

        Raises:
            ValueError: If no synchronous browser is provided for the operation.
        """
        self.step = step
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # Navigate to the desired webpage before using this tool
        selector_effective = self._selector_effective(selector=selector)
        click_text = self.extract_click_text(selector)
        screenshot = None        
        try:
            self.socket_handler.send_console_message(self.app_id, f"I'm initiating learning on {click_text} now.")
            try:
                page.wait_for_load_state("domcontentloaded")
                element= page.query_selector(selector_effective)
                # highlight_element(page, element.element_handle())
            except:
                pass
            page.click(
                selector_effective,
                strict=self.playwright_strict,
                timeout=self.playwright_timeout,
            )
            page.wait_for_load_state('domcontentloaded') 
            if element:
                try:
                    child_links = element.query_selector_all("a")
                    self.child_links_texts = [link.inner_text() for link in child_links] if child_links else []
                except:
                    self.child_links_texts = []
                    pass
            else:
                self.child_links_texts = []


            self.socket_handler.send_console_message(self.app_id, f"Successfully completed learning on '{click_text}'.")
            if self.is_crawler and self.tree[self.index]['section'] != click_text:
                self.sub_section.append({'name':f'{click_text}', 'sub_section':[]})
                self.tree[self.index]['sub_section'] = self.sub_section
                self.socket_handler.send_tree_structure(self.app_id, json.dumps(self.tree))
            if not self.is_crawler:
                screenshot = page.screenshot()
                current_step = f"""page.click(
                    {selector_effective},
                    strict={self.playwright_strict},
                    timeout={self.playwright_timeout},
                )"""
                send_pre_action_screenshot(page,current_step, self.steps, self.socket_handler, screenshot, self.step, None, self.app_id)
        except Exception as e :
            print(e)
            try:
                return self.click_button_by_text(page, click_text, screenshot)
            except Exception as e:
                # remove_highlight(page, "overlayId")
                print(f"click_button_by_text failed to click for {selector}, {e}")
                try:
                    other_radio = page.locator(f'text={selector}')
                    if other_radio.locator('input[type="radio"]').count() > 0:
                        # try:
                        #     highlight_element(page, other_radio.element_handle())
                        # except:
                        #     highlight_element(page, other_radio)
                        screenshot = page.screenshot()
                        other_radio.click()
                        page.wait_for_timeout(1000) 
                        print("Clicked the 'Other' radio button")
                        self.socket_handler.send_console_message(self.app_id, f"I've Successfully checked '{selector}'.")
                        send_pre_action_screenshot(page,None, self.steps, self.socket_handler, screenshot, self.step, None, self.app_id)
                        return f"Clicked element'{selector}'"
                    else:
                        page.wait_for_timeout(500) 
                        element = page.get_by_role('button', name=selector)
                        # highlight_element(page, element)
                        screenshot = page.screenshot()
                        element.click(timeout=self.playwright_timeout)
                        page.wait_for_timeout(1000) 
                        self.socket_handler.send_console_message(self.app_id, f"Successfully completed learning on {click_text}.")
                        if self.is_crawler and self.tree[self.index]['section'] != click_text: 
                            self.sub_section.append({'name':f'{click_text}', 'sub_section':[]})
                            self.tree[self.index]['sub_section'] = self.sub_section
                            self.socket_handler.send_tree_structure(self.app_id, json.dumps(self.tree))
                        if not self.is_crawler:
                            current_step = f"page.get_by_role('button', name='{selector}').click()"
                            send_pre_action_screenshot(page, current_step, self.steps, self.socket_handler, screenshot, self.step, element, self.app_id)
                except Exception as e:
                    # remove_highlight(page,"overlayId")
                    try:
                        page.wait_for_timeout(1000) 
                        element = page.get_by_label(selector, exact=True)
                        # highlight_element(element)
                        screenshot = page.screenshot()
                        element.click(timeout=self.playwright_timeout)
                        page.wait_for_timeout(1000) 
                        self.socket_handler.send_console_message(self.app_id, f"Successfully clicked on {selector}.")
                        if self.is_crawler and self.tree[self.index]['section'] != click_text: 
                            self.sub_section.append({'name':f'{click_text}', 'sub_section':[]})
                            self.tree[self.index]['sub_section'] = self.sub_section
                            self.socket_handler.send_tree_structure(self.app_id, json.dumps(self.tree))
                        if not self.is_crawler:
                            current_step = f" page.get_by_label('{selector}',exact=True).click()"
                            send_pre_action_screenshot(page, current_step, self.steps, self.socket_handler, screenshot, self.step, element, self.app_id)
                    except Exception as e1:
                        # remove_highlight(page,"overlayId")
                        self.socket_handler.send_console_message(self.app_id, f"I wasn't able to click on {selector}. Let's try that again!")
                        print(f"click_button_by_text Failed for {selector}")
                        return f"click_button_by_text Failed for {selector}"
        if self.child_links_texts:
            return f"Clicked element '{selector}' and found having sub sections {self.child_links_texts}, you can visit them by click firstly on {selector} and then sub section link"
        return f"Clicked element '{selector}'"

    def click_button_by_text(self, page, button_text: str, screenshot) -> str:
        """
        Click a button or link by its visible text.

        This method searches for elements (buttons or links) by their text content, sanitizing
        the button text and trying multiple strategies to locate and click the element.

        Args:
            page: The Playwright page object to perform actions on.
            button_text (str): The visible text of the button or link to click.

        Returns:
            str: A message indicating whether the click was successful.

        Raises:
            Exception: If no element matching the text was found and clicked.
        """
        default_button_text = button_text
        button_text = button_text.replace('"', '').replace("'", "").strip().lower()

        # Wait for the page to be fully loaded
        page.wait_for_load_state("domcontentloaded")

        if button_text in ['log in', 'login', 'sign in', 'signin']:
            xpaths = [
                f"//button[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']",
                f"//button[contains(normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), '{button_text}')]",
                f"//button[normalize-space(translate(translate(translate(., '\"', ''), \"'\", ''), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']"
            ]
        else:
            xpaths = [
                f"//a[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}'] | //button[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']",
                f"//a[contains(normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), '{button_text}')] | //button[contains(normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), '{button_text}')]",
                f"//li[normalize-space(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}'] | //li[normalize-space(translate(translate(translate(., '\"', ''), \"'\", ''), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']",
                f"//*[normalize-space(translate(translate(translate(., '\"', ''), \"'\", ''), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']",
            ]
            # xpaths = [
            #         # Match <a> or <button> elements with exact text (case-insensitive)
            #         f"//a[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}'] | "
            #         f"//button[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']",

            #         # Match <a> or <button> elements containing the text (case-insensitive)
            #         f"//a[contains(normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), '{button_text}')] | "
            #         f"//button[contains(normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')), '{button_text}')]",
                    
            #         # Match <li> elements with exact or partial text (case-insensitive) and handle quotes
            #         f"//li[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}'] | "
            #         f"//li[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ\"\'', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}'] | ",
                    
            #         # Generic: Match any element with exact text (case-insensitive) and handle quotes
            #         f"//*[normalize-space(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ\"\'', 'abcdefghijklmnopqrstuvwxyz')) = '{button_text}']"
            #     ]


        element = None
        page.wait_for_load_state("domcontentloaded")
        for xpath in xpaths:
            try:
                # Use Playwright's query selector to locate the element
                element = page.query_selector(xpath)
                if element:
                    # try:
                    #     highlight_element(page, element.element_handle())
                    # except:
                    #     highlight_element(page, element)
                    screenshot = page.screenshot()
                    element.click(timeout=self.playwright_timeout)
                    page.wait_for_load_state('domcontentloaded') 
                    if element:
                        try:
                            child_links = element.query_selector_all("a")
                            self.child_links_texts = [link.inner_text() for link in child_links] if child_links else []
                        except:
                            self.child_links_texts = []
                            pass
                    else:
                        self.child_links_texts = []
                    self.socket_handler.send_console_message(self.app_id, f"Successfully executed the click on {default_button_text}.")


                    if self.is_crawler and self.tree[self.index]['section'] != default_button_text:  
                        self.sub_section.append({'name':f'{default_button_text}', 'sub_section':[]})
                        self.tree[self.index]['sub_section'] = self.sub_section
                        self.socket_handler.send_tree_structure(self.app_id, json.dumps(self.tree))
                        
                    if not self.is_crawler:
                        current_step = f"element = page.query_selector('{xpath}')\n    element.click()"
                        send_pre_action_screenshot(page, current_step, self.steps, self.socket_handler, screenshot, self.step, element, self.app_id)
                        
                    # return f"Successfully clicked on '{default_button_text}'"
                    if self.child_links_texts:
                        return f"Clicked element '{default_button_text}' and found having sub sections {self.child_links_texts}, you can visit them by click firstly on {default_button_text} and then sub section link"
                    return f"Successfully clicked on '{default_button_text}'"
                
            except Exception as e:
                # remove_highlight(page,"overlayId")
                print(e)
                continue  # Try the next XPath if the current one fails
        raise Exception(f"Click not performed on '{default_button_text}'. Do try again")

    def extract_click_text(self, selector: str) -> str:
        """
        Extracts the text inside :has-text() from a selector.

        Args:
            selector (str): The CSS selector that may contain ":has-text('<text>')".

        Returns:
            str: The extracted text if found; otherwise, the original selector.
        """
        try:
            if "has-text" in selector:
                pattern = r":has-text\('([^']*)'\)"
                match = re.search(pattern, selector)

                if match:
                    return match.group(1)  # Extracted text
        except Exception as e:
            print(f"Error extracting text from selector: {e}")

        return selector  # Default to original selector if no match
