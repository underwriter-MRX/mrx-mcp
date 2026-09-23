# Adoption and launch roadmap

The first audience is people already using MCP-compatible assistants for general mineral-rights research. The useful action is a source-linked answer followed, when relevant, by a user-chosen MRX human-review journey.

## Included in this release

- Portable versioned install, six read-only tools, a reusable research prompt and examples.
- Canonical citations, retrieval timestamps, integrity verification and explicit privacy boundaries.
- Fixture tests, real protocol checks, and reproducible package build.
- A tagged GitHub distribution, a live remote endpoint, and an active official MCP Registry listing for version 0.2.0.

## Next experiments, in order

1. **Show the workflow:** a short demonstration of searching, reading a cited guide and choosing a next step. Put installation, privacy and troubleshooting beside it. Measure successful first reads per installation attempt; installs alone do not show usefulness.
2. **Add first-party discovery:** an MRX “Use with your AI assistant” page linked from appropriate learning pages. This requires the website's normal release and SEO checks. Include a plain browser option for visitors who do not use MCP.
3. **Distribute the working package:** publish the working remote endpoint to the official MCP Registry and submit to relevant client directories. Verify each listing. GitHub presence alone is not registry publication. The remote-only official listing was published and independently read back on September 23, 2026. `docs/server.json` describes that endpoint and does not depend on PyPI. Add a PyPI package entry only after that distribution is publicly verified. The README includes the required package identity marker. Use the [official registry publishing guide](https://modelcontextprotocol.io/registry/quickstart).
4. **Measure relevant referrals:** compare deduplicated qualified review requests to eligible referred journeys, then completed human reviews to eligible ready cases due for review. Preserve unknown attribution, consent choices, spam exclusions, queue age and the full review window. Do not add prompt or document telemetry to the MCP.
5. **Deploy the remote transport:** this release includes a stateless HTTP server and deployment guide. Verify the actual HTTPS endpoint, provider abuse controls and cold/restart behavior before advertising remote availability. Hosting, PyPI/Registry publication and ChatGPT submission are separate recorded milestones.

For search traffic, maintain useful public answers, crawlable links and accurate metadata. Google states that established SEO practices apply to AI search features; a special MCP or AI text file is not a substitute for eligibility or useful content. [Google Search guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide).

These are testable recommendations, not traffic or ranking forecasts. Keep installation success, website visits, qualified requests, completed reviews, and agreed next steps as separate measures. Paid promotion and unsolicited outreach are not part of this release.
