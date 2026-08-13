from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

from tools.tools.goto import Goto
from tools.tools.click import ClickTool
from tools.tools.sequential_click import SequentialClickTool 
from tools.tools.fill import FillTool
from tools.tools.take_screenshot import TakeScreenshot
from tools.tools.get_elements import GetElementsTool
from tools.tools.extract_hyperlinks import ExtractHyperlinksTool
from tools.tools.extract_text import ExtractTextTool
from tools.tools.testcase_generator import TestCaseGenerator
from tools.tools.vision_tool import VisionTool
from tools.tools.document_generator import DocumentGenerator


@CrewBase
class CrawlAndGenerateDocumentsService:
    """
    A service class for crawling web content and generating documents using the Crew.ai framework.
    """
    
    def __init__(self, browser, tree, index, current_application_url, app_id) -> None:
        """
        Initializes the service with a browser instance and socket handler.
        Also configures tools for web crawling and document generation.

        Args:
            browser: The browser instance for automation.
            socket_handler: The socket handler for communication.
        """
        self.browser = browser
        self.tree = []  
        self.app_id = app_id  

        # Initialize tools
        try:
            self.goto_tool = Goto(app_id=app_id,is_crawler=True, sync_browser=self.browser)
            self.click_tool = ClickTool(tree=tree, sub_section=[], index=index, app_id=app_id, is_crawler=True, sync_browser=self.browser)
            self.sequential_click_tool = SequentialClickTool(tree=tree, sub_section=[], index=index, app_id=app_id,  is_crawler=True, sync_browser=self.browser)
            self.fill_tool = FillTool(app_id=app_id, is_crawler=True, sync_browser=self.browser)
            self.screenshot_tool = TakeScreenshot(app_id=app_id,  sync_browser=self.browser)
            self.element_tool = GetElementsTool(app_id=app_id,  sync_browser=self.browser)
            self.hyperlink_tool = ExtractHyperlinksTool(app_id=app_id,  sync_browser=self.browser)
            self.text_tool = ExtractTextTool(app_id=app_id,  sync_browser=self.browser)
            self.document_generator = DocumentGenerator(self.app_id, current_application_url)
            self.testcase_generator = TestCaseGenerator()
        except Exception as e:
            print(f"Error initializing tool: {e}")

    agents_config = 'config/agents.yaml'  # Path to agent configuration file
    tasks_config = 'config/tasks.yaml'  # Path to task configuration file


    @agent
    def crawler(self) -> Agent:
        """
        Defines the crawler agent for automating web browsing tasks.

        Returns:
            Agent: Configured agent for crawling.
        """
        return Agent(
            config=self.agents_config['crawler'],
            tools=[
                self.goto_tool,
                self.element_tool,
                self.click_tool,
                self.sequential_click_tool,
                self.fill_tool,
                self.screenshot_tool
            ],
            verbose=True
        )

    @agent
    def document_creator(self) -> Agent:
        """
        Defines the document creator agent for generating structured documents.

        Returns:
            Agent: Configured agent for document creation.
        """
        return Agent(
            config=self.agents_config['document_creator'],
            verbose=True
        )

    @task
    def crawler_task(self) -> Task:
        """
        Defines the crawler task that uses tools to gather web content and logs the results.

        Returns:
            Task: Configured task for web crawling.
        """
        return Task(
            config=self.tasks_config['crawler_task'],
            tools=[
                self.goto_tool,
                self.click_tool,
                self.sequential_click_tool,
                self.fill_tool,
                self.screenshot_tool,
                self.element_tool,
            ],
            output_pydantic=CrawlerResponseModel
        )

    @task
    def document_creator_task(self) -> Task:
        """
        Defines the document creation task that generates structured documents.

        Returns:
            Task: Configured task for document generation.
        """
        return Task(
            config=self.tasks_config['document_creator_task'],
            tools=[self.document_generator],
            output_pydantic=DocumentResponseModel
        )
    
    def step_callback_with_token_usage(self, step_output):
        print(f"Step completed: {step_output}")
        # Assuming there's a way to access token usage per step
        # print(f"Tokens used in this step: {step_output.tokens_used}")

    @crew
    def create_crew(self) -> Crew:
        """
        Creates the crew for managing agents and tasks in a sequential process.

        Returns:
            Crew: Configured crew for managing execution.
        """
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
            step_callback=self.step_callback_with_token_usage
        )

############# helper classes for browser instance:

########## CrawlerResponseModel

from pydantic import BaseModel
from typing import List, Optional, Union

class SubSectionModel(BaseModel):
    """
    A model that represents a subsection in a section.
    It supports recursion to allow nested subsections.
    """
    section_id: str
    name: str
    subsection: Union[List['SubSectionModel'], List[Optional[dict]]]  # Recursive definition with optional dictionaries

class SectionModel(BaseModel):
    """
    A model that represents a section, containing a list of subsections.
    """
    section: str
    sub_section: List[SubSectionModel]  # List of SubSectionModel instances

class CrawlerResponseModel(BaseModel):
    """
    The main model containing the images paths and the sections.
    It validates a list of image paths and a single section structure.
    """
    images_paths: List[str]  # List of image paths
    sections: SectionModel  # The main section containing subsections


###### DocumentResponseModel

from pydantic import BaseModel

class DocumentResponseModel(BaseModel):
    """
    A model representing the response that contains information 
    about the directory where the document has been saved or processed.

    Attributes:
        directory (str): The directory path where the document is stored.
    """
    directory: str  # The directory path of the document
	


from playwright.sync_api import sync_playwright

class BrowserService:
		
	def launch_browser(self, login_url, username, password, application_id):  
		playwright_instance = None
		try:
			if playwright_instance is None:
				playwright_instance = sync_playwright().start()  # Start Playwright without `async with`     
			browser = playwright_instance.chromium.launch(headless=False)
			context = browser.new_context(viewport={'width': 1460, 'height': 1080}, record_video_dir = "video_output", record_video_size={"width": 640, "height": 480})
			page = context.new_page() 
			wait_options = ["networkidle", "domcontentloaded", "load", "commit"]
			for wait_type in wait_options:
				try:
					print(f"Trying with wait_until={wait_type}")
					page.goto(login_url, wait_until=wait_type)
					print(f"Success with wait_until={wait_type}")
					break 
				except Exception as e:
					print(f"Failed with wait_until={wait_type}: {e}")
					print(f"Navigated to {login_url}")
			if username and password and username.strip() != "" and password.strip() != "":
				username_selector = None
				username_candidates = [
					'input[placeholder*="username" i]',
					'input[placeholder*="email" i]',
					'input[name*="username" i]',
					'input[name*="email" i]',
					'input[id*="username" i]',
					'input[id*="email" i]',
					'input[type="email" i]',
				]
				for selector in username_candidates:
					if page.query_selector(selector):
						username_selector = selector
						break

				if not username_selector:
					page_content = page.content()
					print("Page content:", page_content)
					raise Exception("Could not find the username field")

				print("Found the username field")
				
				password_selector = None
				password_candidates = [
					'input[placeholder*="password" i]',
					'input[placeholder="Password" i]',
					'input[name*="password" i]',
					'input[id*="password" i]',
					'input[type="password" i]'
				]
				for selector in password_candidates:
					if page.query_selector(selector):
						password_selector = selector
						break
				
				if not password_selector:
					raise Exception("Could not find the password field")

				# Fill in the username and password
				page.fill(username_selector, username)
				page.fill(password_selector, password)
				print("Filled in username and password")
				
				# Step 3: Find the login button
				login_button_selector = None
				login_button_candidates = [
					'button[type="submit" i]',
					'input[type="submit" i]',
					'button:has-text("login")',
					'button:has-text("sign in")',
					'button:has-text("log in")',
					'input[value*="login" i]',
					'input[value*="sign in" i]',
					'input[value*="log in" i]',
					'button:has-text("Login")',
					'button:has-text("Sign In")',
					'button:has-text("SIGN IN")',
					'button:has-text("Log In")',
					'span:has-text("Sign In")',
					'button:has-text("SIGN IN")',
				]
				for selector in login_button_candidates:
					if page.query_selector(selector):
						login_button_selector = selector
						break
				
				if not login_button_selector:
					raise Exception("Could not find the login button")
				
				# Step 4: Click the login button
				page.click(login_button_selector)
				print("Clicked the login button")
				for wait_type in wait_options:
					try:
						page.wait_for_load_state(state=wait_type)
						break 
					except Exception as e:
						print(f"Failed with wait_until={wait_type}: {e}")
				return browser, context, page.url
			else:
				return browser, context, page.url
		except Exception as e:
			print(f"An error occurred: {e}")
			raise 
		

############ How to trigger the scanning :
browser, context, start_url = BrowserService().launch_browser(
            login_url=os.getenv("POC_START_URL", ""),
            username="",
            password ="",
            application_id=os.getenv("POC_APP_ID", "")
        )
data = {'url': os.getenv("POC_START_URL", ""), 'section': os.getenv("POC_SECTION", ""), 'sections': []}

result = CrawlAndGenerateDocumentsService(browser=browser, tree= [], index=0, current_application_url=os.getenv("POC_START_URL", ""), app_id=os.getenv("POC_APP_ID", "")).create_crew().kickoff(data)


