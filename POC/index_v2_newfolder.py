import os
import json
import asyncio
from urllib.parse import urlparse, urljoin
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from crawl4ai import AsyncWebCrawler
from playwright.sync_api import sync_playwright

class AgnoBrowserCrawler:
    def __init__(self, url, section, sections, app_id, username="", password="", exclude_external_links=True):
        # Initialize crawler settings
        self.url = url  # Website URL to crawl
        self.section = section  # Primary CSS selector (e.g., 'forms')
        self.sections = sections  # List of additional sections (e.g., ['elements', 'forms', 'widgets'])
        self.app_id = app_id  # Application ID for naming screenshots
        self.username = username  # Optional login username
        self.password = password  # Optional login password
        self.screenshot_dir = "screenshots"  # Folder to save screenshots
        self.screenshot_paths = []  # List to store screenshot paths
        self.section_details = {}  # Dictionary to store section details
        self.playwright_instance = None  # Playwright instance for cleanup
        self.exclude_external_links = exclude_external_links  # Whether to exclude external links
        self.base_domain = self._extract_domain(url)  # Extract base domain for filtering
        self.allUrls = {}  # Dictionary to store all discovered URLs with visited status

        # Create screenshots folder if it doesn't exist
        if not os.path.exists(self.screenshot_dir):
            os.makedirs(self.screenshot_dir)
        
        # Create video output folder if it doesn't exist
        if not os.path.exists("video_output"):
            os.makedirs("video_output")

    def _extract_domain(self, url):
        """Extract the domain from a URL for filtering external links"""
        parsed_url = urlparse(url)
        return parsed_url.netloc

    def _is_same_domain(self, url):
        """Check if a URL belongs to the same domain as the base URL"""
        parsed_url = urlparse(url)
        return parsed_url.netloc == self.base_domain or not parsed_url.netloc

    def launch_browser(self):
        # Start Playwright and launch browser
        try:
            self.playwright_instance = sync_playwright().start()
            browser = self.playwright_instance.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={'width': 1460, 'height': 1080},
                record_video_dir="video_output",
                record_video_size={"width": 640, "height": 480}
            )
            page = context.new_page()

            # Navigate to the URL
            wait_options = ["networkidle", "domcontentloaded", "load", "commit"]
            for wait_type in wait_options:
                try:
                    print(f"Trying navigation with wait_until={wait_type}")
                    page.goto(self.url, wait_until=wait_type, timeout=30000)
                    print(f"Success with wait_until={wait_type}")
                    break
                except Exception as e:
                    print(f"Failed with wait_until={wait_type}: {e}")
            else:  # This will execute if the loop doesn't break
                # Final attempt without wait_until
                print("Trying navigation without wait_until")
                page.goto(self.url, timeout=30000)

            # Add initial URL to the allUrls dict
            self.allUrls[self.url] = {"isVisited": True}

            # Handle login if credentials are provided
            if self.username and self.password and self.username.strip() != "" and self.password.strip() != "":
                try:
                    self.handle_login(page)
                except Exception as e:
                    print(f"Login failed: {e}")

            return browser, context, page
        except Exception as e:
            print(f"Error launching browser: {e}")
            if self.playwright_instance:
                self.playwright_instance.stop()
            raise

    def handle_login(self, page):
        """Separate method for handling login (lines 224-232 in original code)"""
        # Find username field
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
            raise Exception("Could not find the username field")

        # Find password field
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

        # Find login button
        login_button_selector = None
        login_button_candidates = [
            'button[type="submit" i]',
            'button:has-text("login")',
            'button:has-text("sign in")',
            'button:has-text("log in")',
            'button:has-text("Login")',
            'button:has-text("Sign In")',
            'button:has-text("Log In")',
            'input[type="submit" i]',
            'a:has-text("login")',
            'a:has-text("sign in")',
        ]
        for selector in login_button_candidates:
            if page.query_selector(selector):
                login_button_selector = selector
                break
        if not login_button_selector:
            raise Exception("Could not find the login button")

        # Perform login
        page.fill(username_selector, self.username)
        page.fill(password_selector, self.password)
        page.click(login_button_selector)
        print("Login attempted")
        
        # Wait for navigation to complete after login
        wait_options = ["networkidle", "domcontentloaded", "load"]
        for wait_type in wait_options:
            try:
                page.wait_for_load_state(state=wait_type, timeout=10000)
                print(f"Post-login wait successful with {wait_type}")
                break
            except Exception as e:
                print(f"Failed waiting with {wait_type}: {e}")

    def create_agent(self):
        # Create an Agno agent for crawling
        return Agent(
            name="BrowserCrawler",
            model=OpenAIChat(id="gpt-4o"),
            role="Website Crawler",
            instructions=[
                "Visit the website and crawl specified sections.",
                "Extract navigational links using Crawl4AI.",
                "Navigate to each link, take screenshots, and save them locally.",
                "Handle popups by closing them if they block progress.",
                "Return screenshot paths and section details."
            ],
            debug_mode=True
        )

    def take_screenshot(self, page, name):
        # Save a screenshot with a unique name
        screenshot_path = os.path.join(self.screenshot_dir, f"{self.app_id}_{name}.png")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            self.screenshot_paths.append(screenshot_path)
            return screenshot_path
        except Exception as e:
            print(f"Error taking screenshot {name}: {e}")
            return None

    def close_popups(self, page):
        # Check for and close popups or modals
        try:
            # Common popup selectors
            popup_selectors = [
                'button.close', 
                '[aria-label="Close"]', 
                '[aria-label="Dismiss"]',
                '.modal-close',
                '.popup-close',
                '.dialog-close',
                '.close-button',
                'button:has-text("Close")',
                'button:has-text("Got it")',
                'button:has-text("Accept")',
                'button:has-text("I accept")',
                'button:has-text("Agree")',
                'button:has-text("OK")',
                '.cookie-banner button',
                '[id*="cookie"] button',
                '[class*="cookie"] button',
                '[id*="popup"] button',
                '[class*="popup"] button'
            ]
            
            for selector in popup_selectors:
                elements = page.query_selector_all(selector)
                for element in elements:
                    if element.is_visible():
                        print(f"Closing popup with selector: {selector}")
                        try:
                            element.click()
                            # Wait a bit for the popup to disappear
                            page.wait_for_timeout(1000)
                        except Exception as e:
                            print(f"Error clicking popup element: {e}")
        except Exception as e:
            print(f"Error handling popups: {e}")

    async def _extract_links_async(self, url):
        async with AsyncWebCrawler() as crawler:
            result = await crawler.run(url=url)
            links = []
            for link in result.extracted_links:
                if link.get("tag") in ["a", "li", "span"]:
                    href = link.get("href")
                    if href:
                        full_url = urljoin(url, href)
                        # Only add links from the same domain if exclude_external_links is True
                        if not self.exclude_external_links or self._is_same_domain(full_url):
                            links.append(full_url)
            return list(set(links))

    def extract_links(self, url):
        # Use Crawl4AI to extract links from the page
        try:
            # Run the async method in the event loop
            links = asyncio.run(self._extract_links_async(url))
            
            # Add all discovered links to the allUrls dictionary
            for link in links:
                if link not in self.allUrls:
                    self.allUrls[link] = {"isVisited": False}
                    
            return links
        except Exception as e:
            print(f"Error extracting links: {e}")
            return []

    def extract_page_links(self, page):
        """Extract all links from the current page and add to allUrls dict"""
        try:
            # Get all links from the page
            link_elements = page.query_selector_all('a[href]')
            links = []
            
            # Extract href attributes
            for element in link_elements:
                try:
                    href = element.get_attribute('href')
                    if href and not href.startswith('#') and not href.startswith('javascript:'):
                        full_url = urljoin(page.url, href)
                        # Only add links from the same domain if exclude_external_links is True
                        if not self.exclude_external_links or self._is_same_domain(full_url):
                            links.append(full_url)
                except Exception as e:
                    print(f"Error extracting href from element: {e}")
            
            # Add all discovered links to the allUrls dictionary
            for link in links:
                if link not in self.allUrls:
                    self.allUrls[link] = {"isVisited": False}
                    
            return links
        except Exception as e:
            print(f"Error extracting page links: {e}")
            return []

    def crawl_section(self, page, section_name):
        # Crawl a specific section
        print(f"Crawling section: {section_name}")
        self.close_popups(page)

        # Take screenshot of the section page
        screenshot_name = f"{section_name}_initial"
        screenshot_path = self.take_screenshot(page, screenshot_name)
        if screenshot_path:
            print(f"Screenshot saved: {screenshot_path}")

        # Save current URL to return to later
        current_url = page.url
        
        # Mark current URL as visited
        if current_url in self.allUrls:
            self.allUrls[current_url]["isVisited"] = True
        else:
            self.allUrls[current_url] = {"isVisited": True}
        
        # Extract links from the section using both methods
        links_from_crawl4ai = self.extract_links(current_url)
        links_from_page = self.extract_page_links(page)
        
        # Combine links from both methods
        links = list(set(links_from_crawl4ai + links_from_page))
        
        # Save section details
        self.section_details[current_url] = {
            "section": section_name, 
            "links": links
        }
        
        print(f"Found {len(links)} links in section {section_name}")

        # Navigate to each link that hasn't been visited
        for i, link in enumerate(links, 1):
            # Skip if this link has already been visited
            if link in self.allUrls and self.allUrls[link].get("isVisited", False):
                print(f"Skipping already visited link: {link}")
                continue
                
            try:
                print(f"Processing link {i}/{len(links)}: {link}")
                
                # Try clicking on element first
                clicked = False
                link_text = link.split('/')[-1]
                if link_text:  # Only try if there's text to match
                    selectors = [
                        f"a:has-text('{link_text}')",
                        f"li:has-text('{link_text}')",
                        f"span:has-text('{link_text}')"
                    ]
                    for selector in selectors:
                        try:
                            element = page.query_selector(selector)
                            if element and element.is_visible():
                                element.click()
                                page.wait_for_load_state("domcontentloaded", timeout=10000)
                                clicked = True
                                print(f"Clicked element with selector: {selector}")
                                break
                        except Exception as e:
                            print(f"Error clicking element with selector {selector}: {e}")
                
                # If clicking didn't work, navigate directly
                if not clicked:
                    print(f"Navigating directly to: {link}")
                    page.goto(link, timeout=30000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)

                # Mark link as visited
                self.allUrls[link]["isVisited"] = True
                
                # Handle any popups after navigation
                self.close_popups(page)
                
                # Extract links from this page too
                self.extract_page_links(page)
                
                # Take screenshot of the linked page
                screenshot_name = f"{section_name}_page_{i}"
                screenshot_path = self.take_screenshot(page, screenshot_name)
                if screenshot_path:
                    print(f"Screenshot saved: {screenshot_path}")

                # Save details about this link
                self.section_details[link] = {"section": section_name, "parent": current_url}
                
                # Return to the original page
                print(f"Returning to: {current_url}")
                page.goto(current_url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                
            except Exception as e:
                print(f"Error processing link {link}: {e}")
                try:
                    # Try to recover by returning to the original URL
                    page.goto(current_url, timeout=30000)
                except Exception as recovery_error:
                    print(f"Error recovering to original URL: {recovery_error}")

    def crawl_unvisited_urls(self, page):
        """Crawl any URLs in allUrls that haven't been visited yet"""
        unvisited_urls = [url for url, data in self.allUrls.items() if not data.get("isVisited", False)]
        print(f"Found {len(unvisited_urls)} unvisited URLs to crawl")
        
        for i, url in enumerate(unvisited_urls, 1):
            try:
                print(f"Crawling unvisited URL {i}/{len(unvisited_urls)}: {url}")
                
                # Navigate to the URL
                page.goto(url, timeout=30000)
                page.wait_for_load_state("domcontentloaded", timeout=10000)
                
                # Mark as visited
                self.allUrls[url]["isVisited"] = True
                
                # Handle popups
                self.close_popups(page)
                
                # Extract more links from this page
                self.extract_page_links(page)
                
                # Take screenshot
                screenshot_name = f"unvisited_url_{i}"
                screenshot_path = self.take_screenshot(page, screenshot_name)
                if screenshot_path:
                    print(f"Screenshot saved: {screenshot_path}")
                    
                # Record details
                self.section_details[url] = {"section": "unvisited", "discovered": True}
                
            except Exception as e:
                print(f"Error crawling unvisited URL {url}: {e}")

    def crawl(self):
        # Main crawling logic
        agent = self.create_agent()
        print(f"Starting crawl for {self.url}")

        try:
            browser, context, page = self.launch_browser()
            
            # Take a screenshot of the homepage
            self.take_screenshot(page, "homepage")
            
            # Crawl the primary section
            try:
                self.crawl_section(page, self.section)
            except Exception as e:
                print(f"Error crawling primary section: {e}")

            # Crawl additional sections
            for section in self.sections:
                if section == self.section:
                    # Skip if it's the same as the primary section
                    continue
                    
                try:
                    # Navigate to the section if it's a subpath or element
                    section_url = urljoin(self.url, section)
                    print(f"Navigating to section: {section_url}")
                    page.goto(section_url, timeout=30000)
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                    self.crawl_section(page, section)
                except Exception as e:
                    print(f"Error crawling section {section}: {e}")
            
            # Now process any unvisited URLs we discovered
            self.crawl_unvisited_urls(page)

            # Prepare final output
            output = {
                "screenshot_paths": self.screenshot_paths,
                "section_details": self.section_details,
                "all_urls": self.allUrls
            }
            
            # Save output to a JSON file
            output_file = f"{self.app_id}_crawl_results.json"
            with open(output_file, 'w') as f:
                json.dump(output, f, indent=2)
            print(f"Results saved to {output_file}")
            
            return output

        except Exception as e:
            print(f"Crawl failed: {e}")
            return {"error": str(e)}
            
        finally:
            # Clean up
            try:
                if 'context' in locals():
                    context.close()
                if 'browser' in locals():
                    browser.close()
                if self.playwright_instance:
                    self.playwright_instance.stop()
            except Exception as e:
                print(f"Error during cleanup: {e}")

# Example usage
if __name__ == "__main__":
    data = {
        'url': os.getenv("POC_START_URL", ""),
        'section': 'forms',
        'sections': ['elements', 'forms', 'widgets'],
        'app_id': os.getenv("POC_APP_ID", ""),
        'username': '',
        'password': '',
        'exclude_external_links': True
    }
    crawler = AgnoBrowserCrawler(
        url=data['url'],
        section=data['section'],
        sections=data['sections'],
        app_id=data['app_id'],
        username=data['username'],
        password=data['password'],
        exclude_external_links=data['exclude_external_links']
    )
    result = crawler.crawl()