from __future__ import annotations
import re
from typing import Any, ClassVar, Optional, Type

from langchain_core.callbacks import (
    AsyncCallbackManagerForToolRun,
    CallbackManagerForToolRun,
)
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from langchain_community.tools.playwright.base import BaseBrowserTool
from langchain_community.tools.playwright.utils import (
    aget_current_page,
    get_current_page,
)

from utils.util import highlight_element, send_post_action_screenshot


class FillToolInput(BaseModel):
    """Input for FillTool."""
    selector: str = Field(..., description="label of the element to fill")
    value: str = Field(None, description="text to be filled in element")
    step: str = Field (..., description="Testcase step executing using this tool.")


class FillTool(BaseBrowserTool, BaseTool):
    """Tool for Filling on an element with the given label text."""

    name: str = "Fill_element"
    description: str = "Fill on an input element with the given label text, click,check radio button, chrckboxes etc."
    args_schema: Type[BaseModel] = FillToolInput
    visible_only: bool = True
    """Whether to consider only visible elements."""
    playwright_strict: bool = False
    """Whether to employ Playwright's strict mode when Filling on elements."""
    playwright_timeout: float = 3_000
    """Timeout (in ms) for Playwright to wait for element to be ready."""
    steps: ClassVar[list]= []
    step: str = None
    app_id: Optional[str] = Field(None, description="Unique identifier for the app instance")
    socket_handler: Any = Field(None, description="Socket handler for communication")
    is_crawler: bool = Field(True, description="Flag to indicate if this is a crawler instance")

    def __init__(self, app_id: str = None, socket_handler: Any =None, is_crawler: bool =True, **kwargs):
        """
        Initialize the Goto tool with an instance-specific app_id.
        """
        super().__init__(**kwargs)  
        self.app_id = app_id 
        self.socket_handler = socket_handler
        self.is_crawler = is_crawler


    def _selector_effective(self, selector: str) -> str:
        if not self.visible_only:
            return selector
        return f"{selector}"
    def _value_effective(self, value: str) -> str:
        if not self.visible_only:
            return value
        return f"{value}"

    def _run(
        self,
        selector: str,
        step: str,
        value: str ,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        self.step = step
        if self.sync_browser is None:
            raise ValueError(f"Synchronous browser not provided to {self.name}")
        page = get_current_page(self.sync_browser)
        # Navigate to the desired webpage before using this tool
        selector_effective = self._selector_effective(selector=selector)
        value_effective = self._value_effective(value=value)
        formated_selector = selector.replace(" ", "");

        try:
            self.socket_handler.send_console_message(self.app_id, f"I'm entering the value {value_effective} into {selector_effective} now.")
            element = page.get_by_label(selector_effective, timeout=self.playwright_timeout) 
            # Timeout of 5 seconds
            input_element = element.locator('xpath=following-sibling::input', timeout=self.playwright_timeout)
            if input_element:
                highlight_element(page, input_element) 
            input_element.fill(value_effective, timeout=self.playwright_timeout)
            self.socket_handler.send_console_message(self.app_id, f"I've successfully entered {value_effective} into {selector_effective}.")
            if not self.is_crawler:
                current_step = f"""page.fill(
                    {selector_effective},
                    {value_effective},
                    strict={self.playwright_strict},
                    timeout={self.playwright_timeout},
                )"""
                send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.step, input_element)
        except Exception as e:
            try:
                page.wait_for_load_state("domcontentloaded")
                label_input_element = self._get_label_element(page, selector)

                if label_input_element is None:
                    label_input_element = self.get_input_after_label(page, selector)

                if label_input_element is not None:
                    label_input_class = label_input_element.get_attribute("class")
                    element_type = label_input_element.get_attribute("type")
                    label_input_role = self.getRole(label_input_element)
                    tag_name = label_input_element.evaluate("el => el.tagName.toLowerCase()")
                    #tag_name = label_input_element.evaluate("el => el.nodeName.toLowerCase()")
                    print(f"tag_name is {tag_name} for {selector} label_input_class is {label_input_class}")
                    if tag_name == "div" and 'tox-' in label_input_class:
                        content_editor = page.locator('.tox-edit-area iframe')
                        if content_editor != None:
                            #page.wait_for_timeout(500)
                            text_editor = page.locator("iframe[title=\"Rich Text Area\\. Press ALT-0 for help\\.\"]").content_frame.locator("#tinymce")
                            #page.wait_for_timeout(500)
                            highlight_element(page, text_editor.element_handle())
                            text_editor.fill(value_effective)
                            self.socket_handler.send_console_message(self.app_id, f"I've successfully entered {value_effective} into {selector_effective}.")
                            if not self.is_crawler:
                                current_step = f"""text_editor_{formated_selector} = page.locator('iframe[title=\'Rich Text Area\\. Press ALT-0 for help\\.\']')
                                    .content_frame.locator('#tinymce') \n     text_editor_{formated_selector}.fill('{value_effective}')"""
                                send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.step, text_editor)
                            return f"Filled Editor element '{selector}'"
                        else:
                            print("Editor not found")
                    elif (tag_name =="fieldset" and label_input_class == "radio-w") or element_type == "radio" :
                            radio_button = self._fill_radio_button(page,selector,value_effective)
                            if  radio_button != None:
                                print(f"fieldset radio {value_effective}Cicking for {selector}")
                                #page.wait_for_timeout(500)
                                if radio_button.is_visible():
                                    highlight_element(page, radio_button.element_handle())
                                    radio_button.check()
                                    is_checked = radio_button.evaluate('(el) => el.checked')
                                    if is_checked:
                                        print(f"fieldset radio {value_effective} checked for {selector}")
                                        self.socket_handler.send_console_message(self.app_id, f"I've Successfully checked {value_effective} for {selector_effective}.")
                                        if not self.is_crawler:
                                            current_step = f"radio_button_{formated_selector}.check()"
                                            send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.step, radio_button)
                                        return f"fieldset radio element checked for '{selector}' with {value_effective}"
                                    else:
                                        print(f"fieldset radio {value_effective} not checked for {selector}")
                                        return f"fieldset radio element not checked for '{selector}' with {value_effective}"

                            else:
                                return f"No matching <legend> found for '{selector}'"

                    if element_type != "file":
                        if tag_name != "select" and label_input_role != "combobox" and 'MuiSelect' not in label_input_class:
                            #page.wait_for_timeout(500)
                            if label_input_element.is_visible():
                                highlight_element(page, label_input_element.element_handle())
                                label_input_element.fill(value_effective)
                                self.socket_handler.send_console_message(self.app_id, f"I've Successfully entered {value_effective} into {selector_effective}.")
                                if not self.is_crawler:
                                    current_step = f"label_input_element_{formated_selector}.fill('{value_effective}')"
                                    send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.step, label_input_element)
                                return f"Filled input element '{selector}'"
                            else:
                                print(f"input element not visible for {label_input_element}")
                        else:
                            print(f"Type of {selector} is file, Implementation is pending for file")
                            return f"Unable to fill file element '{selector}'"
                else:
                    other_radio = page.locator(f'text={value_effective}')
                    if other_radio.locator('input[type="radio"]').count() > 0:
                        other_radio.click()
                        print("Clicked the 'Other' radio button")
                        self.socket_handler.send_console_message(self.app_id, f"I've Successfully checked {value_effective} for {selector_effective}.")
                        return f"filled element'{selector}'"
                    else:
                        raise
                    # page.locator(f'text={value_effective}').click()
                    
            except Exception as e:
                self.socket_handler.send_console_message(self.app_id, f"I wasn't able to enter {value_effective} into {selector_effective}. Let's try again!")
                return f"Unable to fill element '{selector}'"
        return f"Filled element '{selector}'"
    
   
    def _get_label_element(self, page, selector):
        formated_selector = selector.replace(" ", "");
        print(f"_get_label_element : - Attempting to Get label: {selector}")
        element = None
        try:
            print(f"page.get_by_label 1 - {selector}")
            element = page.get_by_label(selector)
            print(f"element count {element.count}")
            element_count = element.count()  # Check how many elements match the label
            if element_count > 0:
                print(f"Element with label '{selector}' found!")
                if not self.is_crawler:
                    current_step = f"label_input_element_{formated_selector} = page.get_by_label('{selector}')"
                    # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.testcase_steps)
                return element
                # Interact with the element (e.g., fill it)
            else :                
                print(f"get_by_label exact -  Element with label '{selector}' not found.")
                print(f"page.get_by_label(selector,exact=True) 2 - {selector}")
                element =page.get_by_label(selector,exact=True)
                element_count = element.count() 
                if element_count > 0:
                    print(f"get_by_label - Element Count  {element_count} with label '{selector}' found!")
                    if not self.is_crawler:
                        current_step = f"label_input_element_{formated_selector} = page.get_by_label('{selector}',exact=True)"
                        # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.testcase_steps, self.testcase_step_index)
                    return element
                else:
                    print(f"page.get_by_placeholder 3 - {selector}")
                    element = page.get_by_placeholder(selector)
                    element_count = element.count() 
                    if element_count > 0:
                        print(f"get_by_placeholder 8888888 - Element for '{selector}' found!")
                        if not self.is_crawler:
                            current_step = f"label_input_element_{formated_selector} = page.get_by_placeholder('{selector}')"
                            # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.testcase_steps, self.testcase_step_index)
                        return element
                    else:
                        print(f"element not found pppppppppppp for selector {selector}")
                        return None
        except Exception as e3:
            print(f"_get_Input_element none for 5 {selector}", e3)
            return None

    
    def _fill_radio_button(self,page,selector,value_effective):
        print("I'm inside _fill_radio_button")
        formated_selector = selector.replace(" ", "");
        try:
            legend_radio_xpath = f"//label/span[translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz') = translate('{value_effective}', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')]/preceding-sibling::input[@type='radio']"
            # XPath to find the parent <legend> containing specific text
            legend_xpath = f"//legend[contains(text(), '{selector}')]"
            # Locate the radio button element
            personal_use_radio = page.locator(legend_radio_xpath)
            print("personal_use_radio is None",personal_use_radio is None)
            # Check if the radio button has a parent <legend> containing the expected text
            parent_legend = personal_use_radio.locator(f"xpath={legend_xpath}")
            print("parent_legend = ", parent_legend is None)
            if personal_use_radio.is_visible():  
                if not self.is_crawler:
                    current_step = f"radio_button_{formated_selector} = page.locator('{legend_radio_xpath}')"
                    # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.testcase_steps, self.testcase_step_index)
                return personal_use_radio
            else:
                print(f"parent_legend InputRadio  for label '{selector}' not found or not visible.")
                return None
        
        except Exception as ex:
            print(f"Exception in legend Radio button for {selector} - {ex}")
            return None

    def get_input_after_label(self, page, label_text):
        formated_selector = label_text.replace(" ", "");
        try:
            print("Find the label element by its text content")
            label_locator = page.locator(f"label:has-text('{label_text}')")
            label_locator.wait_for(timeout=5000)  # Wait up to 5 seconds for the label to appear
            
            if label_locator.is_visible():
                print(f"label_locator found '{label_text}'")
            else:
                print(f"label_locator '{label_text}' not found or not visible.")
                return None
            
            print("Get the input element that follows the label (next sibling or within the same container)")
            input_locator = label_locator.locator("xpath=following-sibling::div//input")
            
            input_locator.wait_for(timeout=500)  # Wait up to 5 seconds for the input to appear
            
            print("Optionally, check if input exists and is visible")
            # Optionally, check if input exists and is visible
            if input_locator.is_visible():
                if not self.is_crawler:
                    current_step = f"""label_locator_{formated_selector} = page.locator(f'label:has-text('{label_text}')')\n      
                        label_input_element_{formated_selector} = label_locator_{formated_selector}.locator('xpath=following-sibling::div//input')"""
                    # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.testcase_steps, self.testcase_step_index)
                return input_locator
            else:
                print(f"Input for label '{label_text}' not found or not visible.")
                return None

        except Exception as e:
            try:
                textarea_locator = label_locator.locator("xpath=following-sibling::div//textarea")
                
                textarea_locator.wait_for(timeout=500)  # Wait up to 5 seconds for the input to appear
                
                print("Optionally, check if textarea exists and is visible")
                # Optionally, check if input exists and is visible
                if textarea_locator.is_visible():
                    if not self.is_crawler:
                        current_step = f"""label_locator_{formated_selector} = page.locator(f'label:has-text('{label_text}')')\n      
                            label_input_element_{formated_selector} = label_locator_{formated_selector}.locator('xpath=following-sibling::div//textarea')"""
                        # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.testcase_steps, self.testcase_step_index)
                    return textarea_locator
                else:
                    print(f"Input for label '{label_text}' not found or not visible.")
                    return None
            except Exception as e2:
                print(f"Exception Input for label '{label_text}' not found or not visible.")
                return None

    # Helper function to fill by placeholder
    def _fill_by_placeholder(self, page, selector, value_effective):
        print(f"Attempting to fill by placeholder: {selector} value_effective {value_effective}")
        try:
           page.get_by_placeholder(selector).fill(value_effective)
           if not self.is_crawler:
                current_step = f"page.get_by_placeholder({selector}).fill({value_effective})"
                send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.step)
           return f"Filled element '{selector}'"
        except Exception as e:
            print(f"Attempting to fill by placeholder is failed : {selector} value_effective {value_effective}")
            return None
        

    # Helper function to fill by custom XPath
    def _fill_by_xpath(self, page, selector, value_effective):
        print(f"Attempting to fill by XPath: {selector} value_effective {value_effective}")
        try:
           xpath = f"//label[text()='{selector}']/ancestor::div[2]//input"
           page.fill(xpath, value_effective, strict=self.playwright_strict, timeout=self.playwright_timeout)
           return f"Filled element '{xpath}'"
        except Exception as e:
            print(f"Attempting to fill by XPath is Failed: {selector} value_effective {value_effective}")
        
    
    
    def check_element_by_text_exists(self, page, selector):
        print("check_element_by_text_exists called")
        try:
            print(f"Check for label by text '{selector}'")
            # Correct way to use f-string inside locator
            label = page.locator(f'label:has-text("{selector}")')
            label.wait_for(timeout=5000)  # Wait up to 5 seconds for the element
            if label.is_visible():
                print(f"Label with text '{selector}' is visible.")
                if not self.is_crawler:
                    current_step = f"page.locator(label:has-text('{selector}'))"
                    # send_post_action_screenshot(page, current_step, self.steps, self.socket_handler, self.step)
                return label
            else:
                print("Label not visible.")
                return None
            
        except Exception as e:
            print(f"Label not found Error: {e}")
            return None

    def _fill_combobox(self, page, selector, value_effective):
        print(f"Attempting to fill combobox: {selector} value_effective {value_effective} type is {type(selector)}" )
        try:
            print("before check_element_by_text_exists")
            element = self.check_element_by_text_exists(page,selector)
            print("element pass")
            if element is not None:
                element_class = element.get_attribute("class")
                print("element_class found" + element_class)
                role = self.getRole(element)
                print(f"Role: {role}, Element class: {element_class}")
                if role == "combobox" or 'MuiSelect' in element_class:
                    try:
                        element.click()
                    except Exception as e:
                        print(f"Combobox special case: {selector}, Exception: {e}")
                        page.get_by_label("", exact=True).click()
                
                #page.wait_for_timeout(500)  # Allow time for selection options
                page.get_by_role("option", name=value_effective).click()
                print(f"Selector option '{value_effective}' selected")
                return f"Filled combobox element '{selector}'"
        except Exception as e:
            print(f"Attempting to fill combobox is failed: {selector} value_effective {value_effective}")
       
    def getRole(self, element):
        role = ""
        try:
            role = element.get_attribute("role")
        except Exception as e:
            role = ""
        return role

    def camel_case_to_title(self, camel_case_str):
        words = re.sub(r'([a-z])([A-Z])', r'\1 \2', camel_case_str)
        return words.title()