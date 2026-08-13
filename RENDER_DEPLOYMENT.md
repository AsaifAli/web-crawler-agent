# Render Deployment

## Public demo topology

The public demo runs the crawler UI as a Docker web service on Render.

- Browser -> Streamlit
- Crawler -> Playwright/Chromium
- LLM -> external OpenAI-compatible HTTPS endpoint
- Ollama -> disabled for cloud deployment

## Free-tier constraints

Playwright/Chromium is resource-intensive. The demo intentionally limits crawl depth/page count so it remains suitable for a portfolio demonstration. A larger runtime may be required if representative crawls exceed the free instance's memory.

## Required secret

Set `OPENAI_API_KEY` in Render.

Do not commit API keys or local `.env` files to GitHub.


## CI gate
GitHub Actions checks the public application entrypoint and tests before deployment. Historical POC code remains in the repository for reference and is not included in the Render runtime.
