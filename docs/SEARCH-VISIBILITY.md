# Search visibility verification

MCP usability, crawler access, indexing, citations and customer outcomes are separate measurements.

## Existing public controls

MRX publishes robots rules, sitemaps, canonical HTML, a crawler manifest and optional LLM discovery files. Preserve private-route exclusions. OAI-SearchBot governs OpenAI search crawling; GPTBot training access is an independent owner policy. Do not change training policy as an assumed search optimization.

## Verification sequence

1. Read current robots, canonical, noindex/snippet controls, sitemap and representative rendered pages.
2. Check ordinary and declared crawler user-agent responses. Label these synthetic requests; they do not verify genuine crawler IPs.
3. Verify actual bot requests using provider logs and official IP verification. Check status codes, challenge responses and representative deep paths.
4. Read Google Search Console URL Inspection for representative public pages: index status, last crawl, Google-selected canonical and rendered content.
5. Verify Search Console's Search generative AI inclusion control and inherited property settings.
6. Read the Generative AI performance report, if available. Preserve unavailable/insufficient-data states; do not interpret missing reports or data as zero visibility.
7. Measure AI referrals separately from successful MCP calls, qualified requests and completed human reviews. Do not store private research questions to count adoption.

Avoid duplicate notification executors: MRX's existing crawler notification/release workflow owns submissions. A notification receipt is not indexing proof. Coordinate any website changes and Search Atlas recrawl with the current website release owner.

## Content improvement

Use original, evidence-backed MRX educational resources with accurate attribution, appropriate professional review and authoritative sources. Do not invent reviewers or fabricate case studies. New articles and document examples follow the MRX editorial/compliance/article-image release gates; the MCP package is not an exemption.

References:
- https://developers.openai.com/api/docs/bots
- https://developers.google.com/search/docs/fundamentals/ai-optimization-guide
- https://support.google.com/webmasters/answer/16908024
- https://support.google.com/webmasters/answer/16984139
