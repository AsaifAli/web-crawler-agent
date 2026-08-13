import os
import json
import asyncio
import logging
import time
import base64
from urllib.parse import urlparse, urljoin
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from crawl4ai import AsyncWebCrawler
from playwright.sync_api import sync_playwright
import google.generativeai as genai
import markdown2
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AgnoBrowserCrawler:
    def __init__(self, url, section, sections, app_id, username="", password="", exclude_external_links=True, gemini_api_key=""):
        self.url = url
        self.section = section
        self.sections = sections
        self.app_id = app_id
        self.username = username
        self.password = password
        self.screenshot_dir = "screenshots"
        self.screenshot_paths = []
        self.section_details = {}
        self.playwright_instance = None
        self.exclude_external_links = exclude_external_links
        self.base_domain = self._extract_domain(url)
        self.allUrls = {}
        self.summaries = {}
        self.gemini_api_key = gemini_api_key
        self.loop = None

        # Initialize Gemini API
        if self.gemini_api_key:
            genai.configure(api_key=self.gemini_api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            logger.warning("Gemini API key not provided. Summarization and vision-based extraction will be skipped.")

        # Create directories
        for directory in [self.screenshot_dir, "video_output", "reports"]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def _extract_domain(self, url):
        parsed_url = urlparse(url)
        return parsed_url.netloc

    def _is_same_domain(self, url):
        parsed_url = urlparse(url)
        return parsed_url.netloc == self.base_domain or not parsed_url.netloc

    def launch_browser(self):
        try:
            self.playwright_instance = sync_playwright().start()
            browser = self.playwright_instance.chromium.launch(headless=False)
            context = browser.new_context(
                viewport={'width': 1460, 'height': 1080},
                record_video_dir="video_output",
                record_video_size={"width": 640, "height": 480}
            )
            page = context.new_page()
            wait_options = ["networkidle", "domcontentloaded", "load", "commit"]
            for wait_type in wait_options:
                try:
                    logger.info(f"Trying navigation with wait_until={wait_type}")
                    page.goto(self.url, wait_until=wait_type, timeout=30000)
                    logger.info(f"Success with wait_until={wait_type}")
                    break
                except Exception as e:
                    logger.warning(f"Failed with wait_until={wait_type}: {e}")
            else:
                logger.info("Trying navigation without wait_until")
                page.goto(self.url, timeout=30000)
            self.allUrls[self.url] = {"isVisited": True}
            if self.username and self.password and self.username.strip() != "" and self.password.strip() != "":
                try:
                    self.handle_login(page)
                except Exception as e:
                    logger.error(f"Login failed: {e}")
            return browser, context, page
        except Exception as e:
            logger.error(f"Error launching browser: {e}")
            if self.playwright_instance:
                self.playwright_instance.stop()
            raise

    def handle_login(self, page):
        username_selector = None
        username_candidates = [
            'input[placeholder*="username" i]', 'input[placeholder*="email" i]',
            'input[name*="username" i]', 'input[name*="email" i]',
            'input[id*="username" i]', 'input[id*="email" i]',
            'input[type="email" i]',
        ]
        for selector in username_candidates:
            if page.query_selector(selector):
                username_selector = selector
                break
        if not username_selector:
            raise Exception("Could not find the username field")
        password_selector = None
        password_candidates = [
            'input[placeholder*="password" i]', 'input[placeholder="Password" i]',
            'input[name*="password" i]', 'input[id*="password" i]',
            'input[type="password" i]'
        ]
        for selector in password_candidates:
            if page.query_selector(selector):
                password_selector = selector
                break
        if not password_selector:
            raise Exception("Could not find the password field")
        login_button_selector = None
        login_button_candidates = [
            'button[type="submit" i]', 'button:text("login")',
            'button:text("sign in")', 'button:text("log in")',
            'button:text("Login")', 'button:text("Sign In")',
            'button:text("Log In")', 'input[type="submit" i]',
            'a:text("login")', 'a:text("sign in")',
        ]
        for selector in login_button_candidates:
            if page.query_selector(selector):
                login_button_selector = selector
                break
        if not login_button_selector:
            raise Exception("Could not find the login button")
        page.fill(username_selector, self.username)
        page.fill(password_selector, self.password)
        page.click(login_button_selector)
        logger.info("Login attempted")
        wait_options = ["networkidle", "domcontentloaded", "load"]
        for wait_type in wait_options:
            try:
                page.wait_for_load_state(state=wait_type, timeout=10000)
                logger.info(f"Post-login wait successful with {wait_type}")
                break
            except Exception as e:
                logger.warning(f"Failed waiting with {wait_type}: {e}")

    def create_agent(self):
        return Agent(
            name="BrowserCrawler",
            model=OpenAIChat(id="gpt-4o"),
            role="Website Crawler",
            instructions=[
                "Dynamically crawl website to discover links, sections, sub-sections, and forms.",
                "Extract navigational links, interactive elements, and sub-elements using Crawl4AI and Playwright.",
                "Navigate to each link, take screenshots, and save them locally.",
                "Extract text content from DOM and screenshots for summarization.",
                "Handle popups by closing them if they block progress.",
                "Detect single-page application routes and dynamic content."
            ],
            debug_mode=True
        )

    def take_screenshot(self, page, name):
        screenshot_path = os.path.join(self.screenshot_dir, f"{self.app_id}_{name}.png")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            self.screenshot_paths.append(screenshot_path)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Error taking screenshot {name}: {e}")
            return None

    def click_with_retry(self, page, selector, max_retries=3):
        bounding_box = None
        for attempt in range(max_retries):
            try:
                element = page.query_selector(selector)
                if not element:
                    logger.warning(f"Element not found for selector: {selector}")
                    return False
                page.evaluate(f"""(selector) => {{
                    const element = document.querySelector(selector);
                    if (element) {{
                        element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                    }}
                }}""", selector)
                page.wait_for_timeout(500)
                bounding_box = element.bounding_box()
                if bounding_box:
                    viewport = page.viewport_size
                    if (bounding_box['x'] < 0 or bounding_box['y'] < 0 or
                            bounding_box['x'] + bounding_box['width'] > viewport['width'] or
                            bounding_box['y'] + bounding_box['height'] > viewport['height']):
                        logger.warning(f"Element {selector} is outside viewport")
                        page.evaluate(f"""(selector) => {{
                            const element = document.querySelector(selector);
                            if (element) element.click();
                        }}""", selector)
                        return True
                element.click(timeout=5000)
                return True
            except Exception as e:
                logger.warning(f"Click attempt {attempt+1} failed for {selector}: {e}")
                if attempt == max_retries - 1:
                    if bounding_box:
                        try:
                            x = bounding_box['x'] + bounding_box['width'] / 2
                            y = bounding_box['y'] + bounding_box['height'] / 2
                            page.mouse.click(x, y)
                            logger.info(f"Mouse click fallback succeeded for {selector}")
                            return True
                        except Exception as mouse_error:
                            logger.error(f"Mouse click fallback failed for {selector}: {mouse_error}")
                    return False
                page.wait_for_timeout(1000)
        return False

    def close_popups(self, page):
        popup_selectors = [
            'button.close', '[aria-label="Close"]', '[aria-label="Dismiss"]',
            '.modal-close', '.popup-close', '.dialog-close', '.close-button',
            'button:text("Close")', 'button:text("Got it")',
            'button:text("Accept")', 'button:text("I accept")',
            'button:text(" Agree")', 'button:text("OK")',
            '.cookie-banner button', '[id*="cookie"] button',
            '[class*="cookie"] button', '[id*="popup"] button',
            '[class*="popup"] button'
        ]
        for selector in popup_selectors:
            elements = page.query_selector_all(selector)
            for element in elements:
                if element.is_visible():
                    logger.info(f"Closing popup with selector: {selector}")
                    try:
                        page.evaluate("""(element) => {
                            element.scrollIntoView({behavior: 'smooth', block: 'center'});
                        }""", element)
                        page.wait_for_timeout(500)
                        if self.click_with_retry(page, selector):
                            page.wait_for_timeout(1000)
                        else:
                            logger.warning(f"Failed to close popup with selector: {selector}")
                    except Exception as e:
                        logger.error(f"Error closing popup with selector {selector}: {e}")

    async def _extract_links_async(self, url):
        async with AsyncWebCrawler() as crawler:
            try:
                # Use 'run' per Crawl4AI 0.6.2 documentation
                result = await crawler.run(url=url, wait_for=5000)
                links = []
                for link in result.extracted_links:
                    if link.get("tag") in ["a", "li", "span", "button"]:
                        href = link.get("href")
                        if href:
                            full_url = urljoin(url, href)
                            if not self.exclude_external_links or self._is_same_domain(full_url):
                                links.append(full_url)
                return list(set(links))
            except Exception as e:
                logger.error(f"Error extracting links from {url}: {e}")
                return []

    def extract_links(self, url):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self._extract_links_async(url), loop)
                links = future.result(timeout=30)
            else:
                links = loop.run_until_complete(self._extract_links_async(url))
            for link in links:
                if link not in self.allUrls:
                    self.allUrls[link] = {"isVisited": False}
            return links
        except Exception as e:
            logger.error(f"Error extracting links for {url}: {e}")
            return []
        finally:
            if self.loop and not self.loop.is_running():
                self.loop.close()
                self.loop = None

    def extract_page_links(self, page):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            link_elements = page.query_selector_all('a[href], [onclick], [data-href], [data-url], [role="link"], button:not([type="submit"]), [data-action]')
            links = []
            for element in link_elements:
                try:
                    href = (element.get_attribute('href') or
                            element.get_attribute('data-href') or
                            element.get_attribute('data-url'))
                    if href and not href.startswith('#') and not href.startswith('javascript:'):
                        full_url = urljoin(page.url, href)
                        if not self.exclude_external_links or self._is_same_domain(full_url):
                            links.append(full_url)
                    if element.is_visible() and href:
                        original_url = page.url
                        selector = f'[href="{href}"], [data-href="{href}"], [data-url="{href}"], [onclick], [role="link"]'
                        if self.click_with_retry(page, selector, max_retries=1):
                            page.wait_for_timeout(1000)
                            if page.url != original_url:
                                full_url = page.url
                                if not self.exclude_external_links or self._is_same_domain(full_url):
                                    links.append(full_url)
                            page.goto(original_url, timeout=10000)
                except Exception as e:
                    logger.error(f"Error extracting href from element: {e}")
            for link in links:
                if link not in self.allUrls:
                    self.allUrls[link] = {"isVisited": False}
            return list(set(links))
        except Exception as e:
            logger.error(f"Error extracting page links: {e}")
            return []

    def extract_sections(self, page):
        try:
            section_elements = page.query_selector_all('section, nav, article, div[class*="section"], div[id*="section"], main, aside, header, footer')
            sections = []
            for i, element in enumerate(section_elements):
                try:
                    section_id = element.evaluate("""(el) => {
                        return el.id || el.className || 'section_' + Math.random().toString(36).substr(2, 9);
                    }""")
                    text = element.evaluate("""(el) => {
                        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                        let text = '';
                        while (node = walker.nextNode()) {
                            text += node.textContent.trim() + ' ';
                        }
                        return text;
                    }""")
                    text = ' '.join(text.split())[:50]
                    sections.append({
                        "identifier": section_id,
                        "text_snippet": text,
                        "element_index": i
                    })
                except Exception as e:
                    logger.error(f"Error extracting section {i}: {e}")
            return sections
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            return []

    def extract_forms(self, page):
        try:
            form_elements = page.query_selector_all('form')
            forms = []
            for i, form in enumerate(form_elements):
                try:
                    form_id = form.evaluate("""(el) => el.id || 'form_' + Math.random().toString(36).substr(2, 9)""")
                    action = form.get_attribute('action') or "N/A"
                    method = form.get_attribute('method') or "N/A"
                    inputs = []
                    input_elements = form.query_selector_all('input, textarea, select')
                    for input_el in input_elements:
                        input_type = input_el.get_attribute('type') or input_el.evaluate("""(el) => el.tagName.toLowerCase()""")
                        input_name = input_el.get_attribute('name') or "N/A"
                        input_id = input_el.get_attribute('id') or "N/A"
                        inputs.append({
                            "type": input_type,
                            "name": input_name,
                            "id": input_id
                        })
                    forms.append({
                        "id": form_id,
                        "action": action,
                        "method": method,
                        "inputs": inputs
                    })
                except Exception as e:
                    logger.error(f"Error extracting form {i}: {e}")
            return forms
        except Exception as e:
            logger.error(f"Error extracting forms: {e}")
            return []

    def extract_page_content(self, page):
        try:
            page.evaluate("""() => {
                window.scrollTo(0, document.body.scrollHeight);
            }""")
            page.wait_for_timeout(1000)
            content = page.evaluate("""() => {
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    {
                        acceptNode: (node) => {
                            const style = window.getComputedStyle(node.parentElement);
                            return (style.display !== 'none' && style.visibility !== 'hidden')
                                ? NodeFilter.FILTER_ACCEPT
                                : NodeFilter.FILTER_REJECT;
                        }
                    }
                );
                let text = '';
                while (node = walker.nextNode()) {
                    text += node.textContent.trim() + ' ';
                }
                return text;
            }""")
            content = ' '.join(content.split())
            return content[:10000]
        except Exception as e:
            logger.error(f"Error extracting page content: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def extract_text_from_screenshot(self, screenshot_path, url):
        if not self.gemini_api_key or not os.path.exists(screenshot_path):
            logger.warning(f"Vision-based text extraction skipped for {url}: Missing API key or screenshot")
            return ""
        try:
            with open(screenshot_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            prompt = "Extract all visible text from this webpage screenshot."
            response = self.gemini_model.generate_content([
                {"mime_type": "image/png", "data": image_data},
                {"text": prompt}
            ])
            text = response.text.strip()
            logger.info(f"Vision-based text extracted from {screenshot_path}: {len(text)} characters")
            return text
        except Exception as e:
            logger.error(f"Error extracting text from screenshot {screenshot_path}: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def summarize_content(self, content, vision_text, url):
        if not self.gemini_api_key or (not content and not vision_text):
            return "Summary not generated: Missing API key or content."
        try:
            combined_content = f"DOM Content: {content}\nVision-Extracted Text: {vision_text}"
            prompt = f"Summarize the following webpage content in 2-3 sentences, focusing on the main purpose and key information. Content: {combined_content[:10000]}"
            response = self.gemini_model.generate_content(prompt)
            summary = response.text.strip()
            return summary
        except Exception as e:
            logger.error(f"Error generating summary for {url}: {e}")
            return f"Failed to generate summary for {url}."

    def crawl_section(self, page, section_name, depth=0, max_depth=2):
        if depth > max_depth:
            logger.info(f"Max depth {max_depth} reached for section {section_name}")
            return
        logger.info(f"Crawling section: {section_name} (Depth: {depth})")
        self.close_popups(page)
        screenshot_name = f"{section_name}_initial_{depth}"
        screenshot_path = self.take_screenshot(page, screenshot_name)
        current_url = page.url
        if current_url in self.allUrls:
            self.allUrls[current_url]["isVisited"] = True
        else:
            self.allUrls[current_url] = {"isVisited": True}
        content = self.extract_page_content(page)
        vision_text = self.extract_text_from_screenshot(screenshot_path, current_url) if screenshot_path else ""
        summary = self.summarize_content(content, vision_text, current_url)
        self.summaries[current_url] = summary
        sections = self.extract_sections(page)
        forms = self.extract_forms(page)
        links_from_crawl4ai = self.extract_links(current_url)
        links_from_page = self.extract_page_links(page)
        links = list(set(links_from_crawl4ai + links_from_page))
        self.section_details[current_url] = {
            "section": section_name,
            "links": links,
            "sections": sections,
            "forms": forms,
            "summary": summary,
            "screenshot": screenshot_path,
            "vision_text": vision_text,
            "depth": depth
        }
        logger.info(f"Found {len(links)} links, {len(sections)} sections, {len(forms)} forms in section {section_name}")
        for i, link in enumerate(links, 1):
            if link in self.allUrls and self.allUrls[link].get("isVisited", False):
                logger.info(f"Skipping already visited link: {link}")
                continue
            try:
                logger.info(f"Processing link {i}/{len(links)}: {link}")
                clicked = False
                link_text = link.split('/')[-1] or link
                selectors = [
                    f'text="{link_text}"',
                    f'a[href*="{link_text}"]',
                    f'[data-href*="{link_text}"]',
                    f'[data-url*="{link_text}"]',
                    f'a[href="{link}"]',
                    'text="App Builder"',
                    'text="Features"',
                    'text="Pricing"',
                    'text="Blog"',
                    'text="Sign In"',
                    'text="Contact"'
                ]
                for selector in selectors:
                    try:
                        if self.click_with_retry(page, selector):
                            page.wait_for_load_state("domcontentloaded", timeout=10000)
                            clicked = True
                            logger.info(f"Clicked element with selector: {selector}")
                            break
                    except Exception as e:
                        logger.warning(f"Error clicking element with selector {selector}: {e}")
                if not clicked:
                    logger.info(f"Navigating directly to: {link}")
                    page.goto(link, timeout=30000)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception as wait_error:
                        logger.warning(f"Error waiting for load state: {wait_error}")
                self.allUrls[link]["isVisited"] = True
                self.close_popups(page)
                content = self.extract_page_content(page)
                screenshot_name = f"{section_name}_page_{i}_{depth}"
                screenshot_path = self.take_screenshot(page, screenshot_name)
                vision_text = self.extract_text_from_screenshot(screenshot_path, link) if screenshot_path else ""
                summary = self.summarize_content(content, vision_text, link)
                self.summaries[link] = summary
                sections = self.extract_sections(page)
                forms = self.extract_forms(page)
                self.extract_page_links(page)
                self.section_details[link] = {
                    "section": section_name,
                    "parent": current_url,
                    "sections": sections,
                    "forms": forms,
                    "summary": summary,
                    "screenshot": screenshot_path,
                    "vision_text": vision_text,
                    "depth": depth + 1
                }
                self.crawl_section(page, section_name, depth=depth + 1, max_depth=max_depth)
                logger.info(f"Returning to: {current_url}")
                try:
                    page.goto(current_url, timeout=30000)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception as wait_error:
                        logger.warning(f"Error waiting for load state after return: {wait_error}")
                except Exception as nav_error:
                    logger.warning(f"Error returning to original URL: {nav_error}")
                    try:
                        page.goto(current_url, wait_until="commit", timeout=30000)
                    except Exception as retry_error:
                        logger.error(f"Second attempt to return also failed: {retry_error}")
            except Exception as e:
                logger.error(f"Error processing link {link}: {e}")
                try:
                    page.goto(current_url, timeout=30000)
                except Exception as recovery_error:
                    logger.error(f"Error recovering to original URL: {recovery_error}")

    def crawl_unvisited_urls(self, page):
        unvisited_urls = [url for url, data in self.allUrls.items() if not data.get("isVisited", False)]
        logger.info(f"Found {len(unvisited_urls)} unvisited URLs to crawl")
        for i, url in enumerate(unvisited_urls, 1):
            try:
                logger.info(f"Crawling unvisited URL {i}/{len(unvisited_urls)}: {url}")
                page.goto(url, timeout=30000)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception as wait_error:
                    logger.warning(f"Error waiting for load state: {wait_error}")
                self.allUrls[url]["isVisited"] = True
                self.close_popups(page)
                content = self.extract_page_content(page)
                screenshot_name = f"unvisited_url_{i}"
                screenshot_path = self.take_screenshot(page, screenshot_name)
                vision_text = self.extract_text_from_screenshot(screenshot_path, url) if screenshot_path else ""
                summary = self.summarize_content(content, vision_text, url)
                self.summaries[url] = summary
                sections = self.extract_sections(page)
                forms = self.extract_forms(page)
                self.extract_page_links(page)
                self.section_details[url] = {
                    "section": "unvisited",
                    "discovered": True,
                    "sections": sections,
                    "forms": forms,
                    "summary": summary,
                    "screenshot": screenshot_path,
                    "vision_text": vision_text
                }
            except Exception as e:
                logger.error(f"Error crawling unvisited URL {url}: {e}")
                self.allUrls[url]["isVisited"] = True

    def crawl_additional_sections(self, page):
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            nav_selectors = [
                'nav a[href]', '.menu a[href]', '.navbar a[href]', '.sidebar a[href]',
                'header a[href]', 'footer a[href]', '*[role="navigation"] a[href]',
                'ul a[href]', 'li a[href]', 'a:not([href^="#"]):not([href^="javascript:"])',
                'a:text("App Builder")', 'a:text("Features")', 'a:text("Pricing")', 'a:text("Blog")',
                'a:text("Sign In")', 'a:text("Contact")'
            ]
            section_urls = []
            for selector in nav_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    for element in elements:
                        try:
                            href = element.get_attribute('href')
                            if href and not href.startswith('#') and not href.startswith('javascript:'):
                                full_url = urljoin(self.url, href)
                                if not self.exclude_external_links or self._is_same_domain(full_url):
                                    section_urls.append(full_url)
                            if element.is_visible():
                                original_url = page.url
                                if self.click_with_retry(page, selector, max_retries=1):
                                    page.wait_for_timeout(1000)
                                    if page.url != original_url:
                                        full_url = page.url
                                        if not self.exclude_external_links or self._is_same_domain(full_url):
                                            section_urls.append(full_url)
                                    page.goto(original_url, timeout=10000)
                        except Exception as e:
                            logger.error(f"Error extracting nav link with selector {selector}: {e}")
                except Exception as e:
                    logger.error(f"Error querying selector {selector}: {e}")
            section_urls = list(set(section_urls))
            logger.info(f"Discovered {len(section_urls)} potential section URLs: {section_urls}")
            for i, section_url in enumerate(section_urls, 1):
                if section_url in self.allUrls and self.allUrls[section_url].get("isVisited", False):
                    logger.info(f"Skipping already visited section: {section_url}")
                    continue
                try:
                    section_name = f"section_{i}"
                    logger.info(f"Navigating to section: {section_url}")
                    page.goto(section_url, timeout=30000)
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=10000)
                    except Exception as wait_error:
                        logger.warning(f"Error waiting for load state in section {section_name}: {wait_error}")
                    self.crawl_section(page, section_name)
                except Exception as e:
                    logger.error(f"Error crawling section {section_url}: {e}")
        except Exception as e:
            logger.error(f"Error discovering additional sections: {e}")

    def generate_report(self):
        report_content = f"# Crawler Report for {self.url}\n\n"
        report_content += f"**Generated on**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        report_content += f"**Application ID**: {self.app_id}\n\n"
        report_content += "## Summary of Findings\n\n"
        for url, details in self.section_details.items():
            report_content += f"### URL: {url}\n"
            report_content += f"- **Section**: {details.get('section', 'N/A')}\n"
            report_content += f"- **Depth**: {details.get('depth', 0)}\n"
            if 'parent' in details:
                report_content += f"- **Parent URL**: {details['parent']}\n"
            if 'summary' in details:
                report_content += f"- **Summary**: {details['summary']}\n"
            if 'vision_text' in details and details['vision_text']:
                report_content += f"- **Vision-Extracted Text**: {details['vision_text'][:200]}...\n"
            if 'screenshot' in details and details['screenshot']:
                report_content += f"- **Screenshot**: ![{url}]({details['screenshot']})\n"
            if 'sections' in details and details['sections']:
                report_content += f"- **Sections Found** ({len(details['sections'])}):\n"
                for section in details['sections']:
                    report_content += f"  - {section['identifier']}: {section['text_snippet']}\n"
            if 'forms' in details and details['forms']:
                report_content += f"- **Forms Found** ({len(details['forms'])}):\n"
                for form in details['forms']:
                    report_content += f"  - Form ID: {form['id']}, Action: {form['action']}, Method: {form['method']}\n"
                    for input_field in form['inputs']:
                        report_content += f"    - Input: {input_field['type']}, Name: {input_field['name']}, ID: {input_field['id']}\n"
            report_content += "\n"
        report_path = os.path.join("reports", f"{self.app_id}_crawler_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        html_content = markdown2.markdown(report_content)
        html_path = os.path.join("reports", f"{self.app_id}_crawler_report.html")
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(f"""
<!DOCTYPE html>
<html>
<head>
    <title>Crawler Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
""")
        return report_path, html_path

    def crawl(self):
        browser = None
        context = None
        try:
            browser, context, page = self.launch_browser()
            page.on("pageerror", lambda err: logger.error(f"Page error: {err}"))
            page.on("crash", lambda: logger.error("Page crashed"))
            page.set_default_timeout(30000)
            self.crawl_section(page, "main")
            self.crawl_additional_sections(page)
            self.crawl_unvisited_urls(page)
            report_path, html_path = self.generate_report()
            return {
                "screenshot_paths": self.screenshot_paths,
                "section_details": self.section_details,
                "all_urls": self.allUrls,
                "summaries": self.summaries,
                "report_path": report_path,
                "html_report_path": html_path
            }
        except Exception as e:
            logger.error(f"Error during crawling: {e}", exc_info=True)
            raise
        finally:
            try:
                if context:
                    context.close()
                if browser:
                    browser.close()
                if self.playwright_instance:
                    self.playwright_instance.stop()
            except Exception as close_error:
                logger.error(f"Error closing browser resources: {close_error}")
            if self.loop and not self.loop.is_running():
                try:
                    self.loop.close()
                    self.loop = None
                except Exception as loop_error:
                    logger.error(f"Error closing event loop: {loop_error}")

if __name__ == "__main__":
    data = {
        'url': os.getenv("POC_START_URL", ""),
        'section': 'main',
        'sections': [],
        'app_id': os.getenv("POC_APP_ID", ""),
        'username': '',
        'password': '',
        'exclude_external_links': True,
        'gemini_api_key': os.getenv("GEMINI_API_KEY", "")
    }
    crawler = AgnoBrowserCrawler(
        url=data['url'],
        section=data['section'],
        sections=data['sections'],
        app_id=data['app_id'],
        username=data['username'],
        password=data['password'],
        exclude_external_links=data['exclude_external_links'],
        gemini_api_key=data['gemini_api_key']
    )
    try:
        result = crawler.crawl()
        logger.info("Crawling completed successfully!")
        logger.info(f"Screenshots taken: {len(result['screenshot_paths'])}")
        logger.info(f"URLs discovered: {len(result['all_urls'])}")
        logger.info(f"Report saved: {result['report_path']}")
        logger.info(f"HTML Report saved: {result['html_report_path']}")
        with open('crawler_results.json', 'w') as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        logger.error(f"Error during crawling: {e}", exc_info=True)