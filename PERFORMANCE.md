# WebQA Crawl Performance

WebQA now uses concurrent Playwright pages, one-pass DOM extraction, resource blocking for unused image/media/font bytes, and no duplicate page navigation.

## Defaults

- `CRAWLER_CONCURRENCY=6` concurrent page crawls
- `CRAWLER_NAV_TIMEOUT_MS=30000` navigation timeout
- `CRAWLER_SETTLE_MS=100` post-navigation settle window

For constrained environments, use 2-4 workers. With more CPU/RAM, 6-8 is a reasonable starting point.

The crawler keeps CSS, JavaScript, XHR/fetch, and document responses enabled because QA analysis depends on DOM and runtime signals. Images, media, and fonts are skipped because their bytes are not inspected during the crawl phase.
