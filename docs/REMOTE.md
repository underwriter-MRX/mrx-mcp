# Remote deployment

The source supports stateless Streamable HTTP at `/mcp` in addition to the default local stdio command. Production endpoint: `https://mrx-public-mcp.vercel.app/mcp`. Health: `https://mrx-public-mcp.vercel.app/health`. The isolated deployment was tested with a real MCP client on September 23, 2026. GitHub publication and hosted availability remain separate milestones.

Set `MRX_MCP_PUBLIC_ORIGIN` to the exact HTTPS origin used by clients (without a trailing slash). Host/Origin validation rejects other hosts. Bind `HOST=0.0.0.0` only inside the intended hosting environment, behind TLS. Run `mrx-mcp-http`, or build the included non-root Docker image. `PORT` defaults to 8000. Do not point this process at private systems or add credentials: all tools read public MRX material only.

`/health` reports process health, not corpus readiness, indexing or citation outcomes. The MCP index verifies current public discovery and individual content integrity. A cold full-text index must fetch the public corpus; set `MRX_MCP_PREWARM=1` to warm it during process startup before inviting clients, and measure cold/warm latency. The opted-in process refreshes its public index every 30 minutes while running. Startup warming is bounded. With the prewarm option enabled, standard search also performs a bounded on-demand warm-up when a replaced serverless instance remains incomplete, then rechecks coverage and still refuses an incomplete result. Do not remove verification to improve availability.

The included `api/index.py` and `vercel.json` provide an isolated Vercel Functions deployment entrypoint with a 300-second invocation limit. Set the exact production origin and prewarm option in the project environment. Verify cold-start timing on the actual host; in-memory indexes and background refresh do not persist across instance replacement. A deployment that times out or returns incomplete search is not ready for advertised use.

Before public release, verify TLS, exact production hostname, Host/Origin rejection, bounded request bodies, provider abuse/rate controls and resource limits, and cold/restart behavior. The SDK caps request bodies at 32 KiB and application admission is limited to four concurrent HTTP requests per process. Access logging is disabled in the application; configure provider logs consistently with your published privacy policy. Do not log research queries or returned source text. Public data does not require end-user authentication; adding private access would require a separately reviewed authentication and authorization design.

Use a real MCP client to initialize, list tools, call search and fetch, and check canonical citations. Test private/cross-origin IDs, incomplete-index errors and invalid inputs. Run `python -m unittest discover -s tests -v` before publishing.

For ChatGPT deep research/company knowledge, this package supplies standard `search(query)` and `fetch(id)` tools with output schemas, structured content and JSON text fallback. The standard search rejects incomplete corpus coverage; `mrx_search_guides` reports explicit coverage for diagnosis. Ordinary MRX tool names remain available.

A hosted endpoint is not automatically a public ChatGPT listing. Complete the current OpenAI submission/review process with the real deployment, privacy policy, verified domain and reviewer test cases. Keep account access, registry publication, successful connection and search-engine visibility as separate milestones.

Official references:
- https://developers.openai.com/api/docs/mcp
- https://developers.openai.com/plugins/deploy/submission
- https://modelcontextprotocol.io/specification/latest/basic/transports
