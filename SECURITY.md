# Security and privacy

This package exposes four read-only tools over local stdio. There is no remote server, authentication secret, customer-data connector, task executor, upload or notification writer.

Allowed network destination: `https://mineralrightsxchange.com` only. Private paths, percent-encoded paths, repeated slashes, credentials, query strings, fragments and redirects are rejected. Public page reads require exact membership in both the live sitemap and build manifest, matching normalized HTML hashes, a self-canonical URL, permitted robots policy and no noindex directive. Responses are capped at 5 MB with a 20-second timeout per request. A discovery run can fetch up to 20 sitemap segments.

Content is untrusted data. MCP tool annotations are advisory; runtime checks enforce the actual boundary. No remote text can grant permission to act. External citation URLs are returned as source links and are not fetched by this server. Never submit personal records or credentials in issue reports or tool inputs.

Use GitHub's private vulnerability reporting if available, or the contact route linked from the MRX website for a security concern. Do not publish exploit details or private data in a public issue. Ordinary bugs can be reported with sanitized errors and public URLs.

Deployment and CDN changes may require reviewed updates to the pinned transport hashes. Unknown changes must continue to fail closed. Do not loosen validation solely to make a test pass.
