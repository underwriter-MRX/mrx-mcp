# Adoption and launch roadmap

The first audience is people already using MCP-compatible assistants for general mineral-rights research. The useful action is a source-linked answer followed, when relevant, by a user-chosen MRX human-review journey.

## Included in this release

- Portable versioned install, four read-only tools, a reusable research prompt and examples.
- Canonical citations, retrieval timestamps, integrity verification and explicit privacy boundaries.
- Fixture tests, real protocol checks, and reproducible package build.
- A tagged GitHub distribution and an MRX referral link in the README.

## Next experiments, in order

1. **Show the workflow:** a short demonstration of searching, reading a cited guide and choosing a next step. Put installation, privacy and troubleshooting beside it. Measure successful first reads per installation attempt; installs alone do not show usefulness.
2. **Add first-party discovery:** an MRX “Use with your AI assistant” page linked from appropriate learning pages. This requires the website's normal release and SEO checks. Include a plain browser option for visitors who do not use MCP.
3. **Distribute the working package:** publish a tested Python package and then submit to the official MCP Registry and relevant client directories. Verify each listing. GitHub presence alone is not registry publication. Use the [official registry publishing guide](https://github.com/modelcontextprotocol/registry/blob/main/docs/guides/publishing/publish-server.md).
4. **Measure relevant referrals:** compare deduplicated qualified review requests to eligible referred journeys, then completed human reviews to eligible ready cases due for review. Preserve unknown attribution, consent choices, spam exclusions, queue age and the full review window. Do not add prompt or document telemetry to the MCP.
5. **Reduce installation friction if usage supports it:** evaluate a maintained remote public-content connector. Treat hosting, abuse controls, client compatibility and any paid capacity as a separate deployment decision. This local package is not a remote connector.

For search traffic, maintain useful public answers, crawlable links and accurate metadata. Google states that established SEO practices apply to AI search features; a special MCP or AI text file is not a substitute for eligibility or useful content. [Google Search guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide).

These are testable recommendations, not traffic or ranking forecasts. Keep installation success, website visits, qualified requests, completed reviews, and agreed next steps as separate measures. Paid promotion and unsolicited outreach are not part of this release.
